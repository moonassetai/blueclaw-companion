from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from .execution_mode import DesktopOptions, DesktopTarget, ExecutionMode, resolve_desktop_options, resolve_desktop_target
from .perception_backends import resolve_perception_plan
from .screen_analysis import ScreenAnalysis, analyze_screen
from .ui_dump_parser import UiDump, load_ui_dump


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"
WORKFLOWS_DIR = ROOT_DIR / "workflows"
ARTIFACTS_DIR = ROOT_DIR / "artifacts" / "phase2"

READ_ONLY_ACTIONS = {"capture_and_classify", "branch_on_state"}


@dataclass
class WorkflowContext:
    workflow_name: str
    variables: dict[str, str]
    dry_run: bool = False
    approve_sensitive: bool = False
    approve_all_boundaries: bool = False
    execution_mode: str = "adb"
    desktop_target: DesktopTarget = field(default_factory=DesktopTarget)
    desktop_options: DesktopOptions = field(default_factory=DesktopOptions)
    artifacts_dir: Path = ARTIFACTS_DIR
    last_analysis: ScreenAnalysis | None = None
    last_ui_dump: UiDump | None = None
    command_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowResult:
    workflow: str
    status: str
    completed_steps: list[str]
    next_step: str | None
    message: str
    analysis: dict[str, Any] | None
    commands: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkflowError(RuntimeError):
    pass


def load_workflow(workflow_name: str) -> dict[str, Any]:
    path = WORKFLOWS_DIR / f"{workflow_name}.json"
    if not path.exists():
        raise WorkflowError(f"Workflow not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def merge_variables(workflow: dict[str, Any], overrides: dict[str, str]) -> dict[str, str]:
    merged = {key: str(value) for key, value in workflow.get("defaults", {}).items()}
    for key, value in overrides.items():
        merged[key] = str(value)
    return merged


def format_value(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        return value.format(**variables)
    if isinstance(value, list):
        return [format_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: format_value(item, variables) for key, item in value.items()}
    return value


def run_powershell_script(script_name: str, params: dict[str, Any], context: WorkflowContext) -> subprocess.CompletedProcess[str]:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise WorkflowError(f"Script not found: {script_path}")

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    for key, value in params.items():
        if value is None or value == "":
            continue
        command.extend([f"-{key}", str(value)])

    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT_DIR)
    context.command_log.append(
        {
            "script": script_name,
            "params": params,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise WorkflowError(f"{script_name} failed: {detail}")
    return result


def parse_running_app(output: str) -> str | None:
    for line in output.splitlines():
        if line.lower().startswith("foreground package:"):
            return line.split(":", 1)[1].strip()
        # Fallback for old output logs if any are retained
        if line.lower().startswith("foreground package:"):
            return line.split(":", 1)[1].strip()
    return None


def capture_and_classify(step_id: str, step: dict[str, Any], context: WorkflowContext) -> ScreenAnalysis:
    context.artifacts_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    use_ocr = bool(step.get("use_ocr"))
    capture_screenshot = bool(step.get("screenshot", True))
    perception_plan = resolve_perception_plan(
        execution_mode=context.execution_mode,
        prefer_ocr=use_ocr,
    )
    resolved_use_ocr = perception_plan.ocr_backend != "none"

    screenshot_path = context.artifacts_dir / f"{context.workflow_name}-{step_id}-{timestamp}.png"
    ui_dump_path = context.artifacts_dir / f"{context.workflow_name}-{step_id}-{timestamp}.xml"

    mode = ExecutionMode.from_value(perception_plan.execution_mode)
    if perception_plan.capture_backend == "desktop_capture" and mode == ExecutionMode.DESKTOP:
        from .desktop_state import capture_desktop_state

        result = capture_desktop_state(
            screenshot_path=screenshot_path,
            package_name=context.variables.get("PackageName"),
            use_ocr=resolved_use_ocr,
            desktop_target=context.desktop_target,
            desktop_options=context.desktop_options,
        )
        context.last_analysis = result.analysis
        context.last_ui_dump = None
        return result.analysis

    params: dict[str, object] = {
        "UiDumpPath": str(ui_dump_path),
    }
    if capture_screenshot or resolved_use_ocr:
        params["ScreenshotPath"] = str(screenshot_path)

    app_result = run_powershell_script("capture-all.ps1", params, context)
    package_name = parse_running_app(app_result.stdout)

    analysis = analyze_screen(
        screenshot_path=str(screenshot_path) if capture_screenshot or resolved_use_ocr else None,
        ui_dump_path=str(ui_dump_path),
        package_name=package_name,
        use_ocr=resolved_use_ocr,
    )
    context.last_analysis = analysis
    context.last_ui_dump = load_ui_dump(ui_dump_path)
    return analysis


def ensure_analysis(context: WorkflowContext) -> ScreenAnalysis:
    if not context.last_analysis:
        raise WorkflowError("No screen analysis is available yet for this workflow run.")
    return context.last_analysis


def choose_next_step(workflow: dict[str, Any], step_id: str | None) -> str | None:
    if step_id is None:
        return None
    steps = workflow["steps"]
    ids = [step["id"] for step in steps]
    try:
        index = ids.index(step_id)
    except ValueError as exc:
        raise WorkflowError(f"Unknown step id: {step_id}") from exc
    if index + 1 >= len(steps):
        return None
    return ids[index + 1]


def run_workflow(
    workflow_name: str,
    variable_overrides: dict[str, str] | None = None,
    dry_run: bool = False,
    approve_sensitive: bool = False,
    approve_all_boundaries: bool = False,
    execution_mode: str = "adb",
    desktop_target: DesktopTarget | None = None,
    desktop_options: DesktopOptions | None = None,
) -> WorkflowResult:
    workflow = load_workflow(workflow_name)
    variables = merge_variables(workflow, variable_overrides or {})
    context = WorkflowContext(
        workflow_name=workflow_name,
        variables=variables,
        dry_run=dry_run,
        approve_sensitive=approve_sensitive,
        approve_all_boundaries=approve_all_boundaries,
        execution_mode=execution_mode,
        desktop_target=desktop_target or resolve_desktop_target(),
        desktop_options=desktop_options or resolve_desktop_options(),
    )

    completed_steps: list[str] = []
    step_lookup = {step["id"]: step for step in workflow["steps"]}
    next_step = workflow["steps"][0]["id"] if workflow.get("steps") else None

    while next_step:
        step = step_lookup[next_step]
        action = step["action"]

        if context.dry_run and action not in READ_ONLY_ACTIONS:
            return WorkflowResult(
                workflow=workflow_name,
                status="dry_run",
                completed_steps=completed_steps,
                next_step=next_step,
                message=f"Next mutating step: {next_step}",
                analysis=context.last_analysis.to_dict() if context.last_analysis else None,
                commands=context.command_log,
            )

        if action == "script":
            params = format_value(step.get("params", {}), context.variables)
            run_powershell_script(step["script"], params, context)
            completed_steps.append(next_step)
            next_step = choose_next_step(workflow, next_step)
            continue

        if action == "capture_and_classify":
            capture_and_classify(next_step, step, context)
            completed_steps.append(next_step)
            next_step = choose_next_step(workflow, next_step)
            continue

        if action == "branch_on_state":
            analysis = ensure_analysis(context)
            target_state = step["state"]
            next_step = step["on_match"] if analysis.state == target_state else step["on_no_match"]
            completed_steps.append(step["id"])
            continue

        if action == "tap_ui_text":
            if ExecutionMode.from_value(context.execution_mode) == ExecutionMode.DESKTOP:
                raise WorkflowError("tap_ui_text requires an Android UI dump and is not available in desktop mode.")
            if not context.last_ui_dump:
                raise WorkflowError("No UI dump is available for tap_ui_text.")
            labels = format_value(step["labels"], context.variables)
            node = context.last_ui_dump.find_first_node(labels)
            if not node or not node.bounds:
                raise WorkflowError(f"Could not find a tappable node for labels: {labels}")
            x, y = node.bounds.center
            run_powershell_script("tap.ps1", {"X": x, "Y": y}, context)
            completed_steps.append(step["id"])
            next_step = choose_next_step(workflow, next_step)
            continue

        if action == "approval_required":
            needs_sensitive_approval = bool(step.get("sensitive", True))
            approved = context.approve_all_boundaries or (context.approve_sensitive and needs_sensitive_approval)
            if not approved:
                return WorkflowResult(
                    workflow=workflow_name,
                    status="approval_required",
                    completed_steps=completed_steps,
                    next_step=next_step,
                    message=step["message"],
                    analysis=context.last_analysis.to_dict() if context.last_analysis else None,
                    commands=context.command_log,
                )
            completed_steps.append(step["id"])
            next_step = choose_next_step(workflow, next_step)
            continue

        if action == "stop":
            return WorkflowResult(
                workflow=workflow_name,
                status="stopped",
                completed_steps=completed_steps,
                next_step=None,
                message=step["message"],
                analysis=context.last_analysis.to_dict() if context.last_analysis else None,
                commands=context.command_log,
            )

        raise WorkflowError(f"Unsupported workflow action: {action}")

    return WorkflowResult(
        workflow=workflow_name,
        status="completed",
        completed_steps=completed_steps,
        next_step=None,
        message="Workflow completed.",
        analysis=context.last_analysis.to_dict() if context.last_analysis else None,
        commands=context.command_log,
    )

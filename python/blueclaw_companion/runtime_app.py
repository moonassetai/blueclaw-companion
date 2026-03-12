from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from .desktop_state import capture_desktop_state
from .execution_mode import DesktopOptions, DesktopTarget, ExecutionMode
from .mobile_game_learner import capture_current_screen, run_learning_cycle
from .window_control import (
    WindowMetadata,
    click_bluestacks_relative,
    detect_bluestacks_window,
    focus_bluestacks_window,
    send_bluestacks_key,
)
from .workflow_runner import ROOT_DIR, WorkflowError, run_workflow


SCRIPTS_DIR = ROOT_DIR / "scripts"


@dataclass(frozen=True)
class RuntimeStatus:
    selected_mode: str
    effective_mode: str
    target: dict[str, object]
    bluestacks_found: bool
    adb_connected: bool
    adb_message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _short_error(message: str) -> str:
    if not message:
        return "Unknown error."
    line = message.strip().splitlines()[0].strip()
    if not line:
        return "Unknown error."
    return line


def _window_payload(window: WindowMetadata | None) -> dict[str, object] | None:
    return window.to_dict() if window else None


def _run_script(script_name: str, params: dict[str, Any] | None = None) -> subprocess.CompletedProcess[str]:
    script_path = SCRIPTS_DIR / script_name
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    for key, value in (params or {}).items():
        if value is None or value == "":
            continue
        command.extend([f"-{key}", str(value)])
    return subprocess.run(command, capture_output=True, text=True, cwd=ROOT_DIR)


def try_connect_adb(*, device: str | None = None, adb_path: str | None = None) -> tuple[bool, str]:
    result = _run_script(
        "connect-bluestacks.ps1",
        {
            "Device": device,
            "AdbPath": adb_path,
        },
    )
    if result.returncode == 0:
        stdout = result.stdout.strip()
        return True, stdout or "ADB connected."
    detail = result.stderr.strip() or result.stdout.strip() or f"connect-bluestacks.ps1 failed with exit code {result.returncode}"
    return False, _short_error(detail)


def resolve_effective_mode(
    selected_mode: ExecutionMode,
    *,
    bluestacks_found: bool,
) -> ExecutionMode:
    if selected_mode == ExecutionMode.HYBRID:
        return ExecutionMode.DESKTOP if bluestacks_found else ExecutionMode.ADB
    return selected_mode


def inspect_runtime(
    *,
    mode: str,
    profile: str,
    use_ocr: bool,
    capture_screenshot: bool,
    connect_adb: bool,
    focus_window: bool,
    device: str | None,
    adb_path: str | None,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    selected_mode = ExecutionMode.from_value(mode)
    window = detect_bluestacks_window(target=desktop_target)
    bluestacks_found = window is not None

    focused_window = window
    focus_error = ""
    if focus_window and selected_mode in {ExecutionMode.DESKTOP, ExecutionMode.HYBRID}:
        try:
            focused_window = focus_bluestacks_window(target=desktop_target, options=desktop_options)
            bluestacks_found = True
        except Exception as exc:  # noqa: BLE001
            focus_error = _short_error(str(exc))

    adb_connected = False
    adb_message = "not_attempted"
    if connect_adb and selected_mode in {ExecutionMode.ADB, ExecutionMode.HYBRID}:
        adb_connected, adb_message = try_connect_adb(device=device, adb_path=adb_path)

    effective_mode = resolve_effective_mode(selected_mode, bluestacks_found=bluestacks_found)

    try:
        learner_result = run_learning_cycle(
            profile_id=profile,
            capture=True,
            connect=False,
            capture_screenshot=capture_screenshot,
            use_ocr=use_ocr,
            control_mode=effective_mode.value,
            desktop_target=desktop_target,
            desktop_options=desktop_options,
            execute_safe_actions=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Inspect failed: {_short_error(str(exc))}") from exc

    status = RuntimeStatus(
        selected_mode=selected_mode.value,
        effective_mode=effective_mode.value,
        target=desktop_target.to_dict(),
        bluestacks_found=bluestacks_found,
        adb_connected=adb_connected,
        adb_message=adb_message,
    )
    payload = {
        "command": "inspect",
        "status": status.to_dict(),
        "window": _window_payload(focused_window),
        "focus_error": focus_error or None,
        "screen": learner_result.screen,
        "state": learner_result.state,
        "action": learner_result.action,
        "decision": learner_result.decision,
        "memory_path": learner_result.memory_path,
    }
    return payload


def capture_runtime(
    *,
    mode: str,
    output_path: str | None,
    use_ocr: bool,
    connect_adb: bool,
    device: str | None,
    adb_path: str | None,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    selected_mode = ExecutionMode.from_value(mode)
    window = detect_bluestacks_window(target=desktop_target)
    effective_mode = resolve_effective_mode(selected_mode, bluestacks_found=window is not None)

    adb_connected = False
    adb_message = "not_attempted"
    if connect_adb and effective_mode == ExecutionMode.ADB:
        adb_connected, adb_message = try_connect_adb(device=device, adb_path=adb_path)

    try:
        if effective_mode == ExecutionMode.DESKTOP:
            screenshot = output_path or str(ROOT_DIR / "artifacts" / f"runtime-capture-{time.strftime('%Y%m%d-%H%M%S')}.png")
            result = capture_desktop_state(
                screenshot_path=screenshot,
                use_ocr=use_ocr,
                desktop_target=desktop_target,
                desktop_options=desktop_options,
            )
            analysis = result.analysis.to_dict()
            capture_payload = result.capture.to_dict()
        else:
            analysis = capture_current_screen(
                connect=False,
                capture_screenshot=True,
                use_ocr=use_ocr,
                control_mode=ExecutionMode.ADB.value,
                desktop_target=desktop_target,
                desktop_options=desktop_options,
            ).to_dict()
            capture_payload = {
                "output_path": analysis.get("screenshot_path"),
                "capture_mode": "adb_screenshot",
                "window": None,
            }
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Capture failed: {_short_error(str(exc))}") from exc

    status = RuntimeStatus(
        selected_mode=selected_mode.value,
        effective_mode=effective_mode.value,
        target=desktop_target.to_dict(),
        bluestacks_found=window is not None,
        adb_connected=adb_connected,
        adb_message=adb_message,
    )
    return {
        "command": "capture",
        "status": status.to_dict(),
        "capture": capture_payload,
        "analysis": analysis,
    }


def focus_runtime(*, desktop_target: DesktopTarget, desktop_options: DesktopOptions) -> dict[str, object]:
    try:
        window = focus_bluestacks_window(target=desktop_target, options=desktop_options)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Focus failed: {_short_error(str(exc))}") from exc
    return {
        "command": "focus",
        "window": window.to_dict(),
    }


def send_key_runtime(
    *,
    key: str,
    repeat_count: int,
    delay_ms: int,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    try:
        payload = send_bluestacks_key(
            key,
            repeat_count=repeat_count,
            delay_ms=delay_ms,
            target=desktop_target,
            options=desktop_options,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Send-key failed: {_short_error(str(exc))}") from exc
    return {
        "command": "send-key",
        "result": payload,
    }


def click_runtime(
    *,
    x: int,
    y: int,
    repeat_count: int,
    delay_ms: int,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    try:
        payload = click_bluestacks_relative(
            x,
            y,
            repeat_count=repeat_count,
            delay_ms=delay_ms,
            target=desktop_target,
            options=desktop_options,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Click failed: {_short_error(str(exc))}") from exc
    return {
        "command": "click",
        "result": payload,
    }


def connect_runtime(*, device: str | None, adb_path: str | None) -> dict[str, object]:
    connected, message = try_connect_adb(device=device, adb_path=adb_path)
    return {
        "command": "connect",
        "adb_connected": connected,
        "message": message,
    }


def learner_runtime(
    *,
    mode: str,
    profile: str,
    use_ocr: bool,
    capture_screenshot: bool,
    connect_adb: bool,
    device: str | None,
    adb_path: str | None,
    execute_safe_actions: bool,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    selected_mode = ExecutionMode.from_value(mode)
    window = detect_bluestacks_window(target=desktop_target)
    effective_mode = resolve_effective_mode(selected_mode, bluestacks_found=window is not None)

    adb_connected = False
    adb_message = "not_attempted"
    if connect_adb and effective_mode == ExecutionMode.ADB:
        adb_connected, adb_message = try_connect_adb(device=device, adb_path=adb_path)

    try:
        result = run_learning_cycle(
            profile_id=profile,
            capture=True,
            connect=False,
            capture_screenshot=capture_screenshot,
            use_ocr=use_ocr,
            control_mode=effective_mode.value,
            desktop_target=desktop_target,
            desktop_options=desktop_options,
            execute_safe_actions=execute_safe_actions,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Learner failed: {_short_error(str(exc))}") from exc

    status = RuntimeStatus(
        selected_mode=selected_mode.value,
        effective_mode=effective_mode.value,
        target=desktop_target.to_dict(),
        bluestacks_found=window is not None,
        adb_connected=adb_connected,
        adb_message=adb_message,
    )
    return {
        "command": "learner",
        "status": status.to_dict(),
        "result": result.to_dict(),
    }


def workflow_runtime(
    *,
    mode: str,
    workflow_name: str,
    vars_items: list[str],
    connect_adb: bool,
    device: str | None,
    adb_path: str | None,
    dry_run: bool,
    approve_sensitive: bool,
    approve_all_boundaries: bool,
    desktop_target: DesktopTarget,
    desktop_options: DesktopOptions,
) -> dict[str, object]:
    selected_mode = ExecutionMode.from_value(mode)
    window = detect_bluestacks_window(target=desktop_target)
    effective_mode = resolve_effective_mode(selected_mode, bluestacks_found=window is not None)
    adb_connected = False
    adb_message = "not_attempted"

    if connect_adb:
        adb_connected, adb_message = try_connect_adb(device=device, adb_path=adb_path)

    variables: dict[str, str] = {}
    for item in vars_items:
        if "=" not in item:
            raise RuntimeError(f"Invalid --var value `{item}`. Expected KEY=VALUE.")
        key, value = item.split("=", 1)
        variables[key] = value

    try:
        result = run_workflow(
            workflow_name=workflow_name,
            variable_overrides=variables,
            dry_run=dry_run,
            approve_sensitive=approve_sensitive,
            approve_all_boundaries=approve_all_boundaries,
            execution_mode=effective_mode.value,
            desktop_target=desktop_target,
            desktop_options=desktop_options,
        )
    except WorkflowError as exc:
        raise RuntimeError(f"Workflow failed: {_short_error(str(exc))}") from exc

    status = RuntimeStatus(
        selected_mode=selected_mode.value,
        effective_mode=effective_mode.value,
        target=desktop_target.to_dict(),
        bluestacks_found=window is not None,
        adb_connected=adb_connected,
        adb_message=adb_message,
    )

    return {
        "command": "workflow",
        "status": status.to_dict(),
        "result": result.to_dict(),
    }


def render_runtime_result(payload: dict[str, object]) -> str:
    command = str(payload.get("command", "run"))
    if command == "inspect":
        status = payload["status"]
        state = payload["state"]
        action = payload["action"]
        lines = [
            f"Mode: {status['selected_mode']} (effective: {status['effective_mode']})",
            f"BlueStacks found: {status['bluestacks_found']}",
            f"ADB connected: {status['adb_connected']} ({status['adb_message']})",
            f"State: {state['state']} ({state['confidence']:.2f})",
            f"Suggested action: {action['action']} [{action['action_type']}]",
        ]
        if payload.get("focus_error"):
            lines.append(f"Focus warning: {payload['focus_error']}")
        return "\n".join(lines)

    if command == "capture":
        status = payload["status"]
        capture = payload["capture"]
        analysis = payload["analysis"]
        return "\n".join(
            [
                f"Mode: {status['selected_mode']} (effective: {status['effective_mode']})",
                f"Capture mode: {capture['capture_mode']}",
                f"Output: {capture['output_path'] or 'n/a'}",
                f"State: {analysis['state']}",
                f"OCR: {analysis['ocr_status']}",
            ]
        )

    if command == "connect":
        return f"ADB connected: {payload['adb_connected']} ({payload['message']})"

    if command in {"focus", "send-key", "click"}:
        return json.dumps(payload, indent=2)

    if command == "learner":
        status = payload["status"]
        result = payload["result"]
        return "\n".join(
            [
                f"Mode: {status['selected_mode']} (effective: {status['effective_mode']})",
                f"Detected state: {result['state']['state']}",
                f"Suggested action: {result['action']['action']}",
                f"Decision: {result['decision']['decision']}",
                f"Memory: {result['memory_path']}",
            ]
        )

    if command == "workflow":
        status = payload["status"]
        result = payload["result"]
        return "\n".join(
            [
                f"Mode: {status['selected_mode']} (effective: {status['effective_mode']})",
                f"BlueStacks found: {status['bluestacks_found']}",
                f"ADB connected: {status['adb_connected']} ({status['adb_message']})",
                f"Workflow: {result['workflow']}",
                f"Status: {result['status']}",
                f"Message: {result['message']}",
            ]
        )

    return json.dumps(payload, indent=2)

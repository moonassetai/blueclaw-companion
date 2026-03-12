from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import time

from .action_policy import ActionSuggestion, choose_action
from .game_profiles import PROFILE_REGISTRY_PATH, GameProfile, load_game_profile
from .game_state import GameStateResult, classify_game_state
from .screen_analysis import ScreenAnalysis, analyze_screen
from .workflow_memory import WorkflowMemoryEntry, append_memory_entry, build_memory_entry
from .workflow_runner import ROOT_DIR, WorkflowContext, parse_running_app, run_powershell_script


ARTIFACTS_DIR = ROOT_DIR / "artifacts" / "mobile-game-learner"
DEFAULT_MEMORY_PATH = ARTIFACTS_DIR / "workflow-memory.jsonl"


@dataclass(frozen=True)
class LearnerResult:
    profile: dict[str, object]
    screen: dict[str, object]
    state: dict[str, object]
    action: dict[str, object]
    memory_entry: dict[str, object]
    memory_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def capture_current_screen(
    *,
    connect: bool = False,
    artifacts_dir: str | Path | None = None,
    capture_screenshot: bool = False,
    use_ocr: bool = False,
) -> ScreenAnalysis:
    target_dir = Path(artifacts_dir) if artifacts_dir else ARTIFACTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    context = WorkflowContext(workflow_name="mobile-game-learner", variables={})
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = target_dir / f"screen-{timestamp}.png"
    ui_dump_path = target_dir / f"screen-{timestamp}.xml"

    if connect:
        run_powershell_script("connect-bluestacks.ps1", {}, context)

    params: dict[str, object] = {
        "UiDumpPath": ui_dump_path,
    }
    if capture_screenshot or use_ocr:
        params["ScreenshotPath"] = screenshot_path

    app_result = run_powershell_script("capture-all.ps1", params, context)
    package_name = parse_running_app(app_result.stdout)
    
    return analyze_screen(
        screenshot_path=str(screenshot_path) if capture_screenshot or use_ocr else None,
        ui_dump_path=str(ui_dump_path),
        package_name=package_name,
        use_ocr=use_ocr,
    )


def run_learning_cycle(
    *,
    profile_id: str = "generic",
    ui_dump_path: str | None = None,
    screenshot_path: str | None = None,
    package_name: str | None = None,
    ui_text: str | None = None,
    profile_path: str | Path | None = None,
    memory_path: str | Path | None = None,
    use_ocr: bool = False,
    connect: bool = False,
    capture: bool = False,
    capture_screenshot: bool = False,
) -> LearnerResult:
    profile: GameProfile = load_game_profile(profile_id=profile_id, path=profile_path)

    if capture:
        analysis = capture_current_screen(
            connect=connect,
            artifacts_dir=ARTIFACTS_DIR,
            capture_screenshot=capture_screenshot,
            use_ocr=use_ocr,
        )
    else:
        analysis = analyze_screen(
            screenshot_path=screenshot_path,
            ui_dump_path=ui_dump_path,
            package_name=package_name or profile.package_name,
            use_ocr=use_ocr,
        )

    state: GameStateResult = classify_game_state(
        analysis=analysis,
        state_hints=profile.known_state_hints,
        ui_text=ui_text,
    )
    action: ActionSuggestion = choose_action(state=state, profile=profile)

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    artifact_paths = {
        key: value
        for key, value in {
            "ui_dump_path": analysis.ui_dump_path or "",
            "screenshot_path": analysis.screenshot_path or "",
            "profile_registry": str(Path(profile_path) if profile_path else PROFILE_REGISTRY_PATH),
        }.items()
        if value
    }
    memory_entry: WorkflowMemoryEntry = build_memory_entry(
        timestamp=timestamp,
        profile=profile,
        state=state,
        action=action,
        artifact_paths=artifact_paths,
    )
    resolved_memory_path = append_memory_entry(memory_path or DEFAULT_MEMORY_PATH, memory_entry)

    return LearnerResult(
        profile=profile.to_dict(),
        screen=analysis.to_dict(),
        state=state.to_dict(),
        action=action.to_dict(),
        memory_entry=memory_entry.to_dict(),
        memory_path=str(resolved_memory_path.resolve()),
    )

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import time

from .action_policy import ActionSuggestion, choose_action
from .control_backends import resolve_control_plan
from .continuation_rules import ContinuationDecision, RuntimePolicy, evaluate_continuation
from .desktop_state import capture_desktop_state
from .execution_mode import DesktopOptions, DesktopTarget, ExecutionMode, resolve_desktop_options, resolve_desktop_target
from .game_memory_store import (
    GameMemory,
    load_game_memory,
    save_game_memory,
    update_game_memory,
)
from .game_profiles import PROFILE_REGISTRY_PATH, GameProfile, load_game_profile
from .game_state import GameStateResult, classify_game_state
from .game_type import GenreProfile
from .game_type_classifier import classify_genre
from .profile_selector import get_genre_profile
from .perception_backends import resolve_perception_plan
from .screen_analysis import ScreenAnalysis, analyze_screen
from .stagnation_detector import CycleSnapshot, evaluate_stagnation
from .ui_dump_parser import UiDump, load_ui_dump
from .window_control import click_bluestacks_relative, focus_bluestacks_window, send_bluestacks_key
from .workflow_memory import WorkflowMemoryEntry, append_memory_entry, build_memory_entry
from .workflow_runner import ROOT_DIR, WorkflowContext, parse_running_app, run_powershell_script


ARTIFACTS_DIR = ROOT_DIR / "artifacts" / "mobile-game-learner"
DEFAULT_MEMORY_PATH = ARTIFACTS_DIR / "workflow-memory.jsonl"
DEFAULT_GAME_MEMORY_DIR = ARTIFACTS_DIR / "games"


@dataclass(frozen=True)
class ActionExecutionResult:
    executed: bool
    outcome: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LearnerResult:
    profile: dict[str, object]
    selected_profile_id: str
    genre: dict[str, object] | None
    screen: dict[str, object]
    state: dict[str, object]
    action: dict[str, object]
    decision: dict[str, object]
    execution: dict[str, object]
    post_action_state: dict[str, object] | None
    memory_entry: dict[str, object]
    memory_path: str
    game_memory_path: str | None
    cycle_index: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_snapshot(self) -> CycleSnapshot:
        next_state = self.post_action_state["state"] if self.post_action_state else self.state["state"]
        progressed = bool(self.execution["executed"]) and next_state != self.state["state"]
        return CycleSnapshot(
            cycle_index=int(self.cycle_index or 0),
            state=str(self.state["state"]),
            action=str(self.action["action"]),
            progressed=progressed,
            state_confidence=float(self.state["confidence"]),
            action_confidence=float(self.action["confidence"]),
        )


def capture_current_screen(
    *,
    connect: bool = False,
    artifacts_dir: str | Path | None = None,
    capture_screenshot: bool = False,
    use_ocr: bool = False,
    control_mode: str = "adb",
    package_name_hint: str | None = None,
    desktop_target: DesktopTarget | None = None,
    desktop_options: DesktopOptions | None = None,
) -> ScreenAnalysis:
    target_dir = Path(artifacts_dir) if artifacts_dir else ARTIFACTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = target_dir / f"screen-{timestamp}.png"
    ui_dump_path = target_dir / f"screen-{timestamp}.xml"

    perception_plan = resolve_perception_plan(
        execution_mode=control_mode,
        prefer_ocr=use_ocr,
    )
    resolved_mode = ExecutionMode.from_value(perception_plan.execution_mode)
    resolved_target = desktop_target or resolve_desktop_target()
    resolved_options = desktop_options or resolve_desktop_options()
    resolved_use_ocr = perception_plan.ocr_backend != "none"

    if perception_plan.capture_backend == "desktop_capture" and resolved_mode == ExecutionMode.DESKTOP:
        result = capture_desktop_state(
            screenshot_path=screenshot_path,
            package_name=package_name_hint,
            use_ocr=resolved_use_ocr,
            desktop_target=resolved_target,
            desktop_options=resolved_options,
        )
        return result.analysis

    context = WorkflowContext(workflow_name="mobile-game-learner", variables={})

    if connect:
        run_powershell_script("connect-bluestacks.ps1", {}, context)

    params: dict[str, object] = {"UiDumpPath": ui_dump_path}
    if capture_screenshot or use_ocr:
        params["ScreenshotPath"] = screenshot_path

    app_result = run_powershell_script("capture-all.ps1", params, context)
    package_name = parse_running_app(app_result.stdout)

    return analyze_screen(
        screenshot_path=str(screenshot_path) if capture_screenshot or resolved_use_ocr else None,
        ui_dump_path=str(ui_dump_path),
        package_name=package_name,
        use_ocr=resolved_use_ocr,
    )


def _resolve_genre(
    *,
    analysis: ScreenAnalysis,
    state: GameStateResult,
    game_memory: GameMemory | None,
) -> tuple[str, float]:
    genre_id = classify_genre(
        package_name=analysis.package_name,
        visible_texts=analysis.visible_text,
        current_state=state.state,
    )
    if genre_id != "unknown":
        return genre_id, 0.72
    if game_memory and game_memory.inferred_genre != "unknown":
        return game_memory.inferred_genre, max(game_memory.genre_confidence, 0.65)
    return "unknown", 0.0


def _merge_state_hints(profile: GameProfile, game_memory: GameMemory | None) -> dict[str, list[str]]:
    merged = {key: list(values) for key, values in profile.known_state_hints.items()}
    if not game_memory:
        return merged
    for state, values in game_memory.state_hints.items():
        merged.setdefault(state, [])
        for value in values:
            if value not in merged[state]:
                merged[state].append(value)
    return merged


def _count_unknown_streak(history: list[CycleSnapshot], current_state: str) -> int:
    streak = 1 if current_state == "unknown" else 0
    if current_state != "unknown":
        return 0
    for entry in reversed(history):
        if entry.state != "unknown":
            break
        streak += 1
    return streak


def _count_low_confidence_streak(
    history: list[CycleSnapshot],
    *,
    current_state_confidence: float,
    current_action_confidence: float,
    policy: RuntimePolicy,
) -> int:
    current_low = current_state_confidence < policy.min_state_confidence or current_action_confidence < policy.min_action_confidence
    if not current_low:
        return 0
    streak = 1
    for entry in reversed(history):
        if entry.state_confidence >= policy.min_state_confidence and entry.action_confidence >= policy.min_action_confidence:
            break
        streak += 1
    return streak


def _load_ui_dump(analysis: ScreenAnalysis) -> UiDump | None:
    if not analysis.ui_dump_path:
        return None
    return load_ui_dump(analysis.ui_dump_path)


def execute_action(
    *,
    action: ActionSuggestion,
    analysis: ScreenAnalysis,
    wait_seconds: float = 1.0,
    control_mode: str = "adb",
    desktop_target: DesktopTarget | None = None,
    desktop_options: DesktopOptions | None = None,
) -> ActionExecutionResult:
    if not action.safe_to_apply:
        return ActionExecutionResult(executed=False, outcome="skipped", reason="Action is not marked safe.")

    if action.action_type == "wait":
        time.sleep(max(wait_seconds, 0.0))
        return ActionExecutionResult(executed=True, outcome="executed", reason="Waited for the next stable screen.")

    context = WorkflowContext(workflow_name="mobile-game-learner", variables={})

    control_plan = resolve_control_plan(control_mode=control_mode)
    resolved_mode = ExecutionMode.from_value(control_plan.execution_mode)
    resolved_target = desktop_target or resolve_desktop_target()
    resolved_options = desktop_options or resolve_desktop_options()

    if action.action_type == "tap":
        target = action.target or {}
        x = target.get("x")
        y = target.get("y")
        if x is None or y is None:
            return ActionExecutionResult(executed=False, outcome="failed", reason="Tap target coordinates are missing.")
        if control_plan.control_backend == "desktop" and resolved_mode == ExecutionMode.DESKTOP:
            reference_width = int(target.get("reference_width", 1080) or 1080)
            reference_height = int(target.get("reference_height", 1920) or 1920)
            window = focus_bluestacks_window(target=resolved_target, options=resolved_options)
            scaled_x = round((int(x) / max(reference_width, 1)) * max(window.client_width, 1))
            scaled_y = round((int(y) / max(reference_height, 1)) * max(window.client_height, 1))
            click_bluestacks_relative(scaled_x, scaled_y, target=resolved_target, options=resolved_options)
            return ActionExecutionResult(
                executed=True,
                outcome="executed",
                reason=f"Clicked BlueStacks window at scaled relative coordinates ({scaled_x}, {scaled_y}).",
            )
        run_powershell_script("tap.ps1", {"X": x, "Y": y}, context)
        return ActionExecutionResult(executed=True, outcome="executed", reason="Tapped explicit screen coordinates.")

    if action.action_type == "text_match_tap":
        if control_plan.control_backend == "desktop" and resolved_mode == ExecutionMode.DESKTOP:
            return ActionExecutionResult(
                executed=False,
                outcome="failed",
                reason="Desktop mode cannot resolve label-based taps without a UI dump.",
            )
        ui_dump = _load_ui_dump(analysis)
        if not ui_dump:
            return ActionExecutionResult(executed=False, outcome="failed", reason="UI dump is unavailable for label-based tap.")
        labels = []
        if action.target and isinstance(action.target.get("labels"), list):
            labels = [str(value) for value in action.target["labels"]]
        node = ui_dump.find_first_node(labels)
        if not node or not node.bounds:
            return ActionExecutionResult(executed=False, outcome="failed", reason="No tappable node matched the configured labels.")
        x, y = node.bounds.center
        run_powershell_script("tap.ps1", {"X": x, "Y": y}, context)
        return ActionExecutionResult(executed=True, outcome="executed", reason=f"Tapped UI element matching labels: {', '.join(labels)}")

    if action.action_type == "key_press":
        if control_plan.control_backend != "desktop" or resolved_mode != ExecutionMode.DESKTOP:
            return ActionExecutionResult(
                executed=False,
                outcome="failed",
                reason="Keyboard-driven actions are currently supported only in desktop control backend.",
            )
        target = action.target or {}
        key = target.get("key")
        if not key:
            return ActionExecutionResult(executed=False, outcome="failed", reason="Keyboard action is missing a key.")
        send_bluestacks_key(
            str(key),
            repeat_count=int(target.get("repeat_count", 1) or 1),
            delay_ms=int(target.get("repeat_delay_ms", 120) or 120),
            target=resolved_target,
            options=resolved_options,
        )
        return ActionExecutionResult(
            executed=True,
            outcome="executed",
            reason=f"Sent keyboard action `{key}` to the BlueStacks window.",
        )

    return ActionExecutionResult(executed=False, outcome="failed", reason=f"Unsupported safe action type `{action.action_type}`.")


def run_learning_cycle(
    *,
    profile_id: str = "generic",
    ui_dump_path: str | None = None,
    screenshot_path: str | None = None,
    package_name: str | None = None,
    ui_text: str | None = None,
    profile_path: str | Path | None = None,
    memory_path: str | Path | None = None,
    game_memory_dir: str | Path | None = None,
    use_ocr: bool = False,
    connect: bool = False,
    capture: bool = False,
    capture_screenshot: bool = False,
    control_mode: str = "adb",
    desktop_target: DesktopTarget | None = None,
    desktop_options: DesktopOptions | None = None,
    policy: RuntimePolicy | None = None,
    cycle_history: list[CycleSnapshot] | None = None,
    cycle_index: int | None = None,
    execute_safe_actions: bool = False,
) -> LearnerResult:
    profile: GameProfile = load_game_profile(profile_id=profile_id, path=profile_path)
    resolved_policy = policy or RuntimePolicy()
    history = list(cycle_history or [])
    resolved_target = desktop_target or resolve_desktop_target()
    resolved_options = desktop_options or resolve_desktop_options()

    if capture:
        analysis = capture_current_screen(
            connect=connect,
            artifacts_dir=ARTIFACTS_DIR,
            capture_screenshot=capture_screenshot,
            use_ocr=use_ocr,
            control_mode=control_mode,
            package_name_hint=package_name or profile.package_name,
            desktop_target=resolved_target,
            desktop_options=resolved_options,
        )
    else:
        analysis = analyze_screen(
            screenshot_path=screenshot_path,
            ui_dump_path=ui_dump_path,
            package_name=package_name or profile.package_name,
            use_ocr=use_ocr,
        )

    package_hint = analysis.package_name or package_name or profile.package_name
    resolved_game_memory_dir = Path(game_memory_dir) if game_memory_dir else DEFAULT_GAME_MEMORY_DIR
    game_memory = load_game_memory(package_hint, resolved_game_memory_dir)

    state: GameStateResult = classify_game_state(
        analysis=analysis,
        state_hints=_merge_state_hints(profile, game_memory),
        ui_text=ui_text,
    )

    genre_id, genre_confidence = _resolve_genre(analysis=analysis, state=state, game_memory=game_memory)
    genre_profile: GenreProfile | None = get_genre_profile(genre_id)

    action: ActionSuggestion = choose_action(
        state=state,
        profile=profile,
        genre_profile=genre_profile,
        game_memory=game_memory,
    )

    current_index = cycle_index or (len(history) + 1)
    provisional_snapshot = CycleSnapshot(
        cycle_index=current_index,
        state=state.state,
        action=action.action,
        progressed=False,
        state_confidence=state.confidence,
        action_confidence=action.confidence,
    )
    stagnation_status = evaluate_stagnation(
        history + [provisional_snapshot],
        max_repeated_state_count=resolved_policy.max_repeated_state_count,
        max_repeated_action_count=resolved_policy.max_repeated_action_count,
        max_no_progress_cycles=resolved_policy.max_no_progress_cycles,
        low_confidence_streak_limit=resolved_policy.low_confidence_streak_limit,
        min_state_confidence=resolved_policy.min_state_confidence,
        min_action_confidence=resolved_policy.min_action_confidence,
    )

    decision = evaluate_continuation(
        state=state,
        action_confidence=action.confidence,
        action_safe_to_apply=action.safe_to_apply,
        action_risk_level=action.risk_level,
        visible_text=state.visible_text,
        genre_profile=genre_profile,
        game_memory=game_memory,
        stagnation_status=stagnation_status,
        policy=resolved_policy,
        unknown_streak=_count_unknown_streak(history, state.state),
        low_confidence_streak=_count_low_confidence_streak(
            history,
            current_state_confidence=state.confidence,
            current_action_confidence=action.confidence,
            policy=resolved_policy,
        ),
        cycle_index=current_index,
    )

    execution = ActionExecutionResult(executed=False, outcome="skipped", reason="Autonomous execution was not requested.")
    post_action_state: GameStateResult | None = None
    final_decision = decision
    if execute_safe_actions and decision.should_continue:
        execution = execute_action(
            action=action,
            analysis=analysis,
            control_mode=control_mode,
            desktop_target=resolved_target,
            desktop_options=resolved_options,
        )
        if execution.executed and capture:
            post_analysis = capture_current_screen(
                connect=False,
                artifacts_dir=ARTIFACTS_DIR,
                capture_screenshot=capture_screenshot,
                use_ocr=use_ocr,
                control_mode=control_mode,
                package_name_hint=package_hint,
                desktop_target=resolved_target,
                desktop_options=resolved_options,
            )
            post_action_state = classify_game_state(
                analysis=post_analysis,
                state_hints=_merge_state_hints(profile, game_memory),
                ui_text=ui_text,
            )
            if post_action_state.state == state.state:
                final_decision = ContinuationDecision(
                    should_continue=False,
                    decision="stop",
                    reason="The action did not move the learner out of the current state.",
                    stop_reason="no_progress_detected",
                    continue_reason=action.continue_reason or "no_progress_detected",
                )
            elif evaluate_continuation(
                state=post_action_state,
                action_confidence=action.confidence,
                action_safe_to_apply=action.safe_to_apply,
                action_risk_level=action.risk_level,
                visible_text=post_action_state.visible_text,
                genre_profile=genre_profile,
                game_memory=game_memory,
                stagnation_status=None,
                policy=resolved_policy,
                unknown_streak=0,
                low_confidence_streak=0,
                cycle_index=current_index,
            ).stop_reason == "security_boundary_detected":
                final_decision = ContinuationDecision(
                    should_continue=False,
                    decision="stop",
                    reason="Post-action screen crossed a security boundary.",
                    stop_reason="security_boundary_detected",
                    continue_reason=action.continue_reason or "security_boundary_detected",
                )

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
    action_outcome = "skipped"
    next_state = post_action_state.state if post_action_state else None
    if execution.executed:
        action_outcome = "success" if next_state and next_state != state.state else "failed"
    elif execution.outcome == "failed":
        action_outcome = "failed"

    memory_entry: WorkflowMemoryEntry = build_memory_entry(
        timestamp=timestamp,
        profile=profile,
        state=state,
        action=action,
        decision=final_decision.decision,
        decision_reason=final_decision.reason,
        continue_reason=final_decision.continue_reason,
        stop_reason=final_decision.stop_reason,
        executed=execution.executed,
        execution_outcome=action_outcome,
        cycle_index=current_index,
        next_state=next_state,
        artifact_paths=artifact_paths,
    )
    resolved_memory_path = append_memory_entry(memory_path or DEFAULT_MEMORY_PATH, memory_entry)

    game_memory_path: Path | None = None
    if package_hint:
        updated_game_memory = update_game_memory(
            game_memory,
            timestamp=timestamp,
            package_name=package_hint,
            inferred_genre=genre_id,
            genre_confidence=genre_confidence,
            state=state.state,
            matched_hints=state.matched_hints,
            action=action.action,
            action_outcome=action_outcome,
            state_confidence=state.confidence,
            action_confidence=action.confidence,
            selected_profile_id=action.selected_profile_id,
            selected_control_style=action.selected_control_style,
            continue_reason=final_decision.continue_reason,
            stop_reason=final_decision.stop_reason,
            next_state=next_state,
        )
        game_memory_path = save_game_memory(resolved_game_memory_dir, updated_game_memory)

    return LearnerResult(
        profile=profile.to_dict(),
        selected_profile_id=action.selected_profile_id,
        genre=genre_profile.to_dict() if genre_profile else None,
        screen=analysis.to_dict(),
        state=state.to_dict(),
        action=action.to_dict(),
        decision=final_decision.to_dict(),
        execution=execution.to_dict(),
        post_action_state=post_action_state.to_dict() if post_action_state else None,
        memory_entry=memory_entry.to_dict(),
        memory_path=str(resolved_memory_path.resolve()),
        game_memory_path=str(game_memory_path.resolve()) if game_memory_path else None,
        cycle_index=current_index,
    )

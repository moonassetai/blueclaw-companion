from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .continuation_rules import RuntimePolicy
from .execution_mode import DesktopOptions, DesktopTarget, resolve_desktop_options, resolve_desktop_target
from .mobile_game_learner import DEFAULT_GAME_MEMORY_DIR, DEFAULT_MEMORY_PATH, LearnerResult, run_learning_cycle
from .stagnation_detector import CycleSnapshot


@dataclass(frozen=True)
class LearningLoopResult:
    cycles: list[dict[str, Any]]
    cycle_count: int
    last_stop_reason: str | None
    memory_path: str
    game_memory_dir: str
    policy: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_learning_loop(
    *,
    profile_id: str = "generic",
    profile_path: str | Path | None = None,
    memory_path: str | Path | None = None,
    game_memory_dir: str | Path | None = None,
    ui_dump_path: str | None = None,
    screenshot_path: str | None = None,
    package_name: str | None = None,
    ui_text: str | None = None,
    use_ocr: bool = False,
    connect: bool = False,
    capture: bool = True,
    capture_screenshot: bool = False,
    control_mode: str = "adb",
    desktop_target: DesktopTarget | None = None,
    desktop_options: DesktopOptions | None = None,
    execute_safe_actions: bool = True,
    policy: RuntimePolicy | None = None,
) -> LearningLoopResult:
    resolved_policy = policy or RuntimePolicy()
    resolved_memory_path = Path(memory_path) if memory_path else DEFAULT_MEMORY_PATH
    resolved_game_memory_dir = Path(game_memory_dir) if game_memory_dir else DEFAULT_GAME_MEMORY_DIR
    resolved_target = desktop_target or resolve_desktop_target()
    resolved_options = desktop_options or resolve_desktop_options()

    cycle_results: list[LearnerResult] = []
    history: list[CycleSnapshot] = []
    last_stop_reason: str | None = None

    for cycle_index in range(1, resolved_policy.max_auto_cycles + 1):
        result = run_learning_cycle(
            profile_id=profile_id,
            ui_dump_path=ui_dump_path,
            screenshot_path=screenshot_path,
            package_name=package_name,
            ui_text=ui_text,
            profile_path=profile_path,
            memory_path=resolved_memory_path,
            game_memory_dir=resolved_game_memory_dir,
            use_ocr=use_ocr,
            connect=connect and cycle_index == 1,
            capture=capture,
            capture_screenshot=capture_screenshot,
            control_mode=control_mode,
            desktop_target=resolved_target,
            desktop_options=resolved_options,
            policy=resolved_policy,
            cycle_history=history,
            cycle_index=cycle_index,
            execute_safe_actions=execute_safe_actions,
        )
        cycle_results.append(result)
        history.append(result.to_snapshot())
        if not result.decision["should_continue"]:
            last_stop_reason = str(result.decision["stop_reason"])
            break
    else:
        last_stop_reason = "max_cycles_reached"

    return LearningLoopResult(
        cycles=[result.to_dict() for result in cycle_results],
        cycle_count=len(cycle_results),
        last_stop_reason=last_stop_reason,
        memory_path=str(resolved_memory_path.resolve()),
        game_memory_dir=str(resolved_game_memory_dir.resolve()),
        policy=resolved_policy.to_dict(),
    )

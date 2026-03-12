from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CycleSnapshot:
    cycle_index: int
    state: str
    action: str
    progressed: bool
    state_confidence: float
    action_confidence: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StagnationStatus:
    repeated_state_count: int
    repeated_action_count: int
    no_progress_streak: int
    low_confidence_streak: int
    triggered_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_stagnation(
    history: list[CycleSnapshot],
    *,
    max_repeated_state_count: int,
    max_repeated_action_count: int,
    max_no_progress_cycles: int,
    low_confidence_streak_limit: int,
    min_state_confidence: float,
    min_action_confidence: float,
) -> StagnationStatus:
    if not history:
        return StagnationStatus(
            repeated_state_count=0,
            repeated_action_count=0,
            no_progress_streak=0,
            low_confidence_streak=0,
            triggered_reason=None,
        )

    latest = history[-1]

    repeated_state_count = 0
    for entry in reversed(history):
        if entry.state != latest.state:
            break
        repeated_state_count += 1

    repeated_action_count = 0
    for entry in reversed(history):
        if entry.action != latest.action:
            break
        repeated_action_count += 1

    no_progress_streak = 0
    for entry in reversed(history):
        if entry.progressed:
            break
        no_progress_streak += 1

    low_confidence_streak = 0
    for entry in reversed(history):
        if entry.state_confidence >= min_state_confidence and entry.action_confidence >= min_action_confidence:
            break
        low_confidence_streak += 1

    triggered_reason: str | None = None
    if repeated_state_count >= max_repeated_state_count:
        triggered_reason = "repeated_state_loop"
    elif repeated_action_count >= max_repeated_action_count:
        triggered_reason = "repeated_action_loop"
    elif no_progress_streak >= max_no_progress_cycles:
        triggered_reason = "no_progress_detected"
    elif low_confidence_streak >= low_confidence_streak_limit:
        triggered_reason = "low_action_confidence"

    return StagnationStatus(
        repeated_state_count=repeated_state_count,
        repeated_action_count=repeated_action_count,
        no_progress_streak=no_progress_streak,
        low_confidence_streak=low_confidence_streak,
        triggered_reason=triggered_reason,
    )

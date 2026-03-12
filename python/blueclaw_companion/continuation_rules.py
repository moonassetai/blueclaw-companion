from __future__ import annotations

from dataclasses import asdict, dataclass

from .game_memory_store import GameMemory
from .game_state import GameStateResult
from .game_type import GenreProfile
from .stagnation_detector import StagnationStatus
from .ui_dump_parser import normalize_text


SECURITY_BOUNDARY_LABELS = (
    "account",
    "bind",
    "confirm purchase",
    "delete",
    "email",
    "identity",
    "link",
    "login with",
    "password",
    "payment",
    "purchase",
    "security",
    "sign",
    "signature",
    "wallet",
    "2fa",
)


@dataclass(frozen=True)
class RuntimePolicy:
    max_auto_cycles: int = 12
    max_repeated_state_count: int = 3
    max_repeated_action_count: int = 3
    max_no_progress_cycles: int = 2
    min_state_confidence: float = 0.7
    min_action_confidence: float = 0.65
    stop_on_risky_action: bool = True
    stop_on_unknown_streak: bool = True
    unknown_streak_limit: int = 2
    low_confidence_streak_limit: int = 2

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ContinuationDecision:
    should_continue: bool
    decision: str
    reason: str
    stop_reason: str | None
    continue_reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_security_boundary(visible_text: list[str]) -> bool:
    normalized_text = " ".join(normalize_text(value) for value in visible_text if value)
    if not normalized_text:
        return False
    return any(normalize_text(label) in normalized_text for label in SECURITY_BOUNDARY_LABELS)


def _state_is_in_known_loop(
    state: str,
    genre_profile: GenreProfile | None,
    game_memory: GameMemory | None,
) -> bool:
    if genre_profile and state in genre_profile.common_ui_states:
        return True
    if game_memory and game_memory.observed_states.get(state, 0) > 1:
        return True
    if game_memory and any(loop.startswith(f"{state}->") or loop.endswith(f"->{state}") for loop in game_memory.known_progression_loops):
        return True
    return state in {"loading", "login", "tutorial"}


def evaluate_continuation(
    *,
    state: GameStateResult,
    action_confidence: float,
    action_safe_to_apply: bool,
    action_risk_level: str,
    visible_text: list[str],
    genre_profile: GenreProfile | None,
    game_memory: GameMemory | None,
    stagnation_status: StagnationStatus | None,
    policy: RuntimePolicy,
    unknown_streak: int = 0,
    low_confidence_streak: int = 0,
    cycle_index: int = 1,
) -> ContinuationDecision:
    if detect_security_boundary(visible_text):
        return ContinuationDecision(
            should_continue=False,
            decision="stop",
            reason="Detected an account, wallet, payment, or identity boundary.",
            stop_reason="security_boundary_detected",
            continue_reason="security_boundary_detected",
        )

    if cycle_index > policy.max_auto_cycles:
        return ContinuationDecision(
            should_continue=False,
            decision="stop",
            reason="Reached the configured maximum number of autonomous cycles.",
            stop_reason="max_cycles_reached",
            continue_reason="max_cycles_reached",
        )

    if stagnation_status and stagnation_status.triggered_reason:
        return ContinuationDecision(
            should_continue=False,
            decision="stop",
            reason=f"Detected stagnation: {stagnation_status.triggered_reason}.",
            stop_reason=stagnation_status.triggered_reason,
            continue_reason=stagnation_status.triggered_reason,
        )

    if state.state == "unknown" and policy.stop_on_unknown_streak and unknown_streak >= policy.unknown_streak_limit:
        return ContinuationDecision(
            should_continue=False,
            decision="stop",
            reason="The learner stayed in unknown state too long.",
            stop_reason="unknown_state_streak",
            continue_reason="unknown_state_streak",
        )

    if state.confidence < policy.min_state_confidence:
        return ContinuationDecision(
            should_continue=False,
            decision="stop",
            reason="State confidence fell below the autonomous threshold.",
            stop_reason="low_state_confidence",
            continue_reason="low_state_confidence",
        )

    if action_confidence < policy.min_action_confidence or low_confidence_streak >= policy.low_confidence_streak_limit:
        return ContinuationDecision(
            should_continue=False,
            decision="stop",
            reason="Action confidence is too low for autonomous execution.",
            stop_reason="low_action_confidence",
            continue_reason="low_action_confidence",
        )

    if policy.stop_on_risky_action and (not action_safe_to_apply or action_risk_level != "safe"):
        return ContinuationDecision(
            should_continue=False,
            decision="stop",
            reason="The selected action is not classified as safe.",
            stop_reason="risky_action_blocked",
            continue_reason="risky_action_blocked",
        )

    if not _state_is_in_known_loop(state.state, genre_profile, game_memory):
        return ContinuationDecision(
            should_continue=False,
            decision="stop",
            reason="Current state is outside known safe progression loops.",
            stop_reason="unknown_state_streak",
            continue_reason="outside_known_loop",
        )

    return ContinuationDecision(
        should_continue=True,
        decision="continue",
        reason="State and action confidence are high enough for safe autonomous continuation.",
        stop_reason=None,
        continue_reason="safe_high_confidence_progression",
    )

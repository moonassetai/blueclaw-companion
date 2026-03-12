from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .game_memory_store import GameMemory, preferred_action_for_state
from .game_profiles import ActionTarget, GameProfile
from .game_state import GameStateResult
from .game_type import GenreProfile


SAFE_ACTION_TYPES = {"tap", "text_match_tap", "wait", "key_press"}


@dataclass(frozen=True)
class ActionSuggestion:
    action: str
    action_type: str
    confidence: float
    reason: str
    inferred_genre_id: str | None = None
    target: dict[str, object] | None = None
    safe_to_apply: bool = False
    risk_level: str = "unsafe"
    continue_reason: str = ""
    stop_reason_candidates: list[str] | None = None
    selected_profile_id: str = "generic"
    selected_control_style: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _target_payload(target: ActionTarget | None) -> dict[str, object] | None:
    if not target:
        return None
    return target.to_dict()


def _risk_level(action_name: str, target: ActionTarget | None, genre_profile: GenreProfile | None) -> tuple[bool, str]:
    if action_name == "wait":
        return True, "safe"
    if genre_profile and action_name in genre_profile.risky_actions:
        return False, "risky"
    if not target:
        return False, "unsupported"
    return target.type in SAFE_ACTION_TYPES, "safe" if target.type in SAFE_ACTION_TYPES else "unsupported"


def _profile_action(
    action_name: str,
    *,
    profile: GameProfile,
    genre_profile: GenreProfile | None,
    confidence: float,
    reason: str,
    selected_profile_id: str,
) -> ActionSuggestion:
    target = profile.action_targets.get(action_name)
    safe_to_apply, risk_level = _risk_level(action_name, target, genre_profile)
    control_style = genre_profile.control_style if genre_profile else "unknown"
    return ActionSuggestion(
        action=action_name,
        action_type=target.type if target else "memory_fallback",
        confidence=confidence,
        reason=reason,
        inferred_genre_id=genre_profile.genre_id if genre_profile else "unknown",
        target=_target_payload(target),
        safe_to_apply=safe_to_apply,
        risk_level=risk_level,
        continue_reason="known_profile_action" if target else "memory_guided_action",
        stop_reason_candidates=["risky_action_blocked", "low_action_confidence"],
        selected_profile_id=selected_profile_id,
        selected_control_style=control_style,
    )


def choose_action(
    state: GameStateResult,
    profile: GameProfile,
    genre_profile: GenreProfile | None = None,
    game_memory: GameMemory | None = None,
) -> ActionSuggestion:
    genre_id = genre_profile.genre_id if genre_profile else "unknown"
    control_style = genre_profile.control_style if genre_profile else "unknown"

    if state.state == "loading":
        return ActionSuggestion(
            action="wait",
            action_type="wait",
            confidence=0.9,
            reason="Loading-like screens are handled conservatively by waiting for a clearer state.",
            inferred_genre_id=genre_id,
            safe_to_apply=True,
            risk_level="safe",
            continue_reason="loading_wait",
            stop_reason_candidates=["unknown_state_streak"],
            selected_profile_id=profile.profile_id,
            selected_control_style=control_style,
        )

    state_to_action = {
        "login": "login_continue",
        "tutorial": "tutorial_continue",
        "battle": "battle_continue",
        "reward": "reward_claim",
        "menu": "menu_primary",
        "upgrade": "upgrade_confirm",
    }
    preferred_action = state_to_action.get(state.state)
    if preferred_action and preferred_action in profile.action_targets:
        return _profile_action(
            preferred_action,
            profile=profile,
            genre_profile=genre_profile,
            confidence=min(state.confidence, 0.92),
            reason=f"Profile `{profile.profile_id}` defines `{preferred_action}` for state `{state.state}`.",
            selected_profile_id=profile.profile_id,
        )

    memory_action = preferred_action_for_state(game_memory, state.state)
    if memory_action and memory_action in profile.action_targets:
        return _profile_action(
            memory_action,
            profile=profile,
            genre_profile=genre_profile,
            confidence=min(max(state.confidence, 0.72), 0.88),
            reason=f"Per-game memory prefers `{memory_action}` for state `{state.state}` based on prior success.",
            selected_profile_id=f"memory:{game_memory.package_name}" if game_memory else profile.profile_id,
        )

    if state.state == "unknown":
        return ActionSuggestion(
            action="inspect",
            action_type="inspect",
            confidence=0.15,
            reason="The current screen is uncertain. Capture more evidence before mutating the UI.",
            inferred_genre_id=genre_id,
            safe_to_apply=False,
            risk_level="unsafe",
            continue_reason="inspect_unknown_state",
            stop_reason_candidates=["unknown_state_streak", "low_state_confidence"],
            selected_profile_id=profile.profile_id,
            selected_control_style=control_style,
        )

    if genre_profile and genre_profile.safe_repeat_actions:
        fallback_action = genre_profile.safe_repeat_actions[0]
        safe_to_apply = fallback_action not in genre_profile.risky_actions and control_style in {"menu_heavy", "unknown"}
        return ActionSuggestion(
            action=fallback_action,
            action_type="genre_fallback",
            confidence=0.5,
            reason=f"No explicit target. Using genre `{genre_id}` safe repeat action `{fallback_action}`.",
            inferred_genre_id=genre_id,
            safe_to_apply=safe_to_apply,
            risk_level="safe" if safe_to_apply else "unsupported",
            continue_reason="genre_safe_repeat_action",
            stop_reason_candidates=["risky_action_blocked", "low_action_confidence"],
            selected_profile_id=f"genre:{genre_id}",
            selected_control_style=control_style,
        )

    return ActionSuggestion(
        action="wait",
        action_type="wait",
        confidence=0.3,
        reason=f"No profile action is configured for state `{state.state}`. Conservative fallback is to wait.",
        inferred_genre_id=genre_id,
        safe_to_apply=True,
        risk_level="safe",
        continue_reason="fallback_wait",
        stop_reason_candidates=["low_action_confidence"],
        selected_profile_id=profile.profile_id,
        selected_control_style=control_style,
    )

from __future__ import annotations

from dataclasses import asdict, dataclass

from .game_profiles import ActionTarget, GameProfile
from .game_state import GameStateResult


@dataclass(frozen=True)
class ActionSuggestion:
    action: str
    action_type: str
    confidence: float
    reason: str
    target: dict[str, object] | None = None
    safe_to_apply: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _target_payload(target: ActionTarget | None) -> dict[str, object] | None:
    if not target:
        return None
    return target.to_dict()


def choose_action(state: GameStateResult, profile: GameProfile) -> ActionSuggestion:
    targets = profile.action_targets

    if state.state == "loading":
        return ActionSuggestion(
            action="wait",
            action_type="wait",
            confidence=0.9,
            reason="Loading-like screens are handled conservatively by waiting for a clearer state.",
            safe_to_apply=True,
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
    target = targets.get(preferred_action) if preferred_action else None

    if target:
        return ActionSuggestion(
            action=preferred_action,
            action_type=target.type,
            confidence=min(state.confidence, 0.9),
            reason=f"Profile `{profile.profile_id}` defines `{preferred_action}` for state `{state.state}`.",
            target=_target_payload(target),
            safe_to_apply=target.type in {"tap", "text_match_tap"},
        )

    if state.state == "unknown":
        return ActionSuggestion(
            action="inspect",
            action_type="inspect",
            confidence=0.15,
            reason="The current screen is uncertain. Capture more evidence before mutating the UI.",
            safe_to_apply=False,
        )

    return ActionSuggestion(
        action="wait",
        action_type="wait",
        confidence=0.3,
        reason=f"No profile action is configured for state `{state.state}`. Conservative fallback is to wait.",
        safe_to_apply=True,
    )

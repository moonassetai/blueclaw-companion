import unittest

from blueclaw_companion.continuation_rules import RuntimePolicy, evaluate_continuation
from blueclaw_companion.game_state import GameStateResult
from blueclaw_companion.genre_profiles import GENRE_PROFILE_REGISTRY
from blueclaw_companion.stagnation_detector import StagnationStatus


class ContinuationRulesTests(unittest.TestCase):
    def test_stops_on_low_action_confidence(self) -> None:
        state = GameStateResult(
            state="reward",
            confidence=0.9,
            reasons=[],
            matched_hints=["Reward"],
            package_name="com.example.game",
            visible_text=["Reward", "Claim"],
        )
        decision = evaluate_continuation(
            state=state,
            action_confidence=0.2,
            action_safe_to_apply=True,
            action_risk_level="safe",
            visible_text=state.visible_text,
            genre_profile=GENRE_PROFILE_REGISTRY["idle_rpg"],
            game_memory=None,
            stagnation_status=StagnationStatus(0, 0, 0, 0, None),
            policy=RuntimePolicy(),
            unknown_streak=0,
            low_confidence_streak=1,
            cycle_index=1,
        )

        self.assertFalse(decision.should_continue)
        self.assertEqual(decision.stop_reason, "low_action_confidence")

    def test_stops_on_security_boundary(self) -> None:
        state = GameStateResult(
            state="menu",
            confidence=0.9,
            reasons=[],
            matched_hints=["Account"],
            package_name="com.example.game",
            visible_text=["Account", "Link Wallet"],
        )
        decision = evaluate_continuation(
            state=state,
            action_confidence=0.8,
            action_safe_to_apply=True,
            action_risk_level="safe",
            visible_text=state.visible_text,
            genre_profile=GENRE_PROFILE_REGISTRY["idle_rpg"],
            game_memory=None,
            stagnation_status=StagnationStatus(0, 0, 0, 0, None),
            policy=RuntimePolicy(),
            unknown_streak=0,
            low_confidence_streak=0,
            cycle_index=1,
        )

        self.assertFalse(decision.should_continue)
        self.assertEqual(decision.stop_reason, "security_boundary_detected")


if __name__ == "__main__":
    unittest.main()

import unittest

from blueclaw_companion.stagnation_detector import CycleSnapshot, evaluate_stagnation


class StagnationDetectorTests(unittest.TestCase):
    def test_detects_repeated_state_loop(self) -> None:
        history = [
            CycleSnapshot(1, "reward", "reward_claim", False, 0.9, 0.9),
            CycleSnapshot(2, "reward", "reward_claim", False, 0.88, 0.87),
            CycleSnapshot(3, "reward", "reward_claim", False, 0.86, 0.86),
        ]

        status = evaluate_stagnation(
            history,
            max_repeated_state_count=3,
            max_repeated_action_count=4,
            max_no_progress_cycles=4,
            low_confidence_streak_limit=3,
            min_state_confidence=0.7,
            min_action_confidence=0.65,
        )

        self.assertEqual(status.triggered_reason, "repeated_state_loop")

    def test_detects_no_progress(self) -> None:
        history = [
            CycleSnapshot(1, "menu", "menu_primary", False, 0.9, 0.9),
            CycleSnapshot(2, "menu", "menu_primary", False, 0.9, 0.9),
        ]

        status = evaluate_stagnation(
            history,
            max_repeated_state_count=5,
            max_repeated_action_count=5,
            max_no_progress_cycles=2,
            low_confidence_streak_limit=3,
            min_state_confidence=0.7,
            min_action_confidence=0.65,
        )

        self.assertEqual(status.triggered_reason, "no_progress_detected")

    def test_detects_state_oscillation_loop(self) -> None:
        history = [
            CycleSnapshot(1, "menu", "menu_primary", False, 0.9, 0.8),
            CycleSnapshot(2, "battle", "battle_continue", False, 0.9, 0.8),
            CycleSnapshot(3, "menu", "menu_primary", False, 0.9, 0.8),
            CycleSnapshot(4, "battle", "battle_continue", False, 0.9, 0.8),
        ]

        status = evaluate_stagnation(
            history,
            max_repeated_state_count=5,
            max_repeated_action_count=5,
            max_no_progress_cycles=10,
            low_confidence_streak_limit=5,
            min_state_confidence=0.7,
            min_action_confidence=0.65,
        )

        self.assertEqual(status.triggered_reason, "oscillation_loop")


if __name__ == "__main__":
    unittest.main()

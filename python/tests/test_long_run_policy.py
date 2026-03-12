import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from blueclaw_companion.continuation_rules import RuntimePolicy
from blueclaw_companion.long_run_policy import run_learning_loop


class LongRunPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        base_root = Path(__file__).resolve().parents[2] / ".tmp-tests"
        base_root.mkdir(parents=True, exist_ok=True)
        self.temp_root = base_root / f"blueclaw-loop-{uuid.uuid4().hex}"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for path in sorted(self.temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.temp_root.rmdir()

    def test_loop_stops_on_reported_reason(self) -> None:
        result_one = type(
            "LoopCycleResult",
            (),
            {
                "decision": {"should_continue": True, "stop_reason": None},
                "to_snapshot": lambda self: None,
                "to_dict": lambda self: {"decision": {"should_continue": True, "stop_reason": None}},
            },
        )()
        result_two = type(
            "LoopCycleResult",
            (),
            {
                "decision": {"should_continue": False, "stop_reason": "unknown_state_streak"},
                "to_snapshot": lambda self: None,
                "to_dict": lambda self: {"decision": {"should_continue": False, "stop_reason": "unknown_state_streak"}},
            },
        )()
        results = [
            result_one,
            result_two,
        ]
        with patch("blueclaw_companion.long_run_policy.run_learning_cycle", side_effect=results):
            result = run_learning_loop(
                memory_path=self.temp_root / "memory.jsonl",
                game_memory_dir=self.temp_root / "games",
                capture=False,
                execute_safe_actions=False,
                policy=RuntimePolicy(max_auto_cycles=4),
            )

        self.assertEqual(result.cycle_count, 2)
        self.assertEqual(result.last_stop_reason, "unknown_state_streak")


if __name__ == "__main__":
    unittest.main()

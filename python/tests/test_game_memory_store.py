import unittest
import uuid
from pathlib import Path

from blueclaw_companion.game_memory_store import (
    GameMemory,
    load_game_memory,
    preferred_action_for_state,
    save_game_memory,
    update_game_memory,
)


class GameMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        base_root = Path(__file__).resolve().parents[2] / ".tmp-tests"
        base_root.mkdir(parents=True, exist_ok=True)
        self.temp_root = base_root / f"blueclaw-memory-{uuid.uuid4().hex}"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for path in sorted(self.temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.temp_root.rmdir()

    def test_update_and_prefer_successful_action(self) -> None:
        memory = GameMemory(package_name="com.example.game")
        memory = update_game_memory(
            memory,
            timestamp="2026-03-12T10:00:00+0900",
            package_name="com.example.game",
            inferred_genre="idle_rpg",
            genre_confidence=0.8,
            state="reward",
            matched_hints=["Claim"],
            action="reward_claim",
            action_outcome="success",
            state_confidence=0.82,
            action_confidence=0.88,
            selected_profile_id="generic",
            selected_control_style="menu_heavy",
            continue_reason="safe_high_confidence_progression",
            next_state="menu",
        )
        memory = update_game_memory(
            memory,
            timestamp="2026-03-12T10:01:00+0900",
            package_name="com.example.game",
            inferred_genre="idle_rpg",
            genre_confidence=0.84,
            state="reward",
            matched_hints=["Collect"],
            action="reward_claim",
            action_outcome="success",
            state_confidence=0.85,
            action_confidence=0.89,
            selected_profile_id="generic",
            selected_control_style="menu_heavy",
            continue_reason="safe_high_confidence_progression",
            next_state="menu",
        )

        save_game_memory(self.temp_root, memory)
        loaded = load_game_memory("com.example.game", self.temp_root)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(preferred_action_for_state(loaded, "reward"), "reward_claim")
        self.assertIn("reward->menu", loaded.known_progression_loops)


if __name__ == "__main__":
    unittest.main()

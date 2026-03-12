import json
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from blueclaw_companion.game_memory_store import game_memory_path
from blueclaw_companion.mobile_game_learner import run_learning_cycle
from blueclaw_companion.screen_analysis import analyze_screen


LOGIN_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" class="android.widget.FrameLayout" package="com.example.game" content-desc="" bounds="[0,0][1080,1920]">
    <node index="1" text="Guest Login" class="android.widget.Button" package="com.example.game" clickable="true" content-desc="" bounds="[100,1200][900,1320]"/>
    <node index="2" text="Start Game" class="android.widget.Button" package="com.example.game" clickable="true" content-desc="" bounds="[100,1400][900,1520]"/>
  </node>
</hierarchy>
"""


REWARD_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" class="android.widget.FrameLayout" package="com.example.game" content-desc="" bounds="[0,0][1080,1920]">
    <node index="1" text="Reward" class="android.widget.TextView" package="com.example.game" content-desc="" bounds="[80,200][400,320]"/>
    <node index="2" text="Claim" class="android.widget.Button" package="com.example.game" clickable="true" content-desc="" bounds="[700,1500][980,1600]"/>
  </node>
</hierarchy>
"""


SECURITY_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" class="android.widget.FrameLayout" package="com.example.game" content-desc="" bounds="[0,0][1080,1920]">
    <node index="1" text="Account" class="android.widget.TextView" package="com.example.game" content-desc="" bounds="[80,200][400,320]"/>
    <node index="2" text="Link Wallet" class="android.widget.Button" package="com.example.game" clickable="true" content-desc="" bounds="[700,1500][980,1600]"/>
  </node>
</hierarchy>
"""


class MobileGameLearnerTests(unittest.TestCase):
    def setUp(self) -> None:
        base_root = Path(__file__).resolve().parents[2] / ".tmp-tests"
        base_root.mkdir(parents=True, exist_ok=True)
        self.temp_root = base_root / f"blueclaw-learner-{uuid.uuid4().hex}"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.memory_path = self.temp_root / "workflow-memory.jsonl"
        self.game_memory_dir = self.temp_root / "games"
        self.addCleanup(self._cleanup_temp_root)

    def _cleanup_temp_root(self) -> None:
        if not self.temp_root.exists():
            return
        for path in sorted(self.temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.temp_root.rmdir()

    def write_temp_xml(self, content: str) -> Path:
        path = self.temp_root / f"{uuid.uuid4().hex}.xml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_login_state_prefers_profile_action(self) -> None:
        xml_path = self.write_temp_xml(LOGIN_XML)
        result = run_learning_cycle(
            profile_id="generic",
            ui_dump_path=str(xml_path),
            package_name="com.example.game",
            memory_path=self.memory_path,
            game_memory_dir=self.game_memory_dir,
        )

        self.assertEqual(result.state["state"], "login")
        self.assertEqual(result.action["action"], "login_continue")
        self.assertEqual(result.decision["decision"], "continue")
        self.assertTrue(self.memory_path.exists())
        self.assertTrue(Path(result.game_memory_path).exists())

    def test_reward_state_logs_memory_entry_and_game_memory(self) -> None:
        xml_path = self.write_temp_xml(REWARD_XML)
        result = run_learning_cycle(
            profile_id="generic",
            ui_dump_path=str(xml_path),
            package_name="com.example.game",
            memory_path=self.memory_path,
            game_memory_dir=self.game_memory_dir,
        )

        self.assertEqual(result.state["state"], "reward")
        lines = self.memory_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["action"], "reward_claim")
        game_memory = json.loads(game_memory_path(self.game_memory_dir, "com.example.game").read_text(encoding="utf-8"))
        self.assertEqual(game_memory["observed_states"]["reward"], 1)

    def test_security_boundary_forces_stop(self) -> None:
        xml_path = self.write_temp_xml(SECURITY_XML)
        result = run_learning_cycle(
            profile_id="generic",
            ui_dump_path=str(xml_path),
            package_name="com.example.game",
            memory_path=self.memory_path,
            game_memory_dir=self.game_memory_dir,
        )

        self.assertEqual(result.decision["decision"], "stop")
        self.assertEqual(result.decision["stop_reason"], "security_boundary_detected")

    def test_execute_safe_action_stops_on_no_progress(self) -> None:
        xml_path = self.write_temp_xml(LOGIN_XML)
        analysis = analyze_screen(ui_dump_path=str(xml_path), package_name="com.example.game")
        with patch("blueclaw_companion.mobile_game_learner.capture_current_screen", side_effect=[analysis, analysis]):
            with patch("blueclaw_companion.mobile_game_learner.execute_action") as execute_action:
                execute_action.return_value = type(
                    "ExecResult",
                    (),
                    {"executed": True, "outcome": "executed", "reason": "mock", "to_dict": lambda self: {"executed": True, "outcome": "executed", "reason": "mock"}},
                )()
                result = run_learning_cycle(
                    profile_id="generic",
                    package_name="com.example.game",
                    memory_path=self.memory_path,
                    game_memory_dir=self.game_memory_dir,
                    capture=True,
                    execute_safe_actions=True,
                )

        self.assertEqual(result.execution["executed"], True)
        self.assertEqual(result.decision["stop_reason"], "no_progress_detected")


if __name__ == "__main__":
    unittest.main()

import json
import unittest
import uuid
from pathlib import Path

from blueclaw_companion.mobile_game_learner import run_learning_cycle


LOGIN_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" class="android.widget.FrameLayout" package="com.example.game" content-desc="" bounds="[0,0][1080,1920]">
    <node index="1" text="Guest Login" class="android.widget.Button" package="com.example.game" content-desc="" bounds="[100,1200][900,1320]"/>
    <node index="2" text="Start Game" class="android.widget.Button" package="com.example.game" content-desc="" bounds="[100,1400][900,1520]"/>
  </node>
</hierarchy>
"""


REWARD_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" class="android.widget.FrameLayout" package="com.example.game" content-desc="" bounds="[0,0][1080,1920]">
    <node index="1" text="Reward" class="android.widget.TextView" package="com.example.game" content-desc="" bounds="[80,200][400,320]"/>
    <node index="2" text="Claim" class="android.widget.Button" package="com.example.game" content-desc="" bounds="[700,1500][980,1600]"/>
  </node>
</hierarchy>
"""


class MobileGameLearnerTests(unittest.TestCase):
    def write_temp_memory_path(self) -> Path:
        temp_root = Path(__file__).resolve().parents[2] / "artifacts" / "test-temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        path = temp_root / f"{uuid.uuid4().hex}.jsonl"
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def write_temp_xml(self, content: str) -> Path:
        temp_root = Path(__file__).resolve().parents[2] / "artifacts" / "test-temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        path = temp_root / f"{uuid.uuid4().hex}.xml"
        path.write_text(content, encoding="utf-8")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_login_state_prefers_profile_action(self) -> None:
        xml_path = self.write_temp_xml(LOGIN_XML)
        memory_path = self.write_temp_memory_path()
        result = run_learning_cycle(
            profile_id="generic",
            ui_dump_path=str(xml_path),
            package_name="com.example.game",
            memory_path=memory_path,
        )

        self.assertEqual(result.state["state"], "login")
        self.assertEqual(result.action["action"], "login_continue")
        self.assertTrue(memory_path.exists())

    def test_reward_state_logs_memory_entry(self) -> None:
        xml_path = self.write_temp_xml(REWARD_XML)
        memory_path = self.write_temp_memory_path()
        result = run_learning_cycle(
            profile_id="generic",
            ui_dump_path=str(xml_path),
            package_name="com.example.game",
            memory_path=memory_path,
        )

        self.assertEqual(result.state["state"], "reward")
        lines = memory_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["action"], "reward_claim")


if __name__ == "__main__":
    unittest.main()

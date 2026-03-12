import unittest
import uuid
from pathlib import Path

from blueclaw_companion.screen_analysis import analyze_screen
from blueclaw_companion.ui_dump_parser import load_ui_dump


PLAYSTORE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.android.vending" content-desc="" bounds="[0,0][1080,1920]">
    <node index="1" text="Google Play" resource-id="" class="android.widget.TextView" package="com.android.vending" content-desc="" bounds="[24,48][400,120]"/>
    <node index="2" text="Install" resource-id="" class="android.widget.Button" package="com.android.vending" content-desc="" bounds="[700,1500][980,1600]"/>
  </node>
</hierarchy>
"""


METAMASK_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="io.metamask" content-desc="" bounds="[0,0][1080,1920]">
    <node index="1" text="Get started" resource-id="" class="android.widget.Button" package="io.metamask" content-desc="" bounds="[100,1200][900,1320]"/>
    <node index="2" text="Import an existing wallet" resource-id="" class="android.widget.Button" package="io.metamask" content-desc="" bounds="[100,1400][900,1520]"/>
  </node>
</hierarchy>
"""


class ScreenAnalysisTests(unittest.TestCase):
    def write_temp_xml(self, content: str) -> Path:
        temp_root = Path(__file__).resolve().parents[2] / "artifacts" / "test-temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        path = temp_root / f"{uuid.uuid4().hex}.xml"
        path.write_text(content, encoding="utf-8")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_ui_dump_extracts_visible_text(self) -> None:
        path = self.write_temp_xml(PLAYSTORE_XML)
        ui_dump = load_ui_dump(path)
        self.assertIn("Google Play", ui_dump.visible_texts)
        self.assertIn("Install", ui_dump.visible_texts)

    def test_playstore_app_page_classifies_from_xml(self) -> None:
        path = self.write_temp_xml(PLAYSTORE_XML)
        result = analyze_screen(ui_dump_path=str(path), package_name="com.android.vending")
        self.assertEqual(result.state, "playstore_app_page")

    def test_metamask_onboarding_classifies_from_xml(self) -> None:
        path = self.write_temp_xml(METAMASK_XML)
        result = analyze_screen(ui_dump_path=str(path), package_name="io.metamask")
        self.assertEqual(result.state, "metamask_onboarding")


if __name__ == "__main__":
    unittest.main()

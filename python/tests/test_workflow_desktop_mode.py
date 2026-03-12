import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from blueclaw_companion.execution_mode import DesktopOptions, DesktopTarget
from blueclaw_companion.screen_analysis import analyze_screen
from blueclaw_companion.workflow_runner import WorkflowContext, capture_and_classify


class WorkflowDesktopModeTests(unittest.TestCase):
    def setUp(self) -> None:
        base_root = Path(__file__).resolve().parents[2] / ".tmp-tests"
        base_root.mkdir(parents=True, exist_ok=True)
        self.temp_root = base_root / f"blueclaw-workflow-desktop-{uuid.uuid4().hex}"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for path in sorted(self.temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.temp_root.rmdir()

    def test_capture_and_classify_passes_desktop_target_and_options(self) -> None:
        analysis = analyze_screen(package_name="com.example.game")
        capture_result = type("DesktopCapture", (), {"analysis": analysis})()
        target = DesktopTarget(window_handle=321, window_title_contains="BlueStacks")
        options = DesktopOptions(expected_client_width=1280, expected_client_height=720)
        context = WorkflowContext(
            workflow_name="test-workflow",
            variables={},
            execution_mode="desktop",
            desktop_target=target,
            desktop_options=options,
            artifacts_dir=self.temp_root,
        )

        with patch("blueclaw_companion.desktop_state.capture_desktop_state", return_value=capture_result) as capture_desktop_state:
            result = capture_and_classify("capture", {"use_ocr": False, "screenshot": True}, context)

        self.assertEqual(result.package_name, "com.example.game")
        capture_desktop_state.assert_called_once()
        called_kwargs = capture_desktop_state.call_args.kwargs
        self.assertEqual(called_kwargs["desktop_target"], target)
        self.assertEqual(called_kwargs["desktop_options"], options)

    def test_capture_and_classify_degrades_when_ui_dump_is_missing(self) -> None:
        screenshot_path = self.temp_root / "test-workflow-capture-20250101-000000.png"

        def fake_capture(_script_name: str, params: dict[str, object], _context: object) -> object:
            Path(str(params["ScreenshotPath"])).write_bytes(b"fake")
            return type("CaptureResult", (), {"stdout": "Foreground Package: com.example.game"})()

        context = WorkflowContext(
            workflow_name="test-workflow",
            variables={},
            execution_mode="adb",
            artifacts_dir=self.temp_root,
        )

        with patch("blueclaw_companion.workflow_runner.run_powershell_script", side_effect=fake_capture):
            with patch("blueclaw_companion.workflow_runner.time.strftime", return_value="20250101-000000"):
                result = capture_and_classify("capture", {"use_ocr": False, "screenshot": False}, context)

        self.assertEqual(Path(result.screenshot_path).resolve(), screenshot_path.resolve())
        self.assertIsNone(result.ui_dump_path)
        self.assertIsNone(context.last_ui_dump)


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

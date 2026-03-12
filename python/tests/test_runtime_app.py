import unittest
from unittest.mock import patch

from blueclaw_companion.execution_mode import DesktopOptions, DesktopTarget, ExecutionMode
from blueclaw_companion.runtime_app import inspect_runtime, resolve_effective_mode
from blueclaw_companion.window_control import WindowMetadata


class _FakeLearnerResult:
    def __init__(self, state: str) -> None:
        self.screen = {"state": state}
        self.state = {"state": state, "confidence": 0.8}
        self.action = {"action": "wait", "action_type": "wait"}
        self.decision = {"decision": "continue"}
        self.memory_path = "memory.jsonl"


class RuntimeAppTests(unittest.TestCase):
    def _window(self) -> WindowMetadata:
        return WindowMetadata(
            handle=100,
            process_id=1,
            process_name="HD-Player",
            title="BlueStacks App Player",
            window_left=0,
            window_top=0,
            window_width=1280,
            window_height=720,
            client_left=0,
            client_top=0,
            client_width=1280,
            client_height=720,
            is_minimized=False,
            is_foreground=True,
        )

    def test_hybrid_prefers_desktop_when_window_found(self) -> None:
        mode = resolve_effective_mode(ExecutionMode.HYBRID, bluestacks_found=True)
        self.assertEqual(mode, ExecutionMode.DESKTOP)

    def test_hybrid_falls_back_to_adb_when_window_missing(self) -> None:
        mode = resolve_effective_mode(ExecutionMode.HYBRID, bluestacks_found=False)
        self.assertEqual(mode, ExecutionMode.ADB)

    def test_non_hybrid_mode_is_preserved(self) -> None:
        mode = resolve_effective_mode(ExecutionMode.DESKTOP, bluestacks_found=False)
        self.assertEqual(mode, ExecutionMode.DESKTOP)

    def test_inspect_hybrid_falls_back_to_adb_when_desktop_run_fails(self) -> None:
        target = DesktopTarget(window_handle=100)
        options = DesktopOptions()
        with patch("blueclaw_companion.runtime_app.detect_bluestacks_window", return_value=self._window()):
            with patch(
                "blueclaw_companion.runtime_app.run_learning_cycle",
                side_effect=[RuntimeError("desktop boom"), _FakeLearnerResult("menu")],
            ):
                payload = inspect_runtime(
                    mode="hybrid",
                    profile="generic",
                    use_ocr=False,
                    capture_screenshot=False,
                    connect_adb=False,
                    focus_window=False,
                    device=None,
                    adb_path=None,
                    desktop_target=target,
                    desktop_options=options,
                )
        self.assertEqual(payload["status"]["effective_mode"], "adb")
        self.assertEqual(payload["fallback"]["desktop_error"], "desktop boom")

    def test_inspect_hybrid_reports_clear_error_when_desktop_and_adb_fail(self) -> None:
        target = DesktopTarget(window_handle=100)
        options = DesktopOptions()
        with patch("blueclaw_companion.runtime_app.detect_bluestacks_window", return_value=self._window()):
            with patch(
                "blueclaw_companion.runtime_app.run_learning_cycle",
                side_effect=[RuntimeError("desktop boom"), RuntimeError("adb boom")],
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    inspect_runtime(
                        mode="hybrid",
                        profile="generic",
                        use_ocr=False,
                        capture_screenshot=False,
                        connect_adb=False,
                        focus_window=False,
                        device=None,
                        adb_path=None,
                        desktop_target=target,
                        desktop_options=options,
                    )
        self.assertIn("Desktop error: desktop boom", str(ctx.exception))
        self.assertIn("ADB error: adb boom", str(ctx.exception))

    def test_inspect_pins_window_handle_for_runtime_target(self) -> None:
        target = DesktopTarget(window_title_contains="BlueStacks")
        options = DesktopOptions()
        with patch("blueclaw_companion.runtime_app.detect_bluestacks_window", return_value=self._window()):
            with patch(
                "blueclaw_companion.runtime_app.run_learning_cycle",
                return_value=_FakeLearnerResult("menu"),
            ) as run_learning_cycle:
                payload = inspect_runtime(
                    mode="desktop",
                    profile="generic",
                    use_ocr=False,
                    capture_screenshot=False,
                    connect_adb=False,
                    focus_window=False,
                    device=None,
                    adb_path=None,
                    desktop_target=target,
                    desktop_options=options,
                )
        self.assertEqual(payload["status"]["target"]["window_handle"], 100)
        called_target = run_learning_cycle.call_args.kwargs["desktop_target"]
        self.assertEqual(called_target.window_handle, 100)


if __name__ == "__main__":
    unittest.main()

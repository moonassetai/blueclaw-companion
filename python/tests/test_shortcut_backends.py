import unittest
from unittest.mock import patch

from blueclaw_companion.control_backends import resolve_control_plan
from blueclaw_companion.perception_backends import resolve_perception_plan
from blueclaw_companion.shortcuts import build_shortcut_summary, list_shortcut_capabilities


class ShortcutBackendTests(unittest.TestCase):
    def test_perception_plan_prefers_tesseract_when_available(self) -> None:
        with patch("blueclaw_companion.perception_backends.shutil.which", return_value="C:\\tools\\tesseract.exe"):
            plan = resolve_perception_plan(execution_mode="adb", prefer_ocr=True)
        self.assertEqual(plan.capture_backend, "adb_ui_dump")
        self.assertEqual(plan.ocr_backend, "ocr_tesseract")

    def test_perception_plan_falls_back_without_ocr_binary(self) -> None:
        with patch("blueclaw_companion.perception_backends.shutil.which", return_value=None):
            plan = resolve_perception_plan(execution_mode="desktop", prefer_ocr=True)
        self.assertEqual(plan.capture_backend, "desktop_capture")
        self.assertEqual(plan.ocr_backend, "none")

    def test_control_plan_keeps_desktop_backend(self) -> None:
        with patch("blueclaw_companion.control_backends.shutil.which", return_value=None):
            plan = resolve_control_plan(control_mode="desktop", prefer_scrcpy=True)
        self.assertEqual(plan.control_backend, "desktop")
        self.assertFalse(plan.scrcpy_available)

    def test_shortcut_summary_reports_machine_readable_availability(self) -> None:
        with patch("blueclaw_companion.shortcuts._script_exists", return_value=True):
            with patch(
                "blueclaw_companion.shortcuts.shutil.which",
                side_effect=lambda name: {"adb": "C:\\adb.exe", "scrcpy": None, "tesseract": None}.get(name),
            ):
                with patch(
                    "blueclaw_companion.shortcuts._probe_adb_device_reachability",
                    return_value={
                        "adb_binary_found": True,
                        "adb_device_reachable": True,
                        "adb_selected_device": None,
                        "adb_connected_devices": ["127.0.0.1:5555"],
                        "adb_error": None,
                    },
                ):
                    with patch(
                        "blueclaw_companion.shortcuts._probe_bluestacks_window",
                        return_value={
                            "bluestacks_window_found": True,
                            "bluestacks_window_handle": 100,
                            "bluestacks_window_title": "BlueStacks",
                            "bluestacks_window_error": None,
                        },
                    ):
                        summary = build_shortcut_summary(
                            execution_mode="adb",
                            use_ocr=True,
                            prefer_scrcpy=True,
                            prefer_vision_model=True,
                        )
                        capabilities = list_shortcut_capabilities(use_ocr=True)

        capability_names = {item.name for item in capabilities}
        self.assertIn("adb_ui_dump", capability_names)
        self.assertIn("desktop_capture", capability_names)
        self.assertIn("scrcpy", capability_names)
        self.assertEqual(summary["perception"]["vision_backend"], "vision_model")
        self.assertIn("availability", summary)
        self.assertFalse(summary["availability"]["ocr_tesseract"]["available"])
        self.assertEqual(summary["availability"]["scrcpy"]["status"], "placeholder")
        self.assertEqual(summary["availability"]["adb_control"]["readiness"], "green")
        self.assertIn("runtime_checks", summary)


if __name__ == "__main__":
    unittest.main()

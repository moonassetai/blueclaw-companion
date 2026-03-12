import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from blueclaw_companion.action_policy import ActionSuggestion
from blueclaw_companion.execution_mode import DesktopOptions, DesktopTarget
from blueclaw_companion.mobile_game_learner import execute_action, run_learning_cycle
from blueclaw_companion.screen_analysis import analyze_screen
from blueclaw_companion.window_control import WindowMetadata, click_bluestacks_relative, validate_window_geometry


LOGIN_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" class="android.widget.FrameLayout" package="com.example.game" content-desc="" bounds="[0,0][1080,1920]">
    <node index="1" text="Guest Login" class="android.widget.Button" package="com.example.game" clickable="true" content-desc="" bounds="[100,1200][900,1320]"/>
    <node index="2" text="Start Game" class="android.widget.Button" package="com.example.game" clickable="true" content-desc="" bounds="[100,1400][900,1520]"/>
  </node>
</hierarchy>
"""


class DesktopModeTests(unittest.TestCase):
    def setUp(self) -> None:
        base_root = Path(__file__).resolve().parents[2] / ".tmp-tests"
        base_root.mkdir(parents=True, exist_ok=True)
        self.temp_root = base_root / f"blueclaw-desktop-{uuid.uuid4().hex}"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.memory_path = self.temp_root / "workflow-memory.jsonl"
        self.game_memory_dir = self.temp_root / "games"
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for path in sorted(self.temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.temp_root.rmdir()

    def _write_xml(self, content: str) -> Path:
        path = self.temp_root / f"{uuid.uuid4().hex}.xml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_learning_cycle_can_capture_from_desktop_mode(self) -> None:
        xml_path = self._write_xml(LOGIN_XML)
        analysis = analyze_screen(ui_dump_path=str(xml_path), package_name="com.example.game")
        capture_result = type("DesktopCapture", (), {"analysis": analysis})()
        desktop_target = DesktopTarget(window_handle=111)
        desktop_options = DesktopOptions(expected_client_width=400, expected_client_height=800)

        with patch("blueclaw_companion.mobile_game_learner.capture_desktop_state", return_value=capture_result) as capture_desktop_state:
            result = run_learning_cycle(
                profile_id="generic",
                package_name="com.example.game",
                memory_path=self.memory_path,
                game_memory_dir=self.game_memory_dir,
                capture=True,
                control_mode="desktop",
                desktop_target=desktop_target,
                desktop_options=desktop_options,
            )

        capture_desktop_state.assert_called_once()
        called_kwargs = capture_desktop_state.call_args.kwargs
        self.assertEqual(called_kwargs["desktop_target"], desktop_target)
        self.assertEqual(called_kwargs["desktop_options"], desktop_options)
        self.assertEqual(result.state["state"], "login")

    def test_desktop_tap_scales_coordinates_to_window_client_area(self) -> None:
        analysis = analyze_screen(package_name="com.example.game")
        action = ActionSuggestion(
            action="battle_continue",
            action_type="tap",
            confidence=0.8,
            reason="test",
            target={"x": 540, "y": 960, "reference_width": 1080, "reference_height": 1920},
            safe_to_apply=True,
            risk_level="safe",
        )
        window = WindowMetadata(
            handle=1,
            process_id=100,
            process_name="HD-Player",
            title="BlueStacks App Player",
            window_left=0,
            window_top=0,
            window_width=420,
            window_height=840,
            client_left=10,
            client_top=20,
            client_width=400,
            client_height=800,
            is_minimized=False,
            is_foreground=True,
        )

        with patch("blueclaw_companion.mobile_game_learner.focus_bluestacks_window", return_value=window):
            with patch("blueclaw_companion.mobile_game_learner.click_bluestacks_relative") as click_relative:
                result = execute_action(action=action, analysis=analysis, control_mode="desktop")

        click_relative.assert_called_once()
        args, kwargs = click_relative.call_args
        self.assertEqual(args, (200, 400))
        self.assertIn("target", kwargs)
        self.assertIn("options", kwargs)
        self.assertTrue(result.executed)

    def test_desktop_key_press_uses_window_keyboard_path(self) -> None:
        analysis = analyze_screen(package_name="com.example.game")
        action = ActionSuggestion(
            action="menu_primary",
            action_type="key_press",
            confidence=0.8,
            reason="test",
            target={"key": "{TAB}", "repeat_count": 2, "repeat_delay_ms": 50},
            safe_to_apply=True,
            risk_level="safe",
        )

        with patch("blueclaw_companion.mobile_game_learner.send_bluestacks_key") as send_key:
            result = execute_action(action=action, analysis=analysis, control_mode="desktop")

        send_key.assert_called_once()
        args, kwargs = send_key.call_args
        self.assertEqual(args, ("{TAB}",))
        self.assertEqual(kwargs["repeat_count"], 2)
        self.assertEqual(kwargs["delay_ms"], 50)
        self.assertIn("target", kwargs)
        self.assertIn("options", kwargs)
        self.assertTrue(result.executed)

    def test_click_relative_rejects_invalid_repeat_count(self) -> None:
        with self.assertRaises(ValueError):
            click_bluestacks_relative(10, 10, repeat_count=0)

    def test_geometry_guard_rejects_unexpected_client_size(self) -> None:
        window = WindowMetadata(
            handle=1,
            process_id=100,
            process_name="HD-Player",
            title="BlueStacks App Player",
            window_left=0,
            window_top=0,
            window_width=420,
            window_height=840,
            client_left=10,
            client_top=20,
            client_width=400,
            client_height=800,
            is_minimized=False,
            is_foreground=True,
        )
        with self.assertRaises(RuntimeError):
            validate_window_geometry(
                window,
                DesktopOptions(expected_client_width=1280, expected_client_height=720),
            )


if __name__ == "__main__":
    unittest.main()

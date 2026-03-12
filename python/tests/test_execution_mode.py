import unittest

from blueclaw_companion.execution_mode import ExecutionMode, resolve_desktop_options, resolve_desktop_target


class ExecutionModeTests(unittest.TestCase):
    def test_execution_mode_accepts_internal_hybrid(self) -> None:
        mode = ExecutionMode.from_value("hybrid")
        self.assertEqual(mode, ExecutionMode.HYBRID)

    def test_resolve_desktop_target_prefers_explicit_values(self) -> None:
        env = {
            "BLUECLAW_WINDOW_HANDLE": "999",
            "BLUECLAW_WINDOW_TITLE_CONTAINS": "ignored-title",
        }
        target = resolve_desktop_target(
            window_handle=123,
            window_title_contains="BlueStacks App Player",
            environ=env,
        )
        self.assertEqual(target.window_handle, 123)
        self.assertEqual(target.window_title_contains, "BlueStacks App Player")

    def test_resolve_desktop_options_reads_env_defaults(self) -> None:
        env = {
            "BLUECLAW_DESKTOP_FULLSCREEN_FALLBACK": "false",
            "BLUECLAW_EXPECTED_CLIENT_WIDTH": "1600",
            "BLUECLAW_EXPECTED_CLIENT_HEIGHT": "900",
            "BLUECLAW_FOCUS_RETRIES": "4",
            "BLUECLAW_FOCUS_RETRY_DELAY_MS": "250",
        }
        options = resolve_desktop_options(environ=env)
        self.assertFalse(options.fullscreen_fallback)
        self.assertEqual(options.expected_client_width, 1600)
        self.assertEqual(options.expected_client_height, 900)
        self.assertEqual(options.focus_retries, 4)
        self.assertEqual(options.focus_retry_delay_ms, 250)


if __name__ == "__main__":
    unittest.main()

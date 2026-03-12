import unittest

from blueclaw_companion.execution_mode import ExecutionMode
from blueclaw_companion.runtime_app import resolve_effective_mode


class RuntimeAppTests(unittest.TestCase):
    def test_hybrid_prefers_desktop_when_window_found(self) -> None:
        mode = resolve_effective_mode(ExecutionMode.HYBRID, bluestacks_found=True)
        self.assertEqual(mode, ExecutionMode.DESKTOP)

    def test_hybrid_falls_back_to_adb_when_window_missing(self) -> None:
        mode = resolve_effective_mode(ExecutionMode.HYBRID, bluestacks_found=False)
        self.assertEqual(mode, ExecutionMode.ADB)

    def test_non_hybrid_mode_is_preserved(self) -> None:
        mode = resolve_effective_mode(ExecutionMode.DESKTOP, bluestacks_found=False)
        self.assertEqual(mode, ExecutionMode.DESKTOP)


if __name__ == "__main__":
    unittest.main()

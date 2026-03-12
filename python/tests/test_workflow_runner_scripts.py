import subprocess
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from blueclaw_companion.workflow_runner import WorkflowContext, run_powershell_script


class WorkflowRunnerScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        base_root = Path(__file__).resolve().parents[2] / ".tmp-tests"
        base_root.mkdir(parents=True, exist_ok=True)
        self.temp_root = base_root / f"blueclaw-workflow-script-{uuid.uuid4().hex}"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        (self.temp_root / "capture-all.ps1").write_text("# test", encoding="utf-8")
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for path in sorted(self.temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.temp_root.rmdir()

    def test_run_powershell_script_serializes_switch_params_without_true_value(self) -> None:
        context = WorkflowContext(workflow_name="test", variables={})
        with patch("blueclaw_companion.workflow_runner.SCRIPTS_DIR", self.temp_root):
            with patch("blueclaw_companion.workflow_runner.subprocess.run") as subprocess_run:
                subprocess_run.return_value = subprocess.CompletedProcess(
                    args=["powershell"],
                    returncode=0,
                    stdout="ok",
                    stderr="",
                )
                run_powershell_script(
                    "capture-all.ps1",
                    {"AllowUiDumpFailure": True, "UiDumpRetries": 2},
                    context,
                )

        command = subprocess_run.call_args.args[0]
        self.assertIn("-AllowUiDumpFailure", command)
        self.assertNotIn("True", command)


if __name__ == "__main__":
    unittest.main()

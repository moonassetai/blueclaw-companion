import subprocess
import unittest
from unittest.mock import patch

from blueclaw_companion.workflow_runner import WorkflowError, run_workflow


class WorkflowRunnerRobustnessTests(unittest.TestCase):
    def test_script_step_retries_before_success(self) -> None:
        workflow = {
            "name": "retry-workflow",
            "steps": [
                {"id": "connect", "action": "script", "script": "connect-bluestacks.ps1", "max_retries": 2},
                {"id": "done", "action": "stop", "message": "done"},
            ],
        }
        with patch("blueclaw_companion.workflow_runner.load_workflow", return_value=workflow):
            with patch(
                "blueclaw_companion.workflow_runner.run_powershell_script",
                side_effect=[
                    WorkflowError("transient failure"),
                    subprocess.CompletedProcess(args=["powershell"], returncode=0, stdout="", stderr=""),
                ],
            ) as run_script:
                result = run_workflow("retry-workflow")

        self.assertEqual(run_script.call_count, 2)
        self.assertEqual(result.status, "stopped")
        self.assertTrue(any(entry.get("status") == "retrying_after_error" for entry in result.commands))

    def test_step_on_error_stop_routes_without_crashing_workflow(self) -> None:
        workflow = {
            "name": "on-error-workflow",
            "steps": [
                {
                    "id": "fragile_step",
                    "action": "script",
                    "script": "connect-bluestacks.ps1",
                    "max_retries": 1,
                    "on_error": "stop",
                },
                {"id": "after", "action": "stop", "message": "should not run"},
            ],
        }
        with patch("blueclaw_companion.workflow_runner.load_workflow", return_value=workflow):
            with patch("blueclaw_companion.workflow_runner.run_powershell_script", side_effect=WorkflowError("fatal")):
                result = run_workflow("on-error-workflow")

        self.assertEqual(result.status, "stopped")
        self.assertIn("on_error", result.message)
        self.assertTrue(any(entry.get("status") == "error_routed" for entry in result.commands))

    def test_step_on_error_routes_to_named_step(self) -> None:
        workflow = {
            "name": "on-error-route-workflow",
            "steps": [
                {
                    "id": "fragile_step",
                    "action": "script",
                    "script": "connect-bluestacks.ps1",
                    "on_error": "fallback_stop",
                },
                {"id": "fallback_stop", "action": "stop", "message": "fallback route reached"},
            ],
        }
        with patch("blueclaw_companion.workflow_runner.load_workflow", return_value=workflow):
            with patch("blueclaw_companion.workflow_runner.run_powershell_script", side_effect=WorkflowError("fatal")):
                result = run_workflow("on-error-route-workflow")

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.message, "fallback route reached")


if __name__ == "__main__":
    unittest.main()

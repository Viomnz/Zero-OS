import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.zero_ai_control_workflows import (
    zero_ai_control_workflow_browser_act,
    zero_ai_control_workflow_browser_open,
    zero_ai_control_workflow_install,
    zero_ai_control_workflow_recover,
    zero_ai_control_workflow_self_repair,
    zero_ai_control_workflows_status,
)
from zero_os.fast_path_cache import clear_fast_path_cache


class ZeroAiControlWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_fast_path_cache(namespace="zero_ai_control_workflows_status")
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_control_workflows_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        clear_fast_path_cache(namespace="zero_ai_control_workflows_status")
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _store_registry_path(self) -> Path:
        path = self.base / ".zero_os" / "store" / "registry.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _stage_store_app(self) -> None:
        self._store_registry_path().write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "DemoApp",
                            "version": "1.0.0",
                            "targets": {
                                "windows": {
                                    "path": "C:/demoapp.exe",
                                    "sha256": "deadbeef",
                                    "size": 10,
                                }
                            },
                            "metadata": {},
                            "security": {
                                "signature_present": True,
                                "permissions_present": True,
                                "malware_scan": "clean",
                            },
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_status_reports_autonomous_lanes(self) -> None:
        status = zero_ai_control_workflows_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertEqual(4, status["summary"]["lane_count"])
        self.assertEqual("autonomous", status["lanes"]["browser"]["control_level"])
        self.assertEqual("autonomous", status["lanes"]["store_install"]["control_level"])
        self.assertEqual("autonomous", status["lanes"]["recovery"]["control_level"])
        self.assertEqual("autonomous", status["lanes"]["self_repair"]["control_level"])

    def test_status_uses_fast_path_when_inputs_are_unchanged(self) -> None:
        first = zero_ai_control_workflows_status(str(self.base))
        second = zero_ai_control_workflows_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])

    def test_browser_workflow_runs_canary_backed_open_and_action(self) -> None:
        with patch("zero_os.browser_session_connector.webbrowser.open", return_value=True):
            opened = zero_ai_control_workflow_browser_open(str(self.base), "https://github.com/Viomnz/Zero-OS")

        self.assertTrue(opened["ok"])
        self.assertTrue(opened["canary"]["ok"])
        self.assertEqual("browser_open", opened["workflow"])

        acted = zero_ai_control_workflow_browser_act(
            str(self.base),
            "https://github.com/Viomnz/Zero-OS",
            "click",
            selector="#main",
        )
        self.assertTrue(acted["ok"])
        self.assertTrue(acted["canary"]["ok"])
        self.assertEqual("browser_act", acted["workflow"])

    def test_store_install_workflow_runs_canary_install_and_promotes_install(self) -> None:
        self._stage_store_app()

        result = zero_ai_control_workflow_install(str(self.base), "DemoApp", email="user@example.com", os_name="windows")

        self.assertTrue(result["ok"])
        self.assertTrue(result["canary"]["ok"])
        self.assertEqual("store_install", result["workflow"])
        self.assertTrue(result["result"]["install"]["ok"])

        prod_state = json.loads((self.base / ".zero_os" / "store" / "prod_state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(prod_state.get("installs", {})), 2)

    def test_recovery_workflow_creates_snapshot_and_recovers(self) -> None:
        result = zero_ai_control_workflow_recover(str(self.base), "latest")

        self.assertTrue(result["ok"])
        self.assertTrue(result["canary"]["ok"])
        self.assertEqual("recovery", result["workflow"])
        self.assertTrue(result["result"]["recovery"]["ok"])

    def test_self_repair_workflow_runs_canary_backed_repair(self) -> None:
        result = zero_ai_control_workflow_self_repair(str(self.base))

        self.assertTrue(result["ok"])
        self.assertTrue(result["canary"]["ok"])
        self.assertEqual("self_repair", result["workflow"])
        self.assertIn("repair", result["result"])


if __name__ == "__main__":
    unittest.main()

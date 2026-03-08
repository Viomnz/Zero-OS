import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.agents_remediation import run_agents_remediation


class AgentsRemediationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_agents_remed_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os" / "runtime").mkdir(parents=True, exist_ok=True)
        (self.base / "ai_from_scratch").mkdir(parents=True, exist_ok=True)
        (self.base / "zero_os_config").mkdir(parents=True, exist_ok=True)
        (self.base / "README.md").write_text("zero os test corpus", encoding="utf-8")
        (self.base / "zero_os_config" / "agi_module_registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "title": "x",
                    "total_modules_expected": 1,
                    "domains": [{"key": "d", "module_count_expected": 1}],
                    "modules": [
                        {
                            "id": "d:01",
                            "name": "m",
                            "domain": "d",
                            "status": "active",
                            "health_contract": {
                                "inputs": ["x"],
                                "outputs": ["y"],
                                "fail_state": "degraded",
                                "safe_state_action": "fallback",
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (self.base / "zero_os_config" / "agi_advanced_layers.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "title": "x",
                    "total_layers_expected": 1,
                    "layers": [
                        {
                            "id": "advanced:01",
                            "name": "layer",
                            "status": "active",
                            "capabilities": ["a"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_creates_checkpoint_when_boot_issue(self) -> None:
        out = run_agents_remediation(
            str(self.base),
            {"score": 40, "smooth": False, "issues": ["boot_not_ok", "module_registry_invalid"]},
        )
        self.assertTrue(any(a.get("action") == "checkpoint_bootstrap" for a in out["actions"]))
        self.assertTrue((self.base / "ai_from_scratch" / "checkpoint.json").exists())

    def test_noop_when_no_issue(self) -> None:
        out = run_agents_remediation(str(self.base), {"score": 100, "smooth": True, "issues": []})
        self.assertEqual(out["actions"][0]["action"], "no_op")

    def test_integrity_issue_triggers_rebaseline(self) -> None:
        out = run_agents_remediation(
            str(self.base),
            {"score": 60, "smooth": False, "issues": ["integrity_not_healthy"]},
        )
        self.assertTrue(any(a.get("action") == "integrity_rebaseline" for a in out["actions"]))
        self.assertTrue((self.base / ".zero_os" / "runtime" / "agent_integrity_baseline.json").exists())
        self.assertTrue((self.base / ".zero_os" / "runtime" / "agent_health.json").exists())


if __name__ == "__main__":
    unittest.main()

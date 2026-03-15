import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.tool_capability_registry import registry_status


class ToolCapabilityRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_tool_registry_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_registry_persists_status_and_reports_missing_tools(self) -> None:
        (self.base / "src").mkdir(parents=True, exist_ok=True)
        (self.base / "src" / "main.py").write_text("# stub\n", encoding="utf-8")
        (self.base / "README.md").write_text("# test\n", encoding="utf-8")

        out = registry_status(str(self.base))

        self.assertTrue(out["ok"])
        self.assertTrue(Path(out["path"]).exists())
        self.assertGreaterEqual(out["summary"]["tool_count"], 8)
        missing = {item["tool"] for item in out["missing_tools"]}
        self.assertIn("recovery", missing)
        self.assertIn("native_store", missing)
        self.assertGreaterEqual(len(out["highest_value_steps"]), 1)

    def test_registry_marks_configured_tools_active(self) -> None:
        (self.base / "src").mkdir(parents=True, exist_ok=True)
        (self.base / "src" / "main.py").write_text("# stub\n", encoding="utf-8")
        (self.base / "README.md").write_text("# test\n", encoding="utf-8")
        (self.base / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        (self.base / "apps" / "demo-app").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "connectors").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "connectors" / "api_profiles.json").write_text(
            json.dumps({"profiles": {"github_public": {"base_url": "https://api.github.com"}}}),
            encoding="utf-8",
        )
        (self.base / ".zero_os" / "production" / "snapshots").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "production" / "snapshots" / "baseline.json").write_text("{}", encoding="utf-8")
        (self.base / ".zero_os" / "runtime").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "runtime" / "phase_runtime_status.json").write_text("{}", encoding="utf-8")

        out = registry_status(str(self.base))

        tools = out["tools"]
        self.assertTrue(tools["system_runtime"]["active"])
        self.assertTrue(tools["recovery"]["active"])
        self.assertTrue(tools["native_store"]["active"])
        self.assertTrue(tools["api_profiles"]["active"])
        self.assertEqual(0, out["summary"]["missing_tool_count"])

    def test_registry_treats_empty_api_profile_store_as_missing(self) -> None:
        (self.base / "src").mkdir(parents=True, exist_ok=True)
        (self.base / "src" / "main.py").write_text("# stub\n", encoding="utf-8")
        (self.base / "README.md").write_text("# test\n", encoding="utf-8")
        (self.base / ".zero_os" / "connectors").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "connectors" / "api_profiles.json").write_text(
            json.dumps({"profiles": {}}),
            encoding="utf-8",
        )

        out = registry_status(str(self.base))

        self.assertFalse(out["tools"]["api_profiles"]["active"])
        self.assertIn("api_profiles", {item["tool"] for item in out["missing_tools"]})


if __name__ == "__main__":
    unittest.main()

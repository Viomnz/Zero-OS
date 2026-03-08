import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.runtime_state import ensure_runtime_schemas


class RuntimeStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_runtime_state_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_creates_missing_schema_files(self) -> None:
        out = ensure_runtime_schemas(str(self.base))
        self.assertTrue(out["ok"])
        self.assertGreater(len(out["updated"]), 0)
        for name in out["updated"]:
            path = self.runtime / name
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)

    def test_migrates_invalid_payload(self) -> None:
        target = self.runtime / "agents_monitor.json"
        target.write_text("{bad json", encoding="utf-8")
        out = ensure_runtime_schemas(str(self.base))
        self.assertIn("agents_monitor.json", out["updated"])
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()

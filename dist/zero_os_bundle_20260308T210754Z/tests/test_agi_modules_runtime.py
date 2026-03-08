import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.agi_modules_runtime import list_module_ids, run_module


class AgiModulesRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_agi_modules_")
        self.base = Path(self.tempdir)
        (self.base / "zero_os_config").mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "title": "test",
            "total_modules_expected": 2,
            "domains": [{"key": "d1", "module_count_expected": 2}],
            "modules": [
                {"id": "d1:01", "name": "m1", "domain": "d1", "status": "active"},
                {"id": "d1:02", "name": "m2", "domain": "d1", "status": "planned"},
            ],
        }
        (self.base / "zero_os_config" / "agi_module_registry.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_list_module_ids(self) -> None:
        mids = list_module_ids(str(self.base))
        self.assertEqual(mids, ["d1:01", "d1:02"])

    def test_run_module(self) -> None:
        out = run_module(str(self.base), "d1:01", {"k": 1})
        self.assertTrue(out["ok"])
        self.assertEqual(out["module_id"], "d1:01")
        self.assertIn("trace", out)


if __name__ == "__main__":
    unittest.main()

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.module_registry import load_registry, validate_registry, write_registry_status


class ModuleRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_registry_")
        self.base = Path(self.tempdir)
        (self.base / "zero_os_config").mkdir(parents=True, exist_ok=True)
        self.registry_path = self.base / "zero_os_config" / "agi_module_registry.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _write_registry(self, modules: list[dict]) -> None:
        bindings = {}
        for m in modules:
            if m.get("status") in {"active", "tested"}:
                bindings[m["id"]] = {
                    "impl_file": "ai_from_scratch/agi_modules_runtime.py",
                    "entrypoint": "run_module",
                    "test_file": "tests/test_agi_modules_runtime.py",
                }
        payload = {
            "schema_version": 1,
            "title": "test",
            "total_modules_expected": len(modules),
            "domains": [{"key": "d1", "module_count_expected": len(modules)}],
            "modules": modules,
            "bindings": bindings,
        }
        self.registry_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_validate_registry_ok(self) -> None:
        self._write_registry(
            [
                {
                    "id": "d1:01",
                    "name": "n1",
                    "domain": "d1",
                    "status": "active",
                    "health_contract": {
                        "inputs": ["a"],
                        "outputs": ["b"],
                        "fail_state": "degraded",
                        "safe_state_action": "fallback",
                    },
                }
            ]
        )
        data = load_registry(str(self.base))
        out = validate_registry(data)
        self.assertTrue(out["ok"])
        self.assertEqual(out["summary"]["total_modules"], 1)

    def test_write_registry_status_file(self) -> None:
        (self.base / "ai_from_scratch").mkdir(parents=True, exist_ok=True)
        (self.base / "tests").mkdir(parents=True, exist_ok=True)
        (self.base / "ai_from_scratch" / "agi_modules_runtime.py").write_text("# stub\n", encoding="utf-8")
        (self.base / "tests" / "test_agi_modules_runtime.py").write_text("# stub\n", encoding="utf-8")
        self._write_registry(
            [
                {
                    "id": "d1:01",
                    "name": "n1",
                    "domain": "d1",
                    "status": "tested",
                    "health_contract": {
                        "inputs": ["a"],
                        "outputs": ["b"],
                        "fail_state": "degraded",
                        "safe_state_action": "fallback",
                    },
                }
            ]
        )
        out = write_registry_status(str(self.base))
        self.assertTrue(out["ok"])
        self.assertTrue((self.base / ".zero_os" / "runtime" / "agi_module_registry_status.json").exists())


if __name__ == "__main__":
    unittest.main()

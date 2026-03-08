import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.advanced_layers_registry import (
    load_advanced_layers,
    validate_advanced_layers,
    write_advanced_layers_status,
)


class AdvancedLayersRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_advanced_layers_")
        self.base = Path(self.tempdir)
        (self.base / "zero_os_config").mkdir(parents=True, exist_ok=True)
        self.path = self.base / "zero_os_config" / "agi_advanced_layers.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _write(self, status: str = "active") -> None:
        payload = {
            "schema_version": 1,
            "title": "x",
            "total_layers_expected": 1,
            "layers": [
                {
                    "id": "advanced:01",
                    "name": "Self-Architecture Evolution Layer",
                    "status": status,
                    "capabilities": ["a", "b"],
                }
            ],
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def test_validate_ok(self) -> None:
        self._write("active")
        out = validate_advanced_layers(load_advanced_layers(str(self.base)))
        self.assertTrue(out["ok"])
        self.assertEqual(out["summary"]["total_layers"], 1)

    def test_write_status_file(self) -> None:
        self._write("tested")
        out = write_advanced_layers_status(str(self.base))
        self.assertTrue(out["ok"])
        self.assertTrue((self.base / ".zero_os" / "runtime" / "agi_advanced_layers_status.json").exists())


if __name__ == "__main__":
    unittest.main()


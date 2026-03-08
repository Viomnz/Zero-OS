import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.memory_update_layer import update_memory_layer


class MemoryUpdateLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_mem_update_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_memory_categories_written(self) -> None:
        out = update_memory_layer(
            str(self.base),
            "optimize storage now",
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"unified_model": {"unified_text": "optimize storage now"}},
            {"signal_type": "positive", "learning_score": 0.9},
            {"mode": "stable", "actions": {"set_profile": "strict", "set_mode": "stability"}},
            {"action": {"method": "parameter_tuning"}},
        )
        self.assertTrue(out["ok"])
        self.assertIn("sizes", out)
        self.assertEqual("high", out["priority"])


if __name__ == "__main__":
    unittest.main()

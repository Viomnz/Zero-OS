import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.reality_modeling_layer import update_reality_model


class RealityModelingLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_reality_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_updates_world_model_file(self) -> None:
        out = update_reality_model(
            str(self.base),
            "monitor kernel memory and network security",
            "human",
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"unified_text": "kernel network security stability"},
        )
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(out["entity_count"], 1)
        p = self.base / ".zero_os" / "runtime" / "reality_world_model.json"
        self.assertTrue(p.exists())

    def test_state_updates_increase(self) -> None:
        a = update_reality_model(str(self.base), "first prompt", "human", {}, {"unified_text": ""})
        b = update_reality_model(str(self.base), "second prompt", "system", {}, {"unified_text": ""})
        self.assertGreaterEqual(b["state_updates"], a["state_updates"])


if __name__ == "__main__":
    unittest.main()


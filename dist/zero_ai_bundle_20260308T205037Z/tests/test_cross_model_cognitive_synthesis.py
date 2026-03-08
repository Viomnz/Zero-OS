import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.cross_model_cognitive_synthesis import synthesize_cross_model_output


class CrossModelCognitiveSynthesisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_cross_model_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_synthesis_returns_unified_output(self) -> None:
        out = synthesize_cross_model_output(
            str(self.base),
            "secure stable action",
            {
                "neural": "generate secure stable path",
                "distributed": "secure stable path with balance",
                "probabilistic": "likely secure path",
            },
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["unified_output"])
        self.assertIn("ranked", out)
        self.assertTrue((self.base / ".zero_os" / "runtime" / "cross_model_cognitive_synthesis.json").exists())

    def test_empty_outputs_fail(self) -> None:
        out = synthesize_cross_model_output(str(self.base), "x", {"neural": "   ", "meta": ""})
        self.assertFalse(out["ok"])
        self.assertEqual("", out["unified_output"])


if __name__ == "__main__":
    unittest.main()


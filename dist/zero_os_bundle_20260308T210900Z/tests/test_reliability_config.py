import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.reliability_config import load_reliability_config


class ReliabilityConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_relcfg_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_default_written_and_loaded(self) -> None:
        cfg = load_reliability_config(str(self.base))
        self.assertIn("balanced", cfg)
        self.assertIn("distributed", cfg)


if __name__ == "__main__":
    unittest.main()

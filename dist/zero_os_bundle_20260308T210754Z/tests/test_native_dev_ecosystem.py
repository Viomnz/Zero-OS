import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NativeDevEcosystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_deveco_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_toolchain_status_command(self) -> None:
        p = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "native_dev_ecosystem.py"), "toolchain-status"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, p.returncode)
        data = json.loads(p.stdout)
        self.assertTrue(data["ok"])
        self.assertIn("tools", data)
        self.assertIn("nasm", data["tools"])
        self.assertIn("cross_gcc", data["tools"])


if __name__ == "__main__":
    unittest.main()

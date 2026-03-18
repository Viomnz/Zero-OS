import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "ai_from_scratch") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai_from_scratch"))

from ai_from_scratch.daemon import _load_model_with_recovery
from ai_from_scratch.daemon_ctl import _checkpoint_health, runtime
from ai_from_scratch.model import TinyBigramModel


class DaemonHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_daemon_hardening_")
        self.base = Path(self.tempdir)
        (self.base / "ai_from_scratch").mkdir(parents=True, exist_ok=True)
        runtime(self.base)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_checkpoint_health_restores_from_backup(self) -> None:
        model = TinyBigramModel.build("zero os checkpoint")
        backup = runtime(self.base) / "checkpoint.backup.json"
        model.save(str(backup))

        out = _checkpoint_health(self.base)
        self.assertTrue(out["ok"])
        self.assertIn(out["source"], {"backup_restore", "checkpoint"})
        ckpt = self.base / "ai_from_scratch" / "checkpoint.json"
        self.assertTrue(ckpt.exists())

    def test_load_model_recovers_from_backup_on_corrupt_checkpoint(self) -> None:
        rt = runtime(self.base)
        ckpt = self.base / "ai_from_scratch" / "checkpoint.json"
        outbox = rt / "zero_ai_output.txt"
        outbox.write_text("", encoding="utf-8")

        model = TinyBigramModel.build("backup copy")
        backup = rt / "checkpoint.backup.json"
        model.save(str(backup))
        ckpt.write_text("{bad-json", encoding="utf-8")

        loaded = _load_model_with_recovery(self.base, rt, outbox)
        self.assertIsNotNone(loaded)
        payload = json.loads(ckpt.read_text(encoding="utf-8", errors="replace"))
        self.assertIn("vocab", payload)
        self.assertIn("architecture", payload)


if __name__ == "__main__":
    unittest.main()

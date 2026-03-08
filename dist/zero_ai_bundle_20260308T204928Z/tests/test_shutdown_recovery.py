import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.shutdown_recovery import (
    load_recovery_state,
    prepare_shutdown_recovery,
    verify_recovery_integrity,
)


class ShutdownRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_shutdown_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_prepare_and_load_recovery(self) -> None:
        (self.runtime / "internal_zero_reasoner_memory.json").write_text(
            json.dumps({"success_patterns": [], "failure_patterns": []}),
            encoding="utf-8",
        )
        out = prepare_shutdown_recovery(str(self.base), "manual_stop", "test", 3, True)
        self.assertEqual("manual_stop", out["trigger"])
        self.assertEqual("manual_request", out["trigger_class"])
        self.assertIn("controlled_shutdown_process", out)
        self.assertIn("recovery_steps", out)
        loaded = load_recovery_state(str(self.base))
        self.assertTrue(loaded["found"])
        self.assertEqual("manual_stop", loaded["state"]["trigger"])
        integ = verify_recovery_integrity(str(self.base))
        self.assertTrue(integ["ok"])


if __name__ == "__main__":
    unittest.main()

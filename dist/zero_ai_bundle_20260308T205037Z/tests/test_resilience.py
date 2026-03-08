import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.resilience import (
    external_outage_failover_apply,
    external_outage_status,
    firmware_rootkit_scan,
    immutable_trust_backup_create,
    immutable_trust_backup_status,
    immutable_trust_recover,
    kernel_driver_compromise_status,
    kernel_driver_emergency_lockdown,
)


class ResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_resilience_")
        self.base = Path(self.tempdir)
        (self.base / "src" / "zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / "src" / "zero_os" / "core.py").write_text("CORE=1\n", encoding="utf-8")
        (self.base / "drivers").mkdir(parents=True, exist_ok=True)
        (self.base / "drivers" / "manifest.json").write_text("{}\n", encoding="utf-8")
        (self.base / "docs" / "kernel").mkdir(parents=True, exist_ok=True)
        (self.base / "docs" / "kernel" / "README.md").write_text("kernel\n", encoding="utf-8")
        (self.base / ".zero_os" / "keys").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "keys" / "trust_root.key").write_text("k\n", encoding="utf-8")
        (self.base / ".zero_os" / "runtime").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "runtime" / "tpm_attestation.json").write_text("{\"ok\":true}\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_kernel_status_and_lockdown(self) -> None:
        st = kernel_driver_compromise_status(str(self.base))
        self.assertTrue(st["ok"])
        lock = kernel_driver_emergency_lockdown(str(self.base))
        self.assertTrue(lock["ok"])

    def test_firmware_scan(self) -> None:
        scan = firmware_rootkit_scan(str(self.base))
        self.assertIn("firmware_rootkit_signal", scan)

    def test_outage_failover(self) -> None:
        st = external_outage_status(str(self.base))
        self.assertIn("outage_count", st)
        ap = external_outage_failover_apply(str(self.base))
        self.assertTrue(ap["ok"])
        self.assertIn("smart_logic", ap)

    def test_immutable_trust_backup_and_recover(self) -> None:
        create = immutable_trust_backup_create(str(self.base))
        self.assertTrue(create["ok"])
        self.assertIn("offsite_replica", create)
        self.assertTrue(Path(create["offsite_replica"]).exists())
        status = immutable_trust_backup_status(str(self.base))
        self.assertGreaterEqual(status["count"], 1)
        rec = immutable_trust_recover(str(self.base), "latest")
        self.assertTrue(rec["ok"])
        self.assertIn("smart_logic", rec)


if __name__ == "__main__":
    unittest.main()

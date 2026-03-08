import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.native_store_smart_logic import (
    abuse_decision,
    package_decision,
    release_gate_decision,
    rollback_decision,
    trust_decision,
)


class NativeStoreSmartLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_native_store_logic_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_package_decision_holds_when_unsigned(self) -> None:
        out = package_decision(str(self.base), "install", "linux", True, False, True)
        self.assertEqual("hold_for_review", out["decision_action"])
        self.assertTrue(out["false_positive_review_needed"])

    def test_rollback_decision_rejects_without_checkpoint(self) -> None:
        out = rollback_decision(str(self.base), False, "medium")
        self.assertEqual("reject_or_hold", out["decision_action"])

    def test_release_gate_holds_with_open_incidents(self) -> None:
        out = release_gate_decision(str(self.base), True, True, 2)
        self.assertEqual("hold_for_review", out["decision_action"])

    def test_abuse_decision_blocks_repeat_offender(self) -> None:
        out = abuse_decision(str(self.base), 85, True)
        self.assertEqual("block", out["decision_action"])

    def test_trust_decision_holds_when_secret_platform_missing(self) -> None:
        out = trust_decision(str(self.base), True, True, False)
        self.assertEqual("hold_for_review", out["decision_action"])


if __name__ == "__main__":
    unittest.main()

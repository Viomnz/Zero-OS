import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.rate_limit import check_and_record
from zero_os.runtime_smart_logic import (
    permission_trust_decision,
    recovery_decision,
    rollout_decision,
    security_action_decision,
)


class RuntimeSmartLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_runtime_logic_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_security_action_holds_without_trust(self) -> None:
        out = security_action_decision(str(self.base), False, True, True)
        self.assertEqual("hold_for_review", out["decision_action"])

    def test_recovery_rejects_without_snapshot(self) -> None:
        out = recovery_decision(str(self.base), False, True, "system")
        self.assertEqual("reject_or_hold", out["decision_action"])

    def test_rollout_holds_prod_with_outages(self) -> None:
        out = rollout_decision(str(self.base), "prod", True, 1)
        self.assertEqual("hold_for_review", out["decision_action"])

    def test_permission_blocks_forbidden_command(self) -> None:
        out = permission_trust_decision(str(self.base), "admin", False, False, True)
        self.assertEqual("block", out["decision_action"])

    def test_rate_limit_state_includes_smart_logic(self) -> None:
        allowed, state = check_and_record(str(self.base), "api", limit=1, window_seconds=60)
        self.assertTrue(allowed)
        self.assertIn("smart_logic", state)
        allowed2, state2 = check_and_record(str(self.base), "api", limit=1, window_seconds=60)
        self.assertFalse(allowed2)
        self.assertIn("smart_logic", state2)


if __name__ == "__main__":
    unittest.main()

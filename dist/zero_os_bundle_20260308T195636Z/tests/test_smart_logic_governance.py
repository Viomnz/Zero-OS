import shutil
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.smart_logic_governance import apply_governance, list_false_positive_reviews


class SmartLogicGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_slg_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_apply_governance_marks_review_needed(self) -> None:
        logic = {
            "engine": "zero_ai_gate_smart_logic_v1",
            "decision_action": "reject_and_regenerate",
            "decision_reason": "gate_checks_failed",
            "confidence": 0.2,
            "root_issues": {"failed_checks": ["logic"], "issue_sources": ["gate_checks_failed"]},
        }
        out = apply_governance(str(self.base), logic, {"stage": "test"})
        self.assertTrue(out["false_positive_review_needed"])
        listed = list_false_positive_reviews(str(self.base), limit=10)
        self.assertGreaterEqual(listed["count"], 1)


if __name__ == "__main__":
    unittest.main()


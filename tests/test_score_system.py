import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.score_system import score_from_checks


class ScoreSystemTests(unittest.TestCase):
    def test_perfect_only_when_no_issues_and_all_checks_pass(self) -> None:
        out = score_from_checks({"a": True, "b": True}, issues=[])
        self.assertEqual(100.0, out["score"])
        self.assertTrue(out["perfect"])

    def test_not_perfect_when_issues_exist(self) -> None:
        out = score_from_checks({"a": True, "b": True}, issues=["x"])
        self.assertEqual(100.0, out["score"])
        self.assertFalse(out["perfect"])

    def test_root_issues_present_when_score_not_perfect(self) -> None:
        out = score_from_checks({"a": True, "b": False}, issues=["x"])
        self.assertLessEqual(out["score"], 99)
        self.assertIn("failed_checks", out["root_issues"])
        self.assertIn("issue_sources", out["root_issues"])
        self.assertIn("b", out["root_issues"]["failed_checks"])

    def test_root_issues_empty_when_perfect(self) -> None:
        out = score_from_checks({"a": True}, issues=[])
        self.assertEqual({}, out["root_issues"])


if __name__ == "__main__":
    unittest.main()

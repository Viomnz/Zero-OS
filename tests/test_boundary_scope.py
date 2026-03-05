import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.boundary_scope import evaluate_scope


class BoundaryScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_scope_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_allows_in_scope_task(self) -> None:
        out = evaluate_scope(str(self.base), "optimize system status", "human")
        self.assertTrue(out["inside_scope"])
        self.assertEqual("allow", out["decision"])

    def test_rejects_unauthorized_action(self) -> None:
        out = evaluate_scope(str(self.base), "disable firewall now", "human")
        self.assertFalse(out["inside_scope"])
        self.assertEqual("reject", out["decision"])

    def test_defers_unknown_domain(self) -> None:
        out = evaluate_scope(str(self.base), "mystic rune phase shift", "human")
        self.assertFalse(out["inside_scope"])
        self.assertIn(out["decision"], {"defer", "reject"})


if __name__ == "__main__":
    unittest.main()


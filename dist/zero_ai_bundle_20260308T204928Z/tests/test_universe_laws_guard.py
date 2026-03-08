import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI = ROOT / "ai_from_scratch"
if str(AI) not in sys.path:
    sys.path.insert(0, str(AI))

from universe_laws_guard import check_universe_laws


class UniverseLawGuardTests(unittest.TestCase):
    def test_passes_when_cycle_present(self) -> None:
        text = "self awareness enters pressure and contradiction then reaches balance and harmony"
        chk = check_universe_laws(text)
        self.assertTrue(chk.passed)

    def test_fails_when_missing_balance(self) -> None:
        text = "self awareness with pressure and contradiction"
        chk = check_universe_laws(text)
        self.assertFalse(chk.passed)
        self.assertIn("law3_balance", chk.reason)


if __name__ == "__main__":
    unittest.main()

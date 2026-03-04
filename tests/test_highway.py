import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


class CoreRoutingTests(unittest.TestCase):
    def test_core_status_route(self) -> None:
        highway = Highway(cwd=".")
        result = highway.dispatch("core status", cwd=".")
        self.assertEqual("system", result.capability)
        self.assertIn("Unified entity: Zero OS Unified Core", result.summary)


if __name__ == "__main__":
    unittest.main()

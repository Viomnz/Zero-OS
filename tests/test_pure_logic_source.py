"""Keep the reviewed PDF and source manifest bound to the foundation."""
import hashlib
import json
import unittest
from pathlib import Path


class PureLogicSourceTests(unittest.TestCase):
    def test_current_and_historical_pdf_identity(self):
        root = Path(__file__).resolve().parents[1]
        source = json.loads((root / "publication/pure_logic_source.json").read_text())
        current = (root / source["path"]).read_bytes()
        self.assertEqual(source["sha256"], hashlib.sha256(current).hexdigest())
        self.assertEqual(source["size_bytes"], len(current))
        old = (root / source["previous_path"]).read_bytes()
        self.assertEqual(source["previous_sha256"], hashlib.sha256(old).hexdigest())
        self.assertIn(source["path"], (root / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()

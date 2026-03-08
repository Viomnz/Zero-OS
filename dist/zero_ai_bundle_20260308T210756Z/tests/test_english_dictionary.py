import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.english_dictionary import (
    add_definition,
    dictionary_status,
    pure_logic_dictionary_step,
    lookup_definition,
)


class EnglishDictionaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_dict_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_base_lookup(self) -> None:
        d = lookup_definition(str(self.base), "kernel")
        self.assertTrue(d["ok"])
        self.assertEqual("base", d["source"])

    def test_add_custom_definition(self) -> None:
        a = add_definition(str(self.base), "hallucination", "A generated statement not grounded in facts.")
        self.assertTrue(a["ok"])
        d = lookup_definition(str(self.base), "hallucination")
        self.assertTrue(d["ok"])
        self.assertEqual("custom", d["source"])

    def test_dictionary_status(self) -> None:
        s = dictionary_status(str(self.base))
        self.assertIn("base_count", s)
        self.assertIn("custom_count", s)

    def test_pure_logic_auto_add_from_rule(self) -> None:
        out = pure_logic_dictionary_step(str(self.base), "latency means the delay before data transfer starts")
        self.assertTrue(out["ok"])
        self.assertEqual("auto_add", out["mode"])
        chk = lookup_definition(str(self.base), "latency")
        self.assertTrue(chk["ok"])
        self.assertEqual("custom", chk["source"])

    def test_pure_logic_single_token_lookup(self) -> None:
        out = pure_logic_dictionary_step(str(self.base), "kernel")
        self.assertTrue(out["ok"])
        self.assertEqual("lookup", out["mode"])


if __name__ == "__main__":
    unittest.main()

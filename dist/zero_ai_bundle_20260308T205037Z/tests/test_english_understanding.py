import unittest

from ai_from_scratch.english_understanding import (
    human_response_from_understanding,
    understand_english,
)
from ai_from_scratch.universe_laws_guard import check_universe_laws


class EnglishUnderstandingTests(unittest.TestCase):
    def test_understand_english_extracts_action(self) -> None:
        d = understand_english("Please create file notes/a.txt with hello world")
        self.assertTrue(d["is_english"])
        self.assertEqual("create", d["action"])
        self.assertEqual("command", d["intent"])
        self.assertGreaterEqual(d["confidence"], 0.6)

    def test_human_response_passes_universe_laws(self) -> None:
        d = understand_english("can you search internet security updates?")
        text = human_response_from_understanding(d, "can you search internet security updates?")
        chk = check_universe_laws(text)
        self.assertTrue(chk.passed)


if __name__ == "__main__":
    unittest.main()

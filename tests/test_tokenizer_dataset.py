import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.tokenizer_dataset import ZeroTokenizer, build_corpus_dataset, load_corpus_dataset


class TokenizerDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_tokenizer_dataset_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_char_tokenizer_lowercase_round_trip(self) -> None:
        tokenizer = ZeroTokenizer.build("Zero AI", mode="char", lowercase=True)
        ids = tokenizer.encode("ZeRo ai")
        self.assertEqual("zero ai", tokenizer.decode_ids(ids))

    def test_byte_tokenizer_round_trip_unicode(self) -> None:
        tokenizer = ZeroTokenizer.build("Zero Ω", mode="byte")
        ids = tokenizer.encode("Zero Ω")
        self.assertEqual("Zero Ω", tokenizer.decode_ids(ids))

    def test_dataset_build_save_and_load(self) -> None:
        dataset = build_corpus_dataset(
            "Zero AI survives contradiction",
            tokenizer_mode="byte",
            valid_fraction=0.25,
            source_path="memory://dataset",
            block_size=10,
        )
        path = self.base / "dataset.json"
        dataset.save(str(path), include_ids=True)
        loaded = load_corpus_dataset(str(path), source_text=dataset.source_text)

        self.assertEqual("byte", loaded.tokenizer.mode)
        self.assertEqual(dataset.source_text, loaded.source_text)
        self.assertEqual(dataset.train_ids, loaded.train_ids)
        self.assertEqual(dataset.valid_ids, loaded.valid_ids)
        self.assertEqual(10, loaded.stats["block_size"])
        self.assertAlmostEqual(0.25, loaded.stats["valid_fraction"])
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        self.assertIn("tokenizer", payload)
        self.assertIn("stats", payload)


if __name__ == "__main__":
    unittest.main()

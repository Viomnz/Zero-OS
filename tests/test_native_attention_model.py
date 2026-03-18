import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.model import NATIVE_ARCHITECTURE, NATIVE_ATTENTION_ARCHITECTURE, TinyBigramModel, inspect_checkpoint_payload
from ai_from_scratch.tokenizer_dataset import build_corpus_dataset


class NativeAttentionModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_native_attention_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_build_defaults_to_attention_base_model(self) -> None:
        model = TinyBigramModel.build("zero ai attention base model")
        meta = model.metadata()
        self.assertEqual(NATIVE_ARCHITECTURE, model.architecture)
        self.assertEqual(NATIVE_ATTENTION_ARCHITECTURE, model.architecture)
        self.assertTrue(meta["fully_native"])
        self.assertTrue(meta["attention_block"])
        self.assertGreaterEqual(meta["attention_heads"], 2)
        self.assertGreater(meta["attention_head_dim"], 0)

    def test_attention_round_trip_checkpoint(self) -> None:
        model = TinyBigramModel.build("zero ai attention survives contradiction and memory")
        ids = model.encode("zero ai attention survives contradiction and memory")
        loss = model.train_step(ids, lr=0.03, batch_size=6)
        self.assertTrue(loss >= 0.0)

        ckpt = self.base / "attention.json"
        model.save(str(ckpt))
        payload = json.loads(ckpt.read_text(encoding="utf-8", errors="replace"))
        summary = inspect_checkpoint_payload(payload)
        self.assertTrue(summary["ok"])
        self.assertTrue(summary["native"])
        self.assertEqual(NATIVE_ATTENTION_ARCHITECTURE, summary["architecture"])
        self.assertGreaterEqual(summary["heads"], 2)

        loaded = TinyBigramModel.load(str(ckpt))
        self.assertTrue(loaded.native_attention)
        self.assertEqual(NATIVE_ATTENTION_ARCHITECTURE, loaded.architecture)
        self.assertTrue(loaded.sample("zero", length=6))

    def test_attention_resolves_requested_head_count(self) -> None:
        model = TinyBigramModel.build(
            "zero ai multi head attention",
            architecture=NATIVE_ATTENTION_ARCHITECTURE,
            embed_dim=24,
            attention_heads=3,
        )
        self.assertEqual(3, model.attention_heads)
        self.assertEqual(8, model.attention_head_dim)

    def test_attention_checkpoint_preserves_tokenizer_dataset_metadata(self) -> None:
        dataset = build_corpus_dataset(
            "Zero AI byte path Ω survives contradiction",
            tokenizer_mode="byte",
            valid_fraction=0.2,
            source_path="memory://zero-byte-corpus",
            block_size=12,
        )
        model = TinyBigramModel.build(
            dataset.source_text,
            architecture=NATIVE_ATTENTION_ARCHITECTURE,
            block_size=dataset.block_size,
            tokenizer=dataset.tokenizer,
            dataset_source_path=dataset.source_path,
            dataset_stats=dataset.stats,
        )
        self.assertEqual("byte", model.tokenizer_mode)
        self.assertEqual(dataset.train_ids + dataset.valid_ids, model.encode(dataset.source_text))

        ckpt = self.base / "attention-tokenizer.json"
        model.save(str(ckpt))
        payload = json.loads(ckpt.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual("byte", payload["tokenizer"]["mode"])
        self.assertEqual(dataset.source_path, payload["dataset"]["source_path"])
        self.assertEqual(dataset.stats["valid_token_count"], payload["dataset"]["stats"]["valid_token_count"])

        loaded = TinyBigramModel.load(str(ckpt))
        self.assertEqual("byte", loaded.tokenizer_mode)
        self.assertEqual(dataset.source_path, loaded.dataset_source_path)
        self.assertEqual(dataset.tokenizer.decode_ids(dataset.tokenizer.encode("Zero Ω")), loaded.decode(loaded.encode("Zero Ω")))

    def test_attention_evaluate_split_reports_perplexity(self) -> None:
        model = TinyBigramModel.build("zero ai evaluates stable branches")
        ids = model.encode("zero ai evaluates stable branches")
        report = model.evaluate_split(ids, split="train")
        self.assertEqual("train", report["split"])
        self.assertTrue(report["ready"])
        self.assertGreater(report["perplexity"], 0.0)


if __name__ == "__main__":
    unittest.main()

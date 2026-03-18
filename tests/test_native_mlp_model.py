import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.model import NATIVE_MLP_ARCHITECTURE, TinyBigramModel, inspect_checkpoint_payload


class NativeMlpModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_native_mlp_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_build_defaults_to_native_mlp(self) -> None:
        model = TinyBigramModel.build("zero ai native model", architecture=NATIVE_MLP_ARCHITECTURE)
        meta = model.metadata()
        self.assertEqual(NATIVE_MLP_ARCHITECTURE, model.architecture)
        self.assertTrue(meta["fully_native"])
        self.assertGreaterEqual(meta["block_size"], 2)
        self.assertGreater(meta["embed_dim"], 0)
        self.assertGreater(meta["hidden_dim"], 0)
        self.assertFalse(meta["attention_block"])

    def test_train_save_load_round_trip(self) -> None:
        model = TinyBigramModel.build(
            "zero ai native model survives contradiction",
            architecture=NATIVE_MLP_ARCHITECTURE,
        )
        ids = model.encode("zero ai native model survives contradiction")
        loss = model.train_step(ids, lr=0.05, batch_size=8)
        self.assertTrue(loss >= 0.0)

        ckpt = self.base / "checkpoint.json"
        model.save(str(ckpt))
        payload = json.loads(ckpt.read_text(encoding="utf-8", errors="replace"))
        summary = inspect_checkpoint_payload(payload)
        self.assertTrue(summary["ok"])
        self.assertTrue(summary["native"])
        self.assertEqual(NATIVE_MLP_ARCHITECTURE, summary["architecture"])

        loaded = TinyBigramModel.load(str(ckpt))
        self.assertEqual(NATIVE_MLP_ARCHITECTURE, loaded.architecture)
        self.assertTrue(loaded.sample("zero", length=8))

    def test_load_legacy_bigram_checkpoint(self) -> None:
        ckpt = self.base / "legacy.json"
        ckpt.write_text(
            json.dumps(
                {
                    "vocab": ["a", "b"],
                    "logits": [[0.0, 1.0], [1.0, 0.0]],
                }
            ),
            encoding="utf-8",
        )
        loaded = TinyBigramModel.load(str(ckpt))
        self.assertEqual("zero_legacy_bigram_v1", loaded.architecture)
        self.assertFalse(loaded.native_mlp)
        self.assertTrue(loaded.sample("a", length=4))


if __name__ == "__main__":
    unittest.main()

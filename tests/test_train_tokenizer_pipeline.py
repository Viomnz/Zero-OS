import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.model import TinyBigramModel


ROOT = Path(__file__).resolve().parents[1]


class TrainTokenizerPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_train_tokenizer_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_train_and_generate_use_checkpoint_tokenizer(self) -> None:
        corpus = self.base / "corpus.txt"
        checkpoint = self.base / "checkpoint.json"
        dataset = self.base / "checkpoint.dataset.json"
        prompt = "Zero \u03A9"
        corpus.write_text("Zero AI byte tokenizer pipeline \u03A9 survives pressure.\n", encoding="utf-8")

        train = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "train.py"),
                "--input",
                str(corpus),
                "--steps",
                "2",
                "--architecture",
                "zero_native_char_attention_v1",
                "--tokenizer-mode",
                "byte",
                "--out",
                str(checkpoint),
                "--dataset-out",
                str(dataset),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, train.returncode, train.stderr)
        self.assertTrue(checkpoint.exists())
        self.assertTrue(dataset.exists())
        self.assertIn("eval=", train.stdout)

        payload = json.loads(checkpoint.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual("byte", payload["tokenizer"]["mode"])
        self.assertEqual(str(corpus.resolve()), payload["dataset"]["source_path"])
        self.assertEqual(str(dataset.resolve()), payload["dataset"]["artifact_path"])
        self.assertIn("eval_metrics", payload)
        self.assertEqual("valid", payload["eval_metrics"]["primary_split"])
        self.assertGreater(payload["eval_metrics"]["primary_perplexity"], 0.0)

        loaded = TinyBigramModel.load(str(checkpoint))
        self.assertEqual("byte", loaded.tokenizer_mode)
        self.assertEqual(str(dataset.resolve()), loaded.dataset_artifact_path)
        self.assertIn("valid", loaded.eval_metrics)
        self.assertTrue(loaded.sample(prompt, length=4))

        generate = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "generate.py"),
                "--ckpt",
                str(checkpoint),
                "--prompt",
                prompt,
                "--length",
                "4",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, generate.returncode, generate.stderr)
        self.assertTrue(generate.stdout.strip())

        evaluate = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "eval.py"),
                "--ckpt",
                str(checkpoint),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, evaluate.returncode, evaluate.stderr)
        report = json.loads(evaluate.stdout)
        self.assertEqual("artifact", report["dataset_resolution"])
        self.assertEqual("valid", report["primary_split"])
        self.assertGreater(report["primary_perplexity"], 0.0)

    def test_eval_rebuild_uses_checkpoint_tokenizer(self) -> None:
        corpus = self.base / "rebuild.txt"
        checkpoint = self.base / "rebuild_checkpoint.json"
        dataset = self.base / "rebuild_checkpoint.dataset.json"
        corpus.write_text("Zero \u03A9 byte rebuild path remains stable.\n", encoding="utf-8")

        train = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "train.py"),
                "--input",
                str(corpus),
                "--steps",
                "2",
                "--tokenizer-mode",
                "byte",
                "--out",
                str(checkpoint),
                "--dataset-out",
                str(dataset),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, train.returncode, train.stderr)
        dataset.unlink()

        evaluate = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "eval.py"),
                "--ckpt",
                str(checkpoint),
                "--input",
                str(corpus),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, evaluate.returncode, evaluate.stderr)
        report = json.loads(evaluate.stdout)
        self.assertEqual("rebuild", report["dataset_resolution"])
        self.assertEqual("byte", report["tokenizer_mode"])
        self.assertGreater(report["primary_perplexity"], 0.0)

    def test_resume_training_keeps_best_validation_checkpoint(self) -> None:
        corpus = self.base / "resume.txt"
        checkpoint = self.base / "resume_checkpoint.json"
        dataset = self.base / "resume_checkpoint.dataset.json"
        corpus.write_text(
            "Zero AI resume path survives contradiction and keeps the strongest validation branch.\n",
            encoding="utf-8",
        )

        initial_train = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "train.py"),
                "--input",
                str(corpus),
                "--steps",
                "4",
                "--architecture",
                "zero_native_char_attention_v1",
                "--out",
                str(checkpoint),
                "--dataset-out",
                str(dataset),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, initial_train.returncode, initial_train.stderr)
        initial_payload = json.loads(checkpoint.read_text(encoding="utf-8", errors="replace"))
        initial_steps = int(initial_payload["training_steps"])

        resumed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "train.py"),
                "--resume",
                str(checkpoint),
                "--steps",
                "4",
                "--lr",
                "0.03",
                "--lr-final",
                "0.01",
                "--keep-best-valid",
                "--eval-interval",
                "1",
                "--out",
                str(checkpoint),
                "--dataset-out",
                str(dataset),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertIn("resume=", resumed.stdout)
        self.assertIn("best_eval_step=", resumed.stdout)
        self.assertIn("restored_best_primary_ppl=", resumed.stdout)

        payload = json.loads(checkpoint.read_text(encoding="utf-8", errors="replace"))
        self.assertGreaterEqual(int(payload["training_steps"]), initial_steps)
        self.assertEqual(str(dataset.resolve()), payload["dataset"]["artifact_path"])
        self.assertIn("eval_metrics", payload)
        self.assertGreater(payload["eval_metrics"]["primary_perplexity"], 0.0)

        loaded = TinyBigramModel.load(str(checkpoint))
        self.assertEqual(str(dataset.resolve()), loaded.dataset_artifact_path)
        self.assertGreater(loaded.eval_metrics["primary_perplexity"], 0.0)

    def test_resume_training_prefers_explicit_input_corpus(self) -> None:
        first_corpus = self.base / "first.txt"
        second_corpus = self.base / "second.txt"
        checkpoint = self.base / "switch_checkpoint.json"
        dataset = self.base / "switch_checkpoint.dataset.json"
        first_corpus.write_text("alpha beta gamma delta\n", encoding="utf-8")
        second_corpus.write_text("zero ai law mix pressure balance contradiction\n", encoding="utf-8")

        initial_train = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "train.py"),
                "--input",
                str(first_corpus),
                "--steps",
                "3",
                "--out",
                str(checkpoint),
                "--dataset-out",
                str(dataset),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, initial_train.returncode, initial_train.stderr)

        resumed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "train.py"),
                "--resume",
                str(checkpoint),
                "--input",
                str(second_corpus),
                "--steps",
                "2",
                "--keep-best-valid",
                "--eval-interval",
                "1",
                "--out",
                str(checkpoint),
                "--dataset-out",
                str(dataset),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, resumed.returncode, resumed.stderr)

        payload = json.loads(checkpoint.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual(str(second_corpus.resolve()), payload["dataset"]["source_path"])
        self.assertEqual(str(dataset.resolve()), payload["dataset"]["artifact_path"])

        saved_dataset = json.loads(dataset.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual(str(second_corpus.resolve()), saved_dataset["source_path"])

    def test_manifest_training_builds_native_multi_corpus_dataset(self) -> None:
        corpus_a = self.base / "a.txt"
        corpus_b = self.base / "b.txt"
        manifest = self.base / "suite.json"
        checkpoint = self.base / "manifest_checkpoint.json"
        dataset = self.base / "manifest_checkpoint.dataset.json"
        history_dir = self.base / "history"
        corpus_a.write_text("zero ai contradiction law core\n", encoding="utf-8")
        corpus_b.write_text("strategy context balance pressure\n", encoding="utf-8")
        history_dir.mkdir(parents=True, exist_ok=True)
        (history_dir / "history.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "run_label": "baseline",
                            "architecture": "zero_native_char_attention_v1",
                            "tokenizer_mode": "char",
                            "cohort": "zero_native_char_attention_v1|char",
                            "primary_perplexity": 10.0,
                            "families": [
                                {"family": "law", "primary_perplexity": 8.0},
                                {"family": "strategy", "primary_perplexity": 12.0},
                            ],
                        },
                        sort_keys=True,
                    ),
                    json.dumps(
                        {
                            "run_label": "regressed",
                            "architecture": "zero_native_char_attention_v1",
                            "tokenizer_mode": "char",
                            "cohort": "zero_native_char_attention_v1|char",
                            "primary_perplexity": 12.0,
                            "families": [
                                {"family": "law", "primary_perplexity": 11.0},
                                {"family": "strategy", "primary_perplexity": 12.0},
                            ],
                        },
                        sort_keys=True,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        manifest.write_text(
            json.dumps(
                {
                    "suite": "local_manifest_suite",
                    "description": "Local native manifest training test.",
                    "valid_fraction": 0.2,
                    "corpora": [
                        {"name": "law_core", "path": str(corpus_a), "weight": 1.0, "family": "law"},
                        {"name": "strategy", "path": str(corpus_b), "weight": 0.5, "family": "strategy"},
                    ],
                    "training": {
                        "family_sampling": "balanced",
                        "adaptive": {
                            "enabled": True,
                            "history_dir": str(history_dir.resolve()),
                            "window": 2,
                            "max_focus_families": 1,
                        },
                        "curriculum": [
                            {
                                "name": "balanced_stage",
                                "weight_scale": 2,
                                "family_sampling": "balanced",
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        train = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "train.py"),
                "--manifest",
                str(manifest),
                "--manifest-weight-scale",
                "4",
                "--steps",
                "2",
                "--out",
                str(checkpoint),
                "--dataset-out",
                str(dataset),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, train.returncode, train.stderr)
        self.assertIn("manifest=", train.stdout)

        payload = json.loads(checkpoint.read_text(encoding="utf-8", errors="replace"))
        stats = payload["dataset"]["stats"]
        self.assertEqual(str(manifest.resolve()), payload["dataset"]["source_path"])
        self.assertEqual("benchmark_manifest", stats["source_kind"])
        self.assertEqual("local_manifest_suite", stats["manifest_suite"])
        self.assertEqual(2, stats["manifest_corpus_count"])
        self.assertEqual(4, stats["manifest_weight_scale"])
        self.assertEqual(2, len(stats["manifest_corpora"]))
        self.assertEqual("balanced", stats["training_family_sampling"])
        self.assertEqual(2, stats["curriculum_stage_count"])
        self.assertEqual("adaptive_regression_focus", stats["curriculum_stages"][0]["name"])
        self.assertEqual("balanced_stage", stats["curriculum_stages"][1]["name"])
        self.assertTrue(stats["adaptive_curriculum_enabled"])
        self.assertTrue(stats["adaptive_curriculum_applied"])
        self.assertEqual("regression_focus", stats["adaptive_curriculum_reason"])
        self.assertEqual("zero_native_char_attention_v1|char", stats["adaptive_curriculum_cohort"])
        self.assertEqual("law", stats["adaptive_curriculum_stage"]["include_families"][0])

        saved_dataset = json.loads(dataset.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual(str(manifest.resolve()), saved_dataset["source_path"])
        self.assertEqual("benchmark_manifest", saved_dataset["stats"]["source_kind"])

    def test_eval_rebuild_uses_manifest_when_dataset_artifact_missing(self) -> None:
        corpus_a = self.base / "manifest_eval_a.txt"
        corpus_b = self.base / "manifest_eval_b.txt"
        manifest = self.base / "manifest_eval.json"
        checkpoint = self.base / "manifest_eval_checkpoint.json"
        dataset = self.base / "manifest_eval_checkpoint.dataset.json"
        corpus_a.write_text("zero ai law recursion structure\n", encoding="utf-8")
        corpus_b.write_text("pressure context memory goals\n", encoding="utf-8")
        manifest.write_text(
            json.dumps(
                {
                    "suite": "manifest_eval_suite",
                    "valid_fraction": 0.2,
                    "corpora": [
                        {"name": "law", "path": str(corpus_a), "weight": 1.0, "family": "law"},
                        {"name": "context", "path": str(corpus_b), "weight": 1.0, "family": "context"},
                    ],
                }
            ),
            encoding="utf-8",
        )

        train = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "train.py"),
                "--manifest",
                str(manifest),
                "--steps",
                "2",
                "--out",
                str(checkpoint),
                "--dataset-out",
                str(dataset),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, train.returncode, train.stderr)
        dataset.unlink()

        evaluate = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "eval.py"),
                "--ckpt",
                str(checkpoint),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, evaluate.returncode, evaluate.stderr)
        report = json.loads(evaluate.stdout)
        self.assertEqual("rebuild", report["dataset_resolution"])
        self.assertEqual(str(manifest.resolve()), report["dataset_source_path"])
        self.assertGreater(report["primary_perplexity"], 0.0)


if __name__ == "__main__":
    unittest.main()

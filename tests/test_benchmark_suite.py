import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.benchmark_suite import build_manifest_training_dataset, materialize_manifest_training_corpus, run_benchmark_suite
from ai_from_scratch.model import TinyBigramModel


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkSuiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_benchmark_suite_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_run_benchmark_suite_across_manifest_corpora(self) -> None:
        corpus_a = self.base / "corpus_a.txt"
        corpus_b = self.base / "corpus_b.txt"
        manifest = self.base / "suite.json"
        checkpoint = self.base / "checkpoint.json"

        corpus_a.write_text("zero ai recursion survives contradiction\n", encoding="utf-8")
        corpus_b.write_text("zero ai strategic context remains stable\n", encoding="utf-8")
        manifest.write_text(
            json.dumps(
                {
                    "suite": "temp_suite",
                    "valid_fraction": 0.2,
                    "corpora": [
                        {"name": "a", "path": str(corpus_a.resolve()), "weight": 1.0, "family": "law_core"},
                        {"name": "b", "path": str(corpus_b.resolve()), "weight": 2.0, "family": "strategy_context"},
                    ],
                }
            ),
            encoding="utf-8",
        )

        model = TinyBigramModel.build((corpus_a.read_text(encoding="utf-8") + corpus_b.read_text(encoding="utf-8")))
        model.save(str(checkpoint))

        report = run_benchmark_suite(str(checkpoint), manifest_path=str(manifest))
        self.assertEqual("temp_suite", report["suite"])
        self.assertEqual(2, report["corpus_count"])
        self.assertEqual("char", report["tokenizer_mode"])
        self.assertEqual("valid", report["primary_split"])
        self.assertGreater(report["primary_perplexity"], 0.0)
        self.assertEqual("a", report["corpora"][0]["name"])
        self.assertEqual("law_core", report["corpora"][0]["family"])
        self.assertEqual(2, report["family_count"])
        self.assertEqual({"law_core", "strategy_context"}, {item["family"] for item in report["families"]})
        self.assertTrue(report["valid"]["ready"])

    def test_benchmark_cli_writes_output(self) -> None:
        corpus = self.base / "corpus.txt"
        manifest = self.base / "suite.json"
        checkpoint = self.base / "checkpoint.json"
        output = self.base / "benchmark.json"

        corpus.write_text("zero ai benchmark suite output path\n", encoding="utf-8")
        manifest.write_text(
            json.dumps({"suite": "cli_suite", "corpora": [{"name": "solo", "path": str(corpus.resolve()), "weight": 1.0}]}),
            encoding="utf-8",
        )
        model = TinyBigramModel.build(corpus.read_text(encoding="utf-8"))
        model.save(str(checkpoint))

        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_suite.py"),
                "--ckpt",
                str(checkpoint),
                "--manifest",
                str(manifest),
                "--out",
                str(output),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue(output.exists())
        report = json.loads(output.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual("cli_suite", report["suite"])
        self.assertEqual(1, report["corpus_count"])
        self.assertGreater(report["primary_perplexity"], 0.0)

    def test_materialize_manifest_training_corpus_supports_curriculum_and_balanced_families(self) -> None:
        corpus_a = self.base / "curriculum_a.txt"
        corpus_b = self.base / "curriculum_b.txt"
        corpus_c = self.base / "curriculum_c.txt"
        manifest = self.base / "curriculum_suite.json"

        corpus_a.write_text("law alpha\n", encoding="utf-8")
        corpus_b.write_text("law beta\n", encoding="utf-8")
        corpus_c.write_text("strategy gamma\n", encoding="utf-8")
        manifest.write_text(
            json.dumps(
                {
                    "suite": "curriculum_suite",
                    "corpora": [
                        {"name": "law_a", "path": str(corpus_a.resolve()), "weight": 1.0, "family": "law_core"},
                        {"name": "law_b", "path": str(corpus_b.resolve()), "weight": 1.0, "family": "law_core"},
                        {"name": "strategy", "path": str(corpus_c.resolve()), "weight": 0.5, "family": "strategy_context"},
                    ],
                    "training": {
                        "family_sampling": "weighted",
                        "curriculum": [
                            {
                                "name": "law_focus",
                                "weight_scale": 2,
                                "family_weights": {"law_core": 2.0, "strategy_context": 0.5},
                            },
                            {
                                "name": "balanced_finish",
                                "weight_scale": 2,
                                "family_sampling": "balanced",
                            },
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        bundle = materialize_manifest_training_corpus(str(manifest), weight_scale=3)
        self.assertEqual("weighted", bundle["family_sampling"])
        self.assertEqual(2, len(bundle["curriculum"]))
        self.assertEqual("law_focus", bundle["curriculum"][0]["name"])
        self.assertEqual("balanced_finish", bundle["curriculum"][1]["name"])
        self.assertEqual(3, len(bundle["corpora"]))
        self.assertTrue(bundle["text"])

        balanced_stage = bundle["curriculum"][1]
        family_counts: dict[str, int] = {}
        for item in balanced_stage["corpora"]:
            family_counts[item["family"]] = family_counts.get(item["family"], 0) + int(item["repeat_count"])
        self.assertEqual({"law_core", "strategy_context"}, set(family_counts))
        self.assertLessEqual(abs(family_counts["law_core"] - family_counts["strategy_context"]), 1)

    def test_build_manifest_training_dataset_records_curriculum_metadata(self) -> None:
        corpus_a = self.base / "dataset_a.txt"
        corpus_b = self.base / "dataset_b.txt"
        manifest = self.base / "dataset_suite.json"

        corpus_a.write_text("zero ai law core pressure\n", encoding="utf-8")
        corpus_b.write_text("strategy context stability\n", encoding="utf-8")
        manifest.write_text(
            json.dumps(
                {
                    "suite": "dataset_suite",
                    "valid_fraction": 0.2,
                    "corpora": [
                        {"name": "law", "path": str(corpus_a.resolve()), "weight": 1.0, "family": "law_core"},
                        {"name": "strategy", "path": str(corpus_b.resolve()), "weight": 0.5, "family": "strategy_context"},
                    ],
                    "training": {
                        "family_sampling": "balanced",
                        "curriculum": [
                            {"name": "balanced_stage", "weight_scale": 2, "family_sampling": "balanced"},
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        dataset = build_manifest_training_dataset(str(manifest), block_size=12, weight_scale=4)
        self.assertEqual(str(manifest.resolve()), dataset.source_path)
        self.assertEqual("benchmark_manifest", dataset.stats["source_kind"])
        self.assertEqual("balanced", dataset.stats["training_family_sampling"])
        self.assertEqual(1, dataset.stats["curriculum_stage_count"])
        self.assertEqual("balanced_stage", dataset.stats["curriculum_stages"][0]["name"])
        self.assertGreater(dataset.stats["token_count"], 0)

    def test_materialize_manifest_training_corpus_injects_adaptive_regression_stage(self) -> None:
        corpus_a = self.base / "adaptive_a.txt"
        corpus_b = self.base / "adaptive_b.txt"
        manifest = self.base / "adaptive_suite.json"
        history_dir = self.base / "history"

        corpus_a.write_text("zero ai law core pressure\n", encoding="utf-8")
        corpus_b.write_text("strategy context stability\n", encoding="utf-8")
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
                                {"family": "law_core", "primary_perplexity": 8.0},
                                {"family": "strategy_context", "primary_perplexity": 12.0},
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
                                {"family": "law_core", "primary_perplexity": 11.0},
                                {"family": "strategy_context", "primary_perplexity": 12.0},
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
                    "suite": "adaptive_suite",
                    "corpora": [
                        {"name": "law", "path": str(corpus_a.resolve()), "weight": 1.0, "family": "law_core"},
                        {"name": "strategy", "path": str(corpus_b.resolve()), "weight": 1.0, "family": "strategy_context"},
                    ],
                    "training": {
                        "family_sampling": "weighted",
                        "adaptive": {
                            "enabled": True,
                            "history_dir": str(history_dir.resolve()),
                            "window": 2,
                            "max_focus_families": 1,
                        },
                        "curriculum": [
                            {"name": "base_stage", "weight_scale": 1},
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        bundle = materialize_manifest_training_corpus(
            str(manifest),
            architecture="zero_native_char_attention_v1",
            tokenizer_mode="char",
        )
        self.assertTrue(bundle["adaptive"]["applied"])
        self.assertEqual("adaptive_regression_focus", bundle["curriculum"][0]["name"])
        self.assertEqual("law_core", bundle["curriculum"][0]["corpora"][0]["family"])


if __name__ == "__main__":
    unittest.main()

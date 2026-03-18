import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.benchmark_history import (
    benchmark_adaptive_curriculum_status,
    benchmark_alert_routes_status,
    benchmark_dashboard_status,
    benchmark_remediation_status,
    compare_records,
    evaluate_benchmark_gate,
    record_benchmark_run,
    route_benchmark_alerts,
)
from ai_from_scratch.model import TinyBigramModel
from ai_from_scratch.tokenizer_dataset import ZeroTokenizer


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_benchmark_history_")
        self.base = Path(self.tempdir)
        self.history_dir = self.base / "history"

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _make_manifest_and_checkpoints(self) -> tuple[Path, Path, Path]:
        corpus_a = self.base / "corpus_a.txt"
        corpus_b = self.base / "corpus_b.txt"
        manifest = self.base / "suite.json"
        checkpoint_a = self.base / "checkpoint_a.json"
        checkpoint_b = self.base / "checkpoint_b.json"

        corpus_a.write_text("zero ai recursion survives contradiction\n", encoding="utf-8")
        corpus_b.write_text("zero ai strategic context remains stable\n", encoding="utf-8")
        manifest.write_text(
            json.dumps(
                {
                    "suite": "history_suite",
                    "valid_fraction": 0.2,
                    "corpora": [
                        {"name": "a", "path": str(corpus_a.resolve()), "weight": 1.0, "family": "law_core"},
                        {"name": "b", "path": str(corpus_b.resolve()), "weight": 1.0, "family": "strategy_context"},
                    ],
                }
            ),
            encoding="utf-8",
        )

        merged = corpus_a.read_text(encoding="utf-8") + corpus_b.read_text(encoding="utf-8")
        base_model = TinyBigramModel.build(merged)
        base_model.save(str(checkpoint_a))

        tuned_model = TinyBigramModel.build(merged)
        ids = tuned_model.encode(merged)
        tuned_model.train_step(ids, lr=0.05, batch_size=8)
        tuned_model.save(str(checkpoint_b))
        return manifest, checkpoint_a, checkpoint_b

    def _make_byte_checkpoint(self, text: str, path: Path) -> Path:
        tokenizer = ZeroTokenizer.build(text, mode="byte")
        model = TinyBigramModel.build(text, tokenizer=tokenizer)
        model.save(str(path))
        return path

    def _write_gate_config(self, payload: dict, name: str = "gate.json") -> Path:
        path = self.base / name
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _write_history_rows(self, rows: list[dict]) -> Path:
        history_dir = self.base / "adaptive_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_path = history_dir / "history.jsonl"
        history_path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
        return history_dir

    def test_record_benchmark_run_writes_history_and_comparison(self) -> None:
        manifest, checkpoint_a, checkpoint_b = self._make_manifest_and_checkpoints()
        out_a = self.base / "run_a.json"
        out_b = self.base / "run_b.json"

        first = record_benchmark_run(
            str(checkpoint_a),
            manifest_path=str(manifest),
            out_path=str(out_a),
            history_dir=self.history_dir,
            label="base",
        )
        second = record_benchmark_run(
            str(checkpoint_b),
            manifest_path=str(manifest),
            out_path=str(out_b),
            history_dir=self.history_dir,
            label="tuned",
        )

        self.assertEqual("base", first["run_label"])
        self.assertEqual("tuned", second["run_label"])
        self.assertTrue((self.history_dir / "latest.json").exists())
        self.assertTrue((self.history_dir / "history.jsonl").exists())
        self.assertTrue((self.history_dir / "history_summary.md").exists())
        self.assertTrue((self.history_dir / "compare_latest.md").exists())
        self.assertTrue((self.history_dir / "cohorts_summary.md").exists())
        self.assertTrue((self.history_dir / "families_summary.md").exists())
        self.assertTrue((self.history_dir / "trend_charts.md").exists())
        self.assertTrue((self.history_dir / "family_trend_charts.md").exists())
        self.assertTrue((self.history_dir / "trend_charts.json").exists())
        self.assertTrue((self.history_dir / "gate_latest.json").exists())
        self.assertTrue((self.history_dir / "alerts_latest.md").exists())
        self.assertTrue((self.history_dir / "alert_routes.json").exists())
        self.assertTrue((self.history_dir / "dashboard_latest.md").exists())
        self.assertTrue((self.history_dir / "dashboard_latest.json").exists())
        self.assertTrue((self.history_dir / "remediation_latest.md").exists())
        self.assertTrue((self.history_dir / "remediation_latest.json").exists())

        history_rows = (self.history_dir / "history.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()
        self.assertEqual(2, len([row for row in history_rows if row.strip()]))
        comparison = compare_records(first, second)
        self.assertIn(comparison["primary_perplexity"]["trend"], {"improved", "regressed", "stable"})
        self.assertIn("cohort", comparison)
        self.assertIn("gate", second)
        self.assertEqual("pass", second["gate"]["status"])
        families_text = (self.history_dir / "families_summary.md").read_text(encoding="utf-8", errors="replace")
        self.assertIn("law_core", families_text)
        charts_payload = json.loads((self.history_dir / "trend_charts.json").read_text(encoding="utf-8", errors="replace"))
        self.assertIn("cohort_charts", charts_payload)
        self.assertIn("family_charts", charts_payload)
        gate_payload = json.loads((self.history_dir / "gate_latest.json").read_text(encoding="utf-8", errors="replace"))
        self.assertEqual("pass", gate_payload["status"])
        route_payload = json.loads((self.history_dir / "alert_routes.json").read_text(encoding="utf-8", errors="replace"))
        self.assertIn("routes", route_payload)
        dashboard_payload = json.loads((self.history_dir / "dashboard_latest.json").read_text(encoding="utf-8", errors="replace"))
        self.assertIn("latest_run", dashboard_payload)
        self.assertIn("remediation", dashboard_payload)
        remediation_payload = json.loads((self.history_dir / "remediation_latest.json").read_text(encoding="utf-8", errors="replace"))
        self.assertIn("status", remediation_payload)
        self.assertIn("proposal", remediation_payload)
        dashboard_status = benchmark_dashboard_status(history_dir=self.history_dir)
        self.assertFalse(dashboard_status["missing"])
        self.assertIn("dashboard", dashboard_status)
        alert_status = benchmark_alert_routes_status(history_dir=self.history_dir)
        self.assertFalse(alert_status["missing"])
        self.assertIn("routes", alert_status)
        remediation_status = benchmark_remediation_status(history_dir=self.history_dir)
        self.assertFalse(remediation_status["missing"])
        self.assertIn("proposal", remediation_status)
        alerts_text = (self.history_dir / "alerts_latest.md").read_text(encoding="utf-8", errors="replace")
        self.assertIn("Benchmark Gate Status", alerts_text)
        dashboard_text = (self.history_dir / "dashboard_latest.md").read_text(encoding="utf-8", errors="replace")
        self.assertIn("Benchmark Dashboard", dashboard_text)
        remediation_text = (self.history_dir / "remediation_latest.md").read_text(encoding="utf-8", errors="replace")
        self.assertIn("Benchmark Remediation Proposal", remediation_text)

    def test_benchmark_history_cli_run_history_compare(self) -> None:
        manifest, checkpoint_a, checkpoint_b = self._make_manifest_and_checkpoints()
        out = self.base / "latest_run.json"

        for label, checkpoint in (("base", checkpoint_a), ("tuned", checkpoint_b)):
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                    "run",
                    "--ckpt",
                    str(checkpoint),
                    "--manifest",
                    str(manifest),
                    "--out",
                    str(out),
                    "--label",
                    label,
                    "--history-dir",
                    str(self.history_dir),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, proc.returncode, proc.stderr)

        history = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "history",
                "--limit",
                "2",
                "--history-dir",
                str(self.history_dir),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, history.returncode, history.stderr)
        self.assertIn("History entries: 2", history.stdout)

        compare = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "compare",
                "--write",
                "--history-dir",
                str(self.history_dir),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, compare.returncode, compare.stderr)
        payload, _ = json.JSONDecoder().raw_decode(compare.stdout.lstrip())
        self.assertIn("primary_perplexity", payload)
        self.assertTrue((self.history_dir / "compare_latest.md").exists())

        cohorts = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "cohorts",
                "--history-dir",
                str(self.history_dir),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, cohorts.returncode, cohorts.stderr)
        self.assertIn("Cohorts: 1", cohorts.stdout)

        families = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "families",
                "--history-dir",
                str(self.history_dir),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, families.returncode, families.stderr)
        self.assertIn("Family slices: 2", families.stdout)

        chart = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "chart",
                "--history-dir",
                str(self.history_dir),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, chart.returncode, chart.stderr)
        self.assertIn("# Benchmark Trend Charts", chart.stdout)
        self.assertIn("Primary chart:", chart.stdout)

        family_chart = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "chart",
                "--history-dir",
                str(self.history_dir),
                "--family",
                "law_core",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, family_chart.returncode, family_chart.stderr)
        self.assertIn("# Benchmark Family Trend Charts", family_chart.stdout)
        self.assertIn("Family: law_core", family_chart.stdout)

        alerts = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "alerts",
                "--history-dir",
                str(self.history_dir),
                "--write",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, alerts.returncode, alerts.stderr)
        routed_payload, _ = json.JSONDecoder().raw_decode(alerts.stdout.lstrip())
        self.assertIn("routes", routed_payload)

        dashboard = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "dashboard",
                "--history-dir",
                str(self.history_dir),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, dashboard.returncode, dashboard.stderr)
        self.assertIn("# Benchmark Dashboard", dashboard.stdout)

        remediation = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "remediation",
                "--history-dir",
                str(self.history_dir),
                "--write",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, remediation.returncode, remediation.stderr)
        remediation_payload, _ = json.JSONDecoder().raw_decode(remediation.stdout.lstrip())
        self.assertIn("status", remediation_payload)
        self.assertTrue((self.history_dir / "remediation_latest.md").exists())

    def test_evaluate_benchmark_gate_flags_regression_and_family_failures(self) -> None:
        gate_config = {
            "max_primary_perplexity": 20.0,
            "max_valid_perplexity": 20.0,
            "max_train_perplexity": 20.0,
            "max_family_primary_perplexity": 15.0,
            "max_primary_regression_delta": 2.0,
            "max_valid_regression_delta": 2.0,
            "max_train_regression_delta": 2.0,
            "max_family_primary_regression_delta": 2.0,
            "max_primary_regression_ratio": 0.10,
            "max_valid_regression_ratio": 0.10,
            "max_train_regression_ratio": 0.10,
            "max_family_primary_regression_ratio": 0.10,
        }
        previous = {
            "architecture": "zero_native_char_attention_v1",
            "tokenizer_mode": "char",
            "cohort": "zero_native_char_attention_v1|char",
            "primary_perplexity": 10.0,
            "valid": {"perplexity": 10.0},
            "train": {"perplexity": 9.0},
            "families": [
                {"family": "law_core", "primary_perplexity": 9.5, "valid": {"perplexity": 9.5}, "train": {"perplexity": 9.0}},
            ],
        }
        latest = {
            "architecture": "zero_native_char_attention_v1",
            "tokenizer_mode": "char",
            "cohort": "zero_native_char_attention_v1|char",
            "primary_perplexity": 16.0,
            "valid": {"perplexity": 15.0},
            "train": {"perplexity": 14.0},
            "families": [
                {"family": "law_core", "primary_perplexity": 16.5, "valid": {"perplexity": 16.0}, "train": {"perplexity": 14.0}},
            ],
        }

        gate = evaluate_benchmark_gate(latest, previous=previous, gate_config=gate_config)
        self.assertEqual("fail", gate["status"])
        self.assertTrue(gate["failed"])
        kinds = {item["kind"] for item in gate["alerts"] if item["level"] == "fail"}
        self.assertIn("family_absolute_threshold", kinds)
        self.assertIn("regression_delta", kinds)
        self.assertIn("family_regression_delta", kinds)

        routed = route_benchmark_alerts(gate)
        self.assertEqual("fail", routed["status"])
        self.assertIn("family_watch", routed["route_counts"])
        self.assertIn("regression_watch", routed["route_counts"])

    def test_benchmark_gate_cli_strict_and_gate_command(self) -> None:
        manifest, checkpoint_a, _ = self._make_manifest_and_checkpoints()
        strict_gate = self._write_gate_config(
            {
                "max_primary_perplexity": 1.0,
                "max_valid_perplexity": 1.0,
                "max_train_perplexity": 1.0,
                "max_family_primary_perplexity": 1.0,
                "max_primary_regression_delta": 0.1,
                "max_valid_regression_delta": 0.1,
                "max_train_regression_delta": 0.1,
                "max_family_primary_regression_delta": 0.1,
                "max_primary_regression_ratio": 0.01,
                "max_valid_regression_ratio": 0.01,
                "max_train_regression_ratio": 0.01,
                "max_family_primary_regression_ratio": 0.01,
            },
            name="strict_gate.json",
        )
        out = self.base / "strict_run.json"

        run = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "run",
                "--ckpt",
                str(checkpoint_a),
                "--manifest",
                str(manifest),
                "--out",
                str(out),
                "--label",
                "strict",
                "--history-dir",
                str(self.history_dir),
                "--gate-config",
                str(strict_gate),
                "--strict-gate",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, run.returncode)
        self.assertTrue((self.history_dir / "gate_latest.json").exists())

        gate = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "gate",
                "--history-dir",
                str(self.history_dir),
                "--gate-config",
                str(strict_gate),
                "--strict",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, gate.returncode)
        payload = json.loads(gate.stdout)
        self.assertEqual("fail", payload["status"])

        alerts = subprocess.run(
            [
                sys.executable,
                str(ROOT / "ai_from_scratch" / "benchmark_history.py"),
                "alerts",
                "--history-dir",
                str(self.history_dir),
                "--gate-config",
                str(strict_gate),
                "--strict",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, alerts.returncode)
        routed_payload = json.loads(alerts.stdout)
        self.assertEqual("fail", routed_payload["status"])

    def test_benchmark_adaptive_curriculum_status_focuses_regressed_family(self) -> None:
        history_dir = self._write_history_rows(
            [
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
                {
                    "run_label": "regressed",
                    "architecture": "zero_native_char_attention_v1",
                    "tokenizer_mode": "char",
                    "cohort": "zero_native_char_attention_v1|char",
                    "primary_perplexity": 12.5,
                    "families": [
                        {"family": "law_core", "primary_perplexity": 11.0},
                        {"family": "strategy_context", "primary_perplexity": 12.0},
                    ],
                },
            ]
        )

        status = benchmark_adaptive_curriculum_status(
            history_dir=history_dir,
            architecture="zero_native_char_attention_v1",
            tokenizer_mode="char",
        )
        self.assertTrue(status["applied"])
        self.assertEqual("regression_focus", status["reason"])
        self.assertEqual("adaptive_regression_focus", status["recommended_stage"]["name"])
        self.assertEqual(["law_core"], status["recommended_stage"]["include_families"])
        self.assertGreaterEqual(status["recommended_stage"]["weight_scale"], 2)

    def test_benchmark_remediation_status_proposes_safe_candidate_run(self) -> None:
        history_dir = self._write_history_rows(
            [
                {
                    "run_label": "baseline",
                    "architecture": "zero_native_char_attention_v1",
                    "tokenizer_mode": "char",
                    "cohort": "zero_native_char_attention_v1|char",
                    "checkpoint": str((ROOT / "ai_from_scratch" / "checkpoint.json").resolve()),
                    "manifest_path": str((ROOT / "laws" / "model_benchmark_suite.json").resolve()),
                    "primary_perplexity": 10.0,
                    "gate": {"status": "pass", "failed": False, "alerts": [], "alert_count": 0, "failure_count": 0, "warning_count": 0},
                    "alert_routes": {"status": "pass", "failed": False, "alerts": [], "routes": [], "route_count": 0, "alert_count": 0},
                    "families": [
                        {"family": "law_core", "primary_perplexity": 8.0},
                        {"family": "strategy_context", "primary_perplexity": 12.0},
                    ],
                    "valid": {"perplexity": 10.0},
                    "train": {"perplexity": 9.0},
                },
                {
                    "run_label": "regressed",
                    "architecture": "zero_native_char_attention_v1",
                    "tokenizer_mode": "char",
                    "cohort": "zero_native_char_attention_v1|char",
                    "checkpoint": str((ROOT / "ai_from_scratch" / "checkpoint.json").resolve()),
                    "manifest_path": str((ROOT / "laws" / "model_benchmark_suite.json").resolve()),
                    "primary_perplexity": 13.0,
                    "gate": {
                        "status": "fail",
                        "failed": True,
                        "alerts": [{"level": "fail", "kind": "regression_delta", "family": "law_core"}],
                        "alert_count": 1,
                        "failure_count": 1,
                        "warning_count": 0,
                    },
                    "alert_routes": {
                        "status": "fail",
                        "failed": True,
                        "alerts": [{"route": "regression_watch", "family": "law_core"}],
                        "routes": [{"route": "regression_watch", "count": 1, "severity": "high", "action": "review_regression"}],
                        "route_count": 1,
                        "alert_count": 1,
                    },
                    "families": [
                        {"family": "law_core", "primary_perplexity": 11.5},
                        {"family": "strategy_context", "primary_perplexity": 12.0},
                    ],
                    "valid": {"perplexity": 12.5},
                    "train": {"perplexity": 11.5},
                },
            ]
        )

        status = benchmark_remediation_status(
            history_dir=history_dir,
            architecture="zero_native_char_attention_v1",
            tokenizer_mode="char",
        )
        self.assertEqual("proposed", status["status"])
        self.assertIn("law_core", status["targeted_families"])
        self.assertTrue(status["proposal"]["safe"])
        self.assertTrue(status["proposal"]["requires_manual_run"])
        self.assertIn("remediation_candidate", status["proposal"]["candidate_checkpoint"])
        self.assertIn("train.py", status["proposal"]["train_command"])

    def test_cohort_summary_and_chart_support_multiple_tokenizer_cohorts(self) -> None:
        manifest, checkpoint_a, checkpoint_b = self._make_manifest_and_checkpoints()
        checkpoint_c = self._make_byte_checkpoint(
            "zero ai byte cohort remains distinct",
            self.base / "checkpoint_c.json",
        )

        record_benchmark_run(
            str(checkpoint_a),
            manifest_path=str(manifest),
            out_path=str(self.base / "run_a.json"),
            history_dir=self.history_dir,
            label="char_base",
        )
        record_benchmark_run(
            str(checkpoint_b),
            manifest_path=str(manifest),
            out_path=str(self.base / "run_b.json"),
            history_dir=self.history_dir,
            label="char_tuned",
        )
        record_benchmark_run(
            str(checkpoint_c),
            manifest_path=str(manifest),
            out_path=str(self.base / "run_c.json"),
            history_dir=self.history_dir,
            label="byte_base",
        )

        cohorts_text = (self.history_dir / "cohorts_summary.md").read_text(encoding="utf-8", errors="replace")
        charts_text = (self.history_dir / "trend_charts.md").read_text(encoding="utf-8", errors="replace")
        family_charts_text = (self.history_dir / "family_trend_charts.md").read_text(encoding="utf-8", errors="replace")
        self.assertIn("zero_native_char_attention_v1|char", cohorts_text)
        self.assertIn("zero_native_char_attention_v1|byte", cohorts_text)
        self.assertIn("## zero_native_char_attention_v1|char", charts_text)
        self.assertIn("## zero_native_char_attention_v1|byte", charts_text)
        self.assertIn("Primary chart:", charts_text)
        self.assertIn("law_core", family_charts_text)
        self.assertIn("strategy_context", family_charts_text)


if __name__ == "__main__":
    unittest.main()

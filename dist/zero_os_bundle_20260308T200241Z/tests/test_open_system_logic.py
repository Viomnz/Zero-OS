import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.open_system_logic import (
    contradiction_score,
    evaluate_input,
    load_state,
    process_open_system_input,
    run_sandbox_experiment,
)


class OpenSystemLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_open_logic_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_contradiction_score_detects_pairs(self) -> None:
        out = contradiction_score("system is open and closed and always never stable")
        self.assertGreater(out["score"], 0.0)
        self.assertTrue(any(pair == ["open", "closed"] for pair in out["pairs"]))

    def test_process_accepts_low_contradiction_input(self) -> None:
        out = process_open_system_input(str(self.base), "system runtime stable pressure survive filter")
        self.assertTrue(out["ok"])
        self.assertTrue(out["update"]["accepted"])
        self.assertEqual(1, out["cycles"])
        self.assertTrue(out["signal_agreement"])

    def test_process_rejects_high_contradiction_input(self) -> None:
        out = process_open_system_input(
            str(self.base),
            "always never all none open closed true false stable unstable",
        )
        self.assertTrue(out["ok"])
        self.assertFalse(out["update"]["accepted"])
        self.assertFalse(out["signal_agreement"])
        state = load_state(str(self.base))
        self.assertEqual(1, state.rejected_updates)

    def test_detects_network_domain_weighting(self) -> None:
        out = contradiction_score("network router online offline allow block latency")
        self.assertEqual("network", out["domain"])
        self.assertGreaterEqual(out["weight"], 1.2)

    def test_detects_code_domain_weighting(self) -> None:
        out = contradiction_score("code compile crash test pass fail deterministic random")
        self.assertEqual("code", out["domain"])
        self.assertGreaterEqual(out["weight"], 1.1)

    def test_detects_security_domain_weighting(self) -> None:
        out = contradiction_score("security firewall trusted untrusted allow deny secure vulnerable")
        self.assertEqual("security", out["domain"])
        self.assertGreaterEqual(out["weight"], 1.3)

    def test_creates_new_model_after_persistent_conflict(self) -> None:
        for _ in range(3):
            out = process_open_system_input(
                str(self.base),
                "always never all none open closed true false unstable",
            )
        self.assertTrue(out["recovery"]["new_model_created"])
        self.assertEqual(2, out["model_version"])

    def test_evaluate_input_thresholds(self) -> None:
        out = evaluate_input(
            "system runtime stable pressure survive filter",
            thresholds={"logic": 0.6, "environment": 0.5, "survival": 0.5},
            contradiction_limit=0.5,
        )
        self.assertTrue(out["signal_agreement"])
        self.assertTrue(out["accepted"])

    def test_run_sandbox_experiment_returns_pass_fail(self) -> None:
        report = run_sandbox_experiment(str(self.base))
        self.assertTrue(report["ok"])
        self.assertIn("best", report)
        self.assertIn("pass", report)


if __name__ == "__main__":
    unittest.main()

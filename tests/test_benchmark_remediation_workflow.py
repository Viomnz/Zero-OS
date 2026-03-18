import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.approval_workflow import decide as approval_decide
from zero_os.benchmark_remediation_workflow import decide, execute, request, status


class BenchmarkRemediationWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_benchmark_remediation_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _proposal_payload(self) -> dict:
        candidate_checkpoint = self.base / "candidate_checkpoint.json"
        candidate_dataset = self.base / "candidate_checkpoint.dataset.json"
        candidate_report = self.base / "candidate_benchmark.json"
        touched = self.base / "train_touched.txt"
        return {
            "ok": True,
            "missing": False,
            "status": "proposed",
            "latest_run_label": "regressed-run",
            "cohort": "zero_native_char_attention_v1|char",
            "proposal": {
                "safe": True,
                "requires_manual_run": True,
                "candidate_checkpoint": str(candidate_checkpoint),
                "candidate_dataset": str(candidate_dataset),
                "candidate_benchmark_report": str(candidate_report),
                "suggested_run_label": "regressed-run-remediation-proposed",
                "train_argv": [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"Path(r'{touched}').write_text('train', encoding='utf-8'); "
                        f"Path(r'{candidate_checkpoint}').write_text('{{}}', encoding='utf-8'); "
                        f"Path(r'{candidate_dataset}').write_text('{{}}', encoding='utf-8')"
                    ),
                ],
                "benchmark_argv": [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path(r'{candidate_report}').write_text('{{}}', encoding='utf-8')",
                ],
            },
            "reasons": ["Gate status: fail"],
        }

    def test_request_creates_pending_approval_for_proposed_remediation(self) -> None:
        with patch("zero_os.benchmark_remediation_workflow._benchmark_history_api", return_value=lambda **kwargs: self._proposal_payload()):
            result = request(str(self.base))

        self.assertTrue(result["ok"])
        self.assertTrue(result["requested"])
        self.assertEqual("pending", result["approval"]["state"])
        self.assertEqual("benchmark_remediation_execute", result["approval"]["action"])

    def test_execute_runs_only_after_approval_and_records_result(self) -> None:
        with patch("zero_os.benchmark_remediation_workflow._benchmark_history_api", return_value=lambda **kwargs: self._proposal_payload()):
            requested = request(str(self.base))
            approval_id = requested["approval"]["id"]
            approval_decide(str(self.base), approval_id, True)
            result = execute(str(self.base))

        self.assertTrue(result["ok"])
        self.assertEqual("benchmark", result["execution"]["stage"])
        self.assertTrue((self.base / "candidate_checkpoint.json").exists())
        self.assertTrue((self.base / "candidate_benchmark.json").exists())
        self.assertTrue(result["status"]["execution"]["latest"]["ok"])
        self.assertTrue(result["status"]["approval"]["approved"])

    def test_decide_can_approve_pending_remediation_without_raw_id_lookup(self) -> None:
        with patch("zero_os.benchmark_remediation_workflow._benchmark_history_api", return_value=lambda **kwargs: self._proposal_payload()):
            requested = request(str(self.base))
            result = decide(str(self.base), True)

        self.assertTrue(result["ok"])
        self.assertEqual(requested["approval"]["id"], result["approval"]["id"])
        self.assertEqual("approved", result["approval"]["state"])


if __name__ == "__main__":
    unittest.main()

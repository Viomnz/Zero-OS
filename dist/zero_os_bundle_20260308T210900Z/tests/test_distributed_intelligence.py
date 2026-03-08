import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.distributed_intelligence import run_distributed_reasoning


class DistributedIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_distributed_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_distributed_consensus_pass(self) -> None:
        prompt = "create stable secure file with awareness pressure balance"
        candidate = (
            "I am aware of your request. This handles pressure and keeps balance with stability. "
            "I will create secure file steps."
        )
        out = run_distributed_reasoning(str(self.base), prompt, [candidate], node_count=3, agreement_threshold=0.67)
        self.assertTrue(out.selected_gate.accepted)
        self.assertTrue(out.report["agreement_pass"])
        self.assertEqual(3, out.report["node_count"])

    def test_distributed_consensus_detects_failures(self) -> None:
        prompt = "security action"
        bad = "always never true false disable firewall"
        out = run_distributed_reasoning(str(self.base), prompt, [bad], node_count=3, agreement_threshold=0.67)
        self.assertFalse(out.report["agreement_pass"])
        self.assertGreaterEqual(len(out.report["failed_nodes"]), 1)


if __name__ == "__main__":
    unittest.main()


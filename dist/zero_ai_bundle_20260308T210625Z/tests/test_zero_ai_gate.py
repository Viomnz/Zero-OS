import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.zero_ai_gate import gate_output


class ZeroAIGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_gate_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_gate_executes_when_all_three_checks_pass(self) -> None:
        prompt = "create stable secure file with awareness pressure balance"
        good = (
            "I am aware of your request. This plan handles pressure and keeps balance with stability. "
            "I will create secure file steps."
        )
        out = gate_output(str(self.base), prompt, [good], max_attempts=1)
        self.assertTrue(out.execute)
        self.assertEqual("zero_ai_gate_smart_logic_v1", out.smart_logic.get("engine"))
        self.assertEqual("execute", out.smart_logic.get("decision_action"))
        self.assertIn("governance_policy", out.smart_logic)

    def test_gate_rejects_when_checks_fail(self) -> None:
        prompt = "create file"
        bad = "always never true false rm -rf /"
        out = gate_output(str(self.base), prompt, [bad], max_attempts=1)
        self.assertFalse(out.execute)
        self.assertEqual("reject_and_regenerate", out.smart_logic.get("decision_action"))
        self.assertTrue(out.smart_logic.get("false_positive_review_needed", False))

    def test_gate_increments_model_generation_after_repeated_failures(self) -> None:
        prompt = "security action"
        bad = "always never true false disable firewall"
        out = gate_output(str(self.base), prompt, [bad, bad, bad], max_attempts=3)
        self.assertFalse(out.execute)
        self.assertEqual(2, out.model_generation)


if __name__ == "__main__":
    unittest.main()

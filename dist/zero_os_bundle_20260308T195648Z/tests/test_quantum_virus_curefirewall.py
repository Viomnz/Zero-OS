import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.cure_firewall import run_cure_firewall, verify_beacon
from zero_os.cure_firewall_agent import run_cure_firewall_agent, cure_firewall_agent_status


class QuantumVirusAgainstCureFirewallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_quantum_virus_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_quantum_virus_file_against_cure_firewall_core(self) -> None:
        infected = self.base / "quantum_virus_payload.py"
        infected.write_text(
            "# simulated quantum virus payload\n"
            "def mutate_wave_state():\n"
            "    return 'entangle|replicate|cloak'\n",
            encoding="utf-8",
        )

        result = run_cure_firewall(str(self.base), "quantum_virus_payload.py", pressure=95)
        self.assertTrue(result.activated)
        self.assertTrue(result.survived)
        self.assertIsNotNone(result.beacon_path)
        self.assertIsNotNone(result.backup_path)
        self.assertTrue(Path(result.backup_path).exists())

        ok, reason = verify_beacon(str(self.base), "quantum_virus_payload.py")
        self.assertTrue(ok, reason)

    def test_quantum_virus_against_cure_firewall_agent(self) -> None:
        infected = self.base / "quantum_agent_payload.txt"
        infected.write_text("quantum-virus-signature::phase-shift::self-modulate", encoding="utf-8")

        report = run_cure_firewall_agent(
            str(self.base),
            pressure=92,
            targets=["quantum_agent_payload.txt"],
            urls=["https://example.com/quantum-virus-sim"],
            verify=True,
        )
        self.assertTrue(report["ok"])
        self.assertEqual(1, report["file_targets"])
        self.assertGreaterEqual(report["file_survived"], 1)
        self.assertEqual(1, report["net_targets"])

        file_entry = report["files"][0]
        self.assertIn("backup", file_entry)
        self.assertTrue(bool(file_entry["backup"]))

        status = cure_firewall_agent_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertEqual(1, status["file_targets"])

        runtime_report = self.base / ".zero_os" / "runtime" / "cure_firewall_agent_report.json"
        self.assertTrue(runtime_report.exists())
        payload = json.loads(runtime_report.read_text(encoding="utf-8"))
        self.assertIn("files", payload)


if __name__ == "__main__":
    unittest.main()

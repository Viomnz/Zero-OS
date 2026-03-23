import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.ci_security_gates import commands_for_profile
from tools.security_gate import suites_for_profile


class SecurityGateProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="security_gate_profiles_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_ci_security_gate_profile_is_focused(self) -> None:
        suites = suites_for_profile("ci")
        joined = " ".join(" ".join(cmd) for cmd in suites)

        self.assertNotIn("discover", joined)
        self.assertIn("tests.test_security_tooling", joined)
        self.assertIn("tests.test_zero_ai_gate", joined)

    def test_full_security_gate_profile_preserves_broad_discover(self) -> None:
        suites = suites_for_profile("full")
        joined = " ".join(" ".join(cmd) for cmd in suites)

        self.assertIn("discover", joined)
        self.assertIn("tests.test_quantum_virus_curefirewall", joined)

    def test_ci_security_commands_drop_release_artifact_work(self) -> None:
        commands = commands_for_profile("ci")
        joined = " ".join(" ".join(cmd) for cmd in commands)

        self.assertIn("tools/security_gate.py --profile ci", joined)
        self.assertNotIn("sign_artifacts.py", joined)
        self.assertNotIn("release_verify.py", joined)
        self.assertNotIn("triad balance run", joined)

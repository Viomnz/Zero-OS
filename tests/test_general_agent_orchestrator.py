import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.general_agent_orchestrator import (
    general_agent_orchestrator_refresh,
    general_agent_orchestrator_status,
)


class GeneralAgentOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_general_agent_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os" / "state.json").parent.mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_status_reports_general_readiness_surface(self) -> None:
        status = general_agent_orchestrator_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertIn("required_subsystems", status)
        self.assertGreaterEqual(status["required_subsystem_count"], 1)
        self.assertIn(status["recommended_mode"], {"bounded_execute", "approval_gated_execute", "stabilize_subsystems", "expand_domain"})

    def test_refresh_assesses_request_domains(self) -> None:
        status = general_agent_orchestrator_refresh(
            str(self.base),
            request="open https://example.com and send a draft reminder update",
        )
        keys = {item["key"] for item in status["required_subsystems"]}
        self.assertIn("integration", keys)
        self.assertIn("communications", keys)
        self.assertIn("calendar_time", keys)
        self.assertEqual("assess", status["mode"])


if __name__ == "__main__":
    unittest.main()

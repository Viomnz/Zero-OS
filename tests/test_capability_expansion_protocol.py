import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.capability_expansion_protocol import capability_expansion_protocol_status
from zero_os.phase_runtime import zero_ai_runtime_run
from zero_os.self_continuity import zero_ai_self_continuity_update
from zero_os.zero_ai_identity import zero_ai_identity


class CapabilityExpansionProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_expansion_protocol_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _prime_runtime(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))
        runtime_dir = self.base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        (runtime_dir / "runtime_agent_state.json").write_text(
            json.dumps(
                {
                    "installed": True,
                    "auto_start_on_login": True,
                    "running": True,
                    "worker_pid": 7777,
                    "last_heartbeat_utc": now,
                    "poll_interval_seconds": 30,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (runtime_dir / "runtime_loop_state.json").write_text(
            json.dumps(
                {
                    "enabled": True,
                    "interval_seconds": 240,
                    "last_run_utc": now,
                    "next_run_utc": now,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            out = zero_ai_runtime_run(str(self.base))
        self.assertTrue(out["ok"])

    def test_protocol_status_writes_artifact_and_required_contracts(self) -> None:
        self._prime_runtime()

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            out = capability_expansion_protocol_status(str(self.base))

        self.assertTrue(out["ok"])
        self.assertGreaterEqual(len(out["required_contracts"]), 8)
        self.assertIn("installed_domain_count", out["summary"])
        self.assertTrue(any(item["stage"] == "typed_plan_steps" for item in out["required_contracts"]))
        self.assertTrue(any(item["key"] == "research" for item in out["candidate_domains"]))
        self.assertTrue(Path(out["path"]).exists())


if __name__ == "__main__":
    unittest.main()

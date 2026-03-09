import json
import shutil
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.self_continuity import zero_ai_self_continuity_update
from zero_os.zero_ai_evolution import (
    _runtime_snapshot,
    zero_ai_evolution_auto_run,
    zero_ai_evolution_canary,
    zero_ai_evolution_propose,
    zero_ai_evolution_rollback,
    zero_ai_evolution_status,
)
from zero_os.zero_ai_identity import zero_ai_identity


class ZeroAiEvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_evolution_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _prime_stable_evolution_ready(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))
        runtime_dir = self.base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        assistant_dir = self.base / ".zero_os" / "assistant"
        assistant_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        (runtime_dir / "phase_runtime_status.json").write_text(
            json.dumps(
                {
                    "ok": True,
                    "runtime_ready": True,
                    "runtime_score": 100.0,
                    "time_utc": now,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (runtime_dir / "runtime_agent_state.json").write_text(
            json.dumps(
                {
                    "installed": True,
                    "auto_start_on_login": True,
                    "running": True,
                    "worker_pid": 4321,
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
                    "interval_seconds": 180,
                    "last_run_utc": now,
                    "next_run_utc": now,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (assistant_dir / "autonomy_loop_state.json").write_text(
            json.dumps(
                {
                    "enabled": True,
                    "interval_seconds": 300,
                    "last_run_utc": now,
                    "next_run_utc": now,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_propose_generates_bounded_candidate(self) -> None:
        self._prime_stable_evolution_ready()

        result = zero_ai_evolution_propose(str(self.base))

        self.assertTrue(result["ok"])
        proposal = result["proposal"]
        self.assertTrue(proposal["candidate_available"])
        self.assertTrue(proposal["beneficial"])
        self.assertEqual(240, proposal["target_profile"]["runtime_loop_interval_seconds"])
        self.assertEqual(360, proposal["target_profile"]["autonomy_loop_interval_seconds"])

    def test_auto_run_promotes_candidate_and_updates_loop_intervals(self) -> None:
        self._prime_stable_evolution_ready()

        result = zero_ai_evolution_auto_run(str(self.base))

        self.assertTrue(result["ok"])
        self.assertTrue(result["changed"])
        status = result["status"]
        self.assertEqual(1, status["current_generation"])
        self.assertEqual(1, status["promoted_count"])
        self.assertEqual(240, status["current_profile"]["runtime_loop_interval_seconds"])
        self.assertEqual(360, status["current_profile"]["autonomy_loop_interval_seconds"])

    def test_canary_failure_keeps_baseline_profile(self) -> None:
        self._prime_stable_evolution_ready()
        stable_snapshot = _runtime_snapshot(str(self.base))
        unstable_snapshot = deepcopy(stable_snapshot)
        unstable_snapshot["profile"]["continuity_healthy"] = False
        unstable_snapshot["profile"]["same_system"] = False
        unstable_snapshot["profile"]["has_contradiction"] = True

        with patch("zero_os.zero_ai_evolution._runtime_snapshot", side_effect=[stable_snapshot, stable_snapshot, unstable_snapshot]):
            result = zero_ai_evolution_canary(str(self.base))

        self.assertFalse(result["ok"])
        status = zero_ai_evolution_status(str(self.base))
        self.assertEqual(180, status["current_profile"]["runtime_loop_interval_seconds"])
        self.assertEqual(300, status["current_profile"]["autonomy_loop_interval_seconds"])

    def test_rollback_restores_previous_profile(self) -> None:
        self._prime_stable_evolution_ready()
        evolved = zero_ai_evolution_auto_run(str(self.base))
        self.assertTrue(evolved["ok"])

        rollback = zero_ai_evolution_rollback(str(self.base))

        self.assertTrue(rollback["ok"])
        status = rollback["status"]
        self.assertEqual(180, status["current_profile"]["runtime_loop_interval_seconds"])
        self.assertEqual(300, status["current_profile"]["autonomy_loop_interval_seconds"])


if __name__ == "__main__":
    unittest.main()

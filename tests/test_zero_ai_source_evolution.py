import json
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.self_continuity import zero_ai_self_continuity_update
from zero_os.zero_ai_evolution import zero_ai_evolution_auto_run
from zero_os.zero_ai_identity import zero_ai_identity
from zero_os.zero_ai_source_evolution import (
    zero_ai_source_evolution_auto_run,
    zero_ai_source_evolution_propose,
    zero_ai_source_evolution_rollback,
    zero_ai_source_evolution_status,
)


class ZeroAiSourceEvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_source_evolution_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _stage_source_targets(self) -> None:
        for relative in (
            Path("src/zero_os/phase_runtime.py"),
            Path("src/zero_os/zero_ai_autonomy.py"),
        ):
            source = ROOT / relative
            target = self.base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source.read_text(encoding="utf-8", errors="replace")
            if relative.name == "phase_runtime.py":
                content = re.sub(
                    r'(def _runtime_loop_default\(\) -> dict:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
                    r"\g<1>180",
                    content,
                    count=1,
                    flags=re.S,
                )
            if relative.name == "zero_ai_autonomy.py":
                content = re.sub(
                    r'(def _loop_state_default\(\) -> dict:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
                    r"\g<1>300",
                    content,
                    count=1,
                    flags=re.S,
                )
            target.write_text(content, encoding="utf-8")

    def _prime_stable_evolution_generation(self) -> None:
        self._stage_source_targets()
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))
        runtime_dir = self.base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        assistant_dir = self.base / ".zero_os" / "assistant"
        assistant_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        (runtime_dir / "phase_runtime_status.json").write_text(
            json.dumps({"ok": True, "runtime_ready": True, "runtime_score": 100.0, "time_utc": now}, indent=2) + "\n",
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
            json.dumps({"enabled": True, "interval_seconds": 180, "last_run_utc": now, "next_run_utc": now}, indent=2) + "\n",
            encoding="utf-8",
        )
        (assistant_dir / "autonomy_loop_state.json").write_text(
            json.dumps({"enabled": True, "interval_seconds": 300, "last_run_utc": now, "next_run_utc": now}, indent=2) + "\n",
            encoding="utf-8",
        )
        evolution = zero_ai_evolution_auto_run(str(self.base))
        self.assertTrue(evolution["ok"])

    def test_source_evolution_requires_promoted_bounded_profile(self) -> None:
        self._stage_source_targets()

        status = zero_ai_source_evolution_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertFalse(status["source_evolution_ready"])
        self.assertFalse(status["proposal"]["candidate_available"])

    def test_source_evolution_propose_generates_guarded_candidate(self) -> None:
        self._prime_stable_evolution_generation()

        result = zero_ai_source_evolution_propose(str(self.base))

        self.assertTrue(result["ok"])
        proposal = result["proposal"]
        self.assertTrue(proposal["candidate_available"])
        self.assertTrue(proposal["beneficial"])
        self.assertEqual(2, len(proposal["mutations"]))

    def test_source_evolution_auto_run_updates_source_defaults_and_rollback_restores(self) -> None:
        self._prime_stable_evolution_generation()

        promoted = zero_ai_source_evolution_auto_run(str(self.base))

        self.assertTrue(promoted["ok"])
        self.assertTrue(promoted["changed"])
        phase_runtime = (self.base / "src/zero_os/phase_runtime.py").read_text(encoding="utf-8")
        autonomy = (self.base / "src/zero_os/zero_ai_autonomy.py").read_text(encoding="utf-8")
        self.assertIn('"interval_seconds": 240,', phase_runtime)
        self.assertIn('"interval_seconds": 360,', autonomy)

        rolled_back = zero_ai_source_evolution_rollback(str(self.base))

        self.assertTrue(rolled_back["ok"])
        phase_runtime_restored = (self.base / "src/zero_os/phase_runtime.py").read_text(encoding="utf-8")
        autonomy_restored = (self.base / "src/zero_os/zero_ai_autonomy.py").read_text(encoding="utf-8")
        self.assertIn('"interval_seconds": 180,', phase_runtime_restored)
        self.assertIn('"interval_seconds": 300,', autonomy_restored)


if __name__ == "__main__":
    unittest.main()

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

from zero_os.phase_runtime import zero_ai_runtime_run
from zero_os.fast_path_cache import clear_fast_path_cache
from zero_os.self_continuity import zero_ai_self_continuity_update
from zero_os.subsystem_controller_registry import controller_registry_status
from zero_os.zero_ai_identity import zero_ai_identity


class SubsystemControllerRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_fast_path_cache(namespace="tool_capability_registry_status")
        clear_fast_path_cache(namespace="controller_registry_status")
        clear_fast_path_cache(namespace="zero_ai_capability_map_status")
        self.tempdir = tempfile.mkdtemp(prefix="zero_controller_registry_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        clear_fast_path_cache(namespace="tool_capability_registry_status")
        clear_fast_path_cache(namespace="controller_registry_status")
        clear_fast_path_cache(namespace="zero_ai_capability_map_status")
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

    def test_registry_groups_subsystems_and_persists_status(self) -> None:
        self._prime_runtime()

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            out = controller_registry_status(str(self.base))

        self.assertTrue(out["ok"])
        self.assertTrue(Path(out["path"]).exists())
        self.assertGreaterEqual(out["summary"]["subsystem_count"], 9)

        subsystems = {item["key"]: item for item in out["subsystems"]}
        self.assertEqual("autonomous", subsystems["observation"]["control_level"])
        self.assertIn("zero ai workspace status", subsystems["observation"]["commands"])
        self.assertIn("zero ai flow status", subsystems["observation"]["commands"])
        self.assertEqual("autonomous", subsystems["reasoning"]["control_level"])
        self.assertIn("zero ai contradiction status", subsystems["reasoning"]["commands"])
        self.assertIn("general_agent", subsystems)
        self.assertIn("zero ai general agent status", subsystems["general_agent"]["commands"])
        self.assertIn("pressure", subsystems)
        self.assertIn("zero ai pressure status", subsystems["pressure"]["commands"])
        self.assertIn("expansion", subsystems)
        self.assertIn("zero ai capability expansion protocol status", subsystems["expansion"]["commands"])
        self.assertIn("zero ai domain pack factory status", subsystems["expansion"]["commands"])
        self.assertIn("communications", subsystems)
        self.assertIn("zero ai communications status", subsystems["communications"]["commands"])
        self.assertIn("calendar_time", subsystems)
        self.assertIn("zero ai calendar status", subsystems["calendar_time"]["commands"])
        self.assertEqual("autonomous", subsystems["runtime"]["control_level"])
        self.assertEqual([], subsystems["runtime"]["missing_functions"])
        self.assertIn("zero ai runtime status", subsystems["runtime"]["commands"])
        self.assertTrue(any("app package" in step.lower() for step in out["highest_value_steps"]))
        self.assertIn("tool_registry_cache_hit", out["summary"])
        self.assertIn("capability_map_cache_hit", out["summary"])

    def test_registry_surfaces_missing_runtime_functions_without_runtime_baseline(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))

        out = controller_registry_status(str(self.base))

        subsystems = {item["key"]: item for item in out["subsystems"]}
        self.assertIn("background runtime agent", subsystems["runtime"]["missing_functions"])
        self.assertIn("scheduled runtime loop", subsystems["runtime"]["missing_functions"])
        self.assertIn("runtime orchestration baseline", subsystems["runtime"]["missing_functions"])

    def test_registry_uses_fast_path_when_inputs_are_unchanged(self) -> None:
        self._prime_runtime()
        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            first = controller_registry_status(str(self.base))

        with patch("zero_os.subsystem_controller_registry._build_controller_registry_status", side_effect=AssertionError("should use cache")):
            second = controller_registry_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])


if __name__ == "__main__":
    unittest.main()

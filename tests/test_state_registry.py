import json
import subprocess
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.state_registry import (
    boot_state_registry,
    flush_state_registry,
    get_state_store,
    put_state_store,
    state_registry_status,
    update_state_store,
)


class StateRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_state_registry_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _write_json_in_subprocess(self, path: Path, payload: dict) -> None:
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "target = Path(sys.argv[1])\n"
            "target.parent.mkdir(parents=True, exist_ok=True)\n"
            "payload = json.loads(sys.argv[2])\n"
            "target.write_text(json.dumps(payload, indent=2) + '\\n', encoding='utf-8')\n"
        )
        subprocess.run(
            [sys.executable, "-c", script, str(path), json.dumps(payload)],
            check=True,
        )

    def _run_repeated_writer_in_subprocess(self, path: Path, count: int, delay_seconds: float) -> subprocess.Popen:
        script = (
            "import json, sys, time\n"
            "from pathlib import Path\n"
            "target = Path(sys.argv[1])\n"
            "count = int(sys.argv[2])\n"
            "delay = float(sys.argv[3])\n"
            "target.parent.mkdir(parents=True, exist_ok=True)\n"
            "for index in range(count):\n"
            "    payload = {\"writer\": \"runtime_agent\", \"tick\": index, \"ok\": True}\n"
            "    target.write_text(json.dumps(payload, indent=2) + '\\n', encoding='utf-8')\n"
            "    time.sleep(delay)\n"
        )
        return subprocess.Popen(
            [sys.executable, "-c", script, str(path), str(count), str(delay_seconds)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def test_boot_state_registry_preloads_hot_stores(self) -> None:
        runtime = self.base / ".zero_os" / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "runtime_loop_state.json").write_text("{}\n", encoding="utf-8")

        boot = boot_state_registry(str(self.base))
        status = state_registry_status(str(self.base))

        self.assertTrue(boot["ok"])
        self.assertGreaterEqual(status["loaded_store_count"], 1)
        self.assertTrue(status["stores"]["runtime_loop"]["loaded"])

    def test_put_state_store_updates_memory_first_and_flushes(self) -> None:
        payload = {"ok": True, "value": 3}

        put_state_store(str(self.base), "zero_engine_status", payload)
        in_memory = get_state_store(str(self.base), "zero_engine_status", {})
        flushed = flush_state_registry(str(self.base), names=["zero_engine_status"])

        self.assertEqual(payload, in_memory)
        self.assertTrue(flushed["ok"])
        self.assertTrue((self.base / ".zero_os" / "runtime" / "zero_engine_status.json").exists())

    def test_get_state_store_refreshes_clean_entry_after_external_write(self) -> None:
        path = self.base / ".zero_os" / "runtime" / "zero_engine_status.json"

        update_state_store(str(self.base), "zero_engine_status", lambda current: {"version": 1})
        flush_state_registry(str(self.base), names=["zero_engine_status"])
        self.assertEqual(1, get_state_store(str(self.base), "zero_engine_status", {}).get("version"))

        path.write_text('{\n  "version": 2\n}\n', encoding="utf-8")

        refreshed = get_state_store(str(self.base), "zero_engine_status", {})
        self.assertEqual(2, refreshed.get("version"))

    def test_flush_state_registry_detects_external_revision_conflict(self) -> None:
        path = self.base / ".zero_os" / "runtime" / "zero_engine_status.json"

        update_state_store(str(self.base), "zero_engine_status", lambda current: {"version": 1})
        flush_state_registry(str(self.base), names=["zero_engine_status"])
        update_state_store(str(self.base), "zero_engine_status", lambda current: {"version": 2})

        path.write_text('{\n  "version": 3\n}\n', encoding="utf-8")

        flushed = flush_state_registry(str(self.base), names=["zero_engine_status"])
        status = state_registry_status(str(self.base))
        refreshed = get_state_store(str(self.base), "zero_engine_status", {})

        self.assertTrue(flushed["ok"])
        self.assertTrue(status["stores"]["zero_engine_status"]["conflict"])
        self.assertEqual(3, refreshed.get("version"))

    def test_cross_process_phase_runtime_status_refreshes_clean_cache(self) -> None:
        path = self.base / ".zero_os" / "runtime" / "phase_runtime_status.json"

        update_state_store(str(self.base), "phase_runtime_status", lambda current: {"writer": "direct_command", "run": 1})
        flush_state_registry(str(self.base), names=["phase_runtime_status"])

        self._write_json_in_subprocess(path, {"writer": "runtime_agent", "run": 2, "ok": True})

        refreshed = get_state_store(str(self.base), "phase_runtime_status", {})
        self.assertEqual("runtime_agent", refreshed.get("writer"))
        self.assertEqual(2, refreshed.get("run"))

    def test_cross_process_zero_engine_status_conflict_is_detected(self) -> None:
        path = self.base / ".zero_os" / "runtime" / "zero_engine_status.json"

        update_state_store(str(self.base), "zero_engine_status", lambda current: {"writer": "runtime", "version": 1})
        flush_state_registry(str(self.base), names=["zero_engine_status"])
        update_state_store(str(self.base), "zero_engine_status", lambda current: {"writer": "direct_command", "version": 2})

        self._write_json_in_subprocess(path, {"writer": "runtime_agent", "version": 3})

        flushed = flush_state_registry(str(self.base), names=["zero_engine_status"])
        status = state_registry_status(str(self.base))
        refreshed = get_state_store(str(self.base), "zero_engine_status", {})

        self.assertTrue(flushed["ok"])
        self.assertTrue(status["stores"]["zero_engine_status"]["conflict"])
        self.assertEqual("runtime_agent", refreshed.get("writer"))

    def test_repeated_cross_process_contention_preserves_external_truth(self) -> None:
        path = self.base / ".zero_os" / "runtime" / "phase_runtime_status.json"

        update_state_store(str(self.base), "phase_runtime_status", lambda current: {"writer": "direct_command", "tick": -1})
        flush_state_registry(str(self.base), names=["phase_runtime_status"])

        writer = self._run_repeated_writer_in_subprocess(path, count=30, delay_seconds=0.01)
        conflict_total = 0
        try:
            for tick in range(6):
                update_state_store(
                    str(self.base),
                    "phase_runtime_status",
                    lambda current, current_tick=tick: {"writer": "direct_command", "tick": current_tick},
                )
                time.sleep(0.015)
                flush_state_registry(str(self.base), names=["phase_runtime_status"])
                conflict_total += int(state_registry_status(str(self.base))["conflict_store_count"])
                time.sleep(0.005)
        finally:
            writer.wait(timeout=10)

        refreshed = get_state_store(str(self.base), "phase_runtime_status", {})

        self.assertGreaterEqual(conflict_total, 1)
        self.assertEqual("runtime_agent", refreshed.get("writer"))
        self.assertGreaterEqual(int(refreshed.get("tick", -1)), 0)

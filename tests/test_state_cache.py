import json
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

from zero_os.state_cache import clear_state_cache, flush_state_writes, load_json_state, queue_json_state, state_cache_status


class StateCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_state_cache_")
        self.base = Path(self.tempdir)
        clear_state_cache()

    def tearDown(self) -> None:
        clear_state_cache()
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_load_json_state_uses_cache_until_file_changes(self) -> None:
        path = self.base / "state.json"
        path.write_text(json.dumps({"value": 1}) + "\n", encoding="utf-8")

        first = load_json_state(path, {})
        first_status = state_cache_status()
        second = load_json_state(path, {})
        second_status = state_cache_status()

        self.assertEqual({"value": 1}, first)
        self.assertEqual({"value": 1}, second)
        self.assertEqual(1, first_status["json_cache_miss_count"])
        self.assertEqual(1, second_status["json_cache_hit_count"])

        time.sleep(0.02)
        path.write_text(json.dumps({"value": 2}) + "\n", encoding="utf-8")
        third = load_json_state(path, {})
        third_status = state_cache_status()

        self.assertEqual({"value": 2}, third)
        self.assertEqual(2, third_status["json_cache_miss_count"])

    def test_queue_json_state_batches_until_flush(self) -> None:
        path = self.base / "queued.json"

        queue_json_state(path, {"value": 7})
        queued_status = state_cache_status()

        self.assertFalse(path.exists())
        self.assertEqual({"value": 7}, load_json_state(path, {}))
        self.assertEqual(1, queued_status["pending_write_count"])
        self.assertEqual(1, queued_status["dirty_path_count"])

        flushed = flush_state_writes(paths=[path])
        final_status = state_cache_status()

        self.assertTrue(flushed["ok"])
        self.assertEqual(1, flushed["flushed_count"])
        self.assertTrue(path.exists())
        self.assertEqual({"value": 7}, load_json_state(path, {}))
        self.assertEqual(0, final_status["pending_write_count"])
        self.assertEqual(1, final_status["json_disk_write_count"])

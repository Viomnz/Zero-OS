import shutil
import sys
import tempfile
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
)


class StateRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_state_registry_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

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

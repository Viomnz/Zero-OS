import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.runtime_subsystem_registry import (
    RuntimeSubsystemAdapter,
    register_runtime_subsystem_adapter,
    run_runtime_subsystems,
    unregister_runtime_subsystem_adapter,
)
from zero_os.subsystem_registry import subsystem_registry_status


class RuntimeSubsystemRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_runtime_subsystem_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        unregister_runtime_subsystem_adapter("unit_runtime")
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_runtime_subsystem_registry_runs_registered_adapter(self) -> None:
        register_runtime_subsystem_adapter(
            RuntimeSubsystemAdapter(
                name="unit_runtime",
                order=15,
                run=lambda cwd, context: {
                    "updates": {"unit_runtime": {"ok": True, "cwd": cwd}},
                    "runtime_checks": {"unit_runtime": True},
                    "context": {"unit_runtime_seen": True},
                },
            )
        )

        result = run_runtime_subsystems(str(self.base))

        self.assertTrue(result["ok"])
        self.assertEqual("universal", result["mode"])
        self.assertEqual("flattened", result["scheduler"])
        self.assertIn("unit_runtime", result["adapter_names"])
        self.assertIn("unit_runtime", result["updates"])
        self.assertIn("zero_engine", result["updates"])
        self.assertIn("zero_engine_background", result["updates"])
        self.assertTrue(result["runtime_checks"]["unit_runtime"])
        self.assertTrue(result["runtime_checks"]["zero_engine"])
        self.assertTrue(result["context"]["unit_runtime_seen"])
        registry = subsystem_registry_status()
        self.assertIn("runtime", registry["planes"])
        self.assertIn("unit_runtime", registry["planes"]["runtime"]["names"])


if __name__ == "__main__":
    unittest.main()

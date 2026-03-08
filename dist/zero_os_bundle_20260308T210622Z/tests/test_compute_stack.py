import json
import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.compute_runtime import initialize_compute_runtime
from zero_os.hal import ComputeHAL, WorkloadSpec
from zero_os.performance import HardwareInfo, compute_tier_from_hardware, effective_profile
from zero_os.scheduler import SchedulerRouter


class ComputeStackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_compute_")
        self.base = Path(self.tempdir)
        (self.base / "zero_os_config").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_tier_detection(self) -> None:
        self.assertEqual("tier1", compute_tier_from_hardware(HardwareInfo(cpu_cores=2, memory_gb=4)))
        self.assertEqual("tier2", compute_tier_from_hardware(HardwareInfo(cpu_cores=16, memory_gb=64)))
        self.assertEqual(
            "tier3",
            compute_tier_from_hardware(HardwareInfo(cpu_cores=16, memory_gb=64, distributed_ready=True)),
        )
        self.assertEqual(
            "tier4",
            compute_tier_from_hardware(HardwareInfo(cpu_cores=16, memory_gb=64, distributed_ready=True, quantum_ready=True)),
        )

    def test_effective_profile_legacy_and_tier(self) -> None:
        info = HardwareInfo(cpu_cores=8, memory_gb=16)
        tier, profile = effective_profile("auto", info)
        self.assertEqual("tier2", tier)
        self.assertEqual("high", profile)

        tier, profile = effective_profile("tier1", info)
        self.assertEqual("tier1", tier)
        self.assertEqual("low", profile)

        tier, profile = effective_profile("balanced", info)
        self.assertEqual("tier2", tier)
        self.assertEqual("balanced", profile)

    def test_hal_and_scheduler(self) -> None:
        hw = HardwareInfo(cpu_cores=32, memory_gb=128, gpu_count=4, distributed_ready=True)
        hal = ComputeHAL()
        target = hal.allocate(WorkloadSpec(lane="distributed", distributed=True), hw, "tier3")
        self.assertEqual("distributed-cluster", target.backend)

        sched = SchedulerRouter()
        decision = sched.route("distributed", hw, "tier3", {"fallback": "distributed-cluster"})
        self.assertEqual("cluster", decision.queue)
        self.assertEqual("distributed-cluster", decision.backend)

    def test_initialize_runtime_writes_file(self) -> None:
        profiles = {
            "tier1": {"fallback": "cpu-local"},
            "tier2": {"fallback": "gpu-local"},
            "tier3": {"fallback": "distributed-cluster"},
            "tier4": {"fallback": "quantum-hybrid"},
        }
        (self.base / "zero_os_config" / "compute_profiles.yaml").write_text(
            json.dumps(profiles), encoding="utf-8"
        )

        os.environ["ZERO_OS_DISTRIBUTED_READY"] = "true"
        try:
            result = initialize_compute_runtime(str(self.base), "auto")
        finally:
            os.environ.pop("ZERO_OS_DISTRIBUTED_READY", None)

        self.assertIn(result["tier"], {"tier1", "tier2", "tier3", "tier4"})
        runtime = self.base / ".zero_os" / "runtime" / "compute_runtime.json"
        self.assertTrue(runtime.exists())
        payload = json.loads(runtime.read_text(encoding="utf-8"))
        self.assertIn("scheduler", payload)
        self.assertIn("interactive", payload["scheduler"])


if __name__ == "__main__":
    unittest.main()

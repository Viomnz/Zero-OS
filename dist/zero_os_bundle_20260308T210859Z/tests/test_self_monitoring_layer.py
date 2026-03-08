import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.self_monitoring_layer import monitor_system_health


class _GateStub:
    def __init__(self, avg_conf: float, attempts_used: int, attempt_limit: int, rejection_streak: int = 0) -> None:
        self.self_monitor = {"avg_confidence_recent": avg_conf, "rejection_streak": rejection_streak}
        self.resource = {"attempts_used": attempts_used, "attempt_limit": attempt_limit}


class SelfMonitoringLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_selfmon_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_healthy_system_passes(self) -> None:
        (self.runtime / "internal_zero_reasoner_memory.json").write_text(
            json.dumps({"success_patterns": [], "failure_patterns": []}),
            encoding="utf-8",
        )
        gate = _GateStub(avg_conf=0.9, attempts_used=2, attempt_limit=9)
        out = monitor_system_health(
            str(self.base),
            "status",
            gate,
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertTrue(out["healthy"])

    def test_unhealthy_system_blocks(self) -> None:
        (self.runtime / "internal_zero_reasoner_memory.json").write_text(
            "{bad json",
            encoding="utf-8",
        )
        gate = _GateStub(avg_conf=0.2, attempts_used=9, attempt_limit=9, rejection_streak=5)
        out = monitor_system_health(
            str(self.base),
            "status",
            gate,
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertFalse(out["healthy"])
        self.assertTrue(out["responses"]["diagnostic_scan"])


if __name__ == "__main__":
    unittest.main()


import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.resource_constraint_layer import evaluate_resource_constraints


class _GateStub:
    def __init__(self, attempts_used: int, attempt_limit: int, elapsed_ms: int = 50, deadline_ms: int = 220) -> None:
        self.resource = {
            "attempts_used": attempts_used,
            "attempt_limit": attempt_limit,
            "elapsed_ms": elapsed_ms,
            "deadline_ms": deadline_ms,
        }


class ResourceConstraintLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_resource_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_approve_under_normal_pressure(self) -> None:
        gate = _GateStub(attempts_used=2, attempt_limit=9, elapsed_ms=40, deadline_ms=220)
        out = evaluate_resource_constraints(
            str(self.base),
            "status",
            gate,
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertEqual("approve", out["decision"])

    def test_reject_under_high_pressure(self) -> None:
        # Seed large trace history to increase storage pressure.
        trace = {"history": [{"i": i} for i in range(1400)]}
        (self.runtime / "decision_trace.json").write_text(json.dumps(trace), encoding="utf-8")
        gate = _GateStub(attempts_used=9, attempt_limit=9, elapsed_ms=220, deadline_ms=220)
        out = evaluate_resource_constraints(
            str(self.base),
            "x" * 5000,
            gate,
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertEqual("reject", out["decision"])


if __name__ == "__main__":
    unittest.main()


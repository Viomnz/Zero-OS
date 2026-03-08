import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.safe_state_layer import evaluate_safe_state


class _Gate:
    def __init__(self, accepted: bool, fallback_mode: str, resource: dict):
        self.accepted = accepted
        self.fallback_mode = fallback_mode
        self.resource = resource


class SafeStateLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_safe_state_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_continue_when_stable(self) -> None:
        gate = _Gate(True, "none", {"attempt_limit": 9, "attempts_used": 1, "time_abort": False})
        out = evaluate_safe_state(str(self.base), gate, {"degraded": False, "score": 0}, {"actions": {}})
        self.assertFalse(out["enter_safe_state"])
        self.assertEqual("continue", out["action"])
        self.assertFalse(out["controlled_mode"]["restrict_actions"])
        self.assertEqual("normal", out["state"]["mode"])

    def test_enter_safe_state_on_signal_corruption(self) -> None:
        gate = _Gate(False, "signal_reliability_block", {"attempt_limit": 9, "attempts_used": 0, "time_abort": False})
        out = evaluate_safe_state(str(self.base), gate, {"degraded": False, "score": 1}, {"actions": {}})
        self.assertTrue(out["enter_safe_state"])
        self.assertEqual("return_to_baseline", out["action"])
        self.assertTrue(out["controlled_mode"]["restrict_actions"])
        self.assertEqual("safe", out["state"]["mode"])

    def test_enter_safe_state_on_resource_exhaustion(self) -> None:
        gate = _Gate(False, "best_available", {"attempt_limit": 9, "attempts_used": 9, "time_abort": True})
        out = evaluate_safe_state(str(self.base), gate, {"degraded": False, "score": 1}, {"actions": {}})
        self.assertTrue(out["enter_safe_state"])
        self.assertIn("resource_exhaustion", out["triggers"])

    def test_recovery_state_updates_after_safe(self) -> None:
        gate_bad = _Gate(False, "signal_reliability_block", {"attempt_limit": 9, "attempts_used": 9, "time_abort": True})
        first = evaluate_safe_state(str(self.base), gate_bad, {"degraded": True, "score": 3}, {"actions": {}})
        self.assertEqual("safe", first["state"]["mode"])
        gate_ok = _Gate(True, "none", {"attempt_limit": 9, "attempts_used": 1, "time_abort": False})
        second = evaluate_safe_state(str(self.base), gate_ok, {"degraded": False, "score": 0}, {"actions": {}})
        self.assertEqual("normal", second["state"]["mode"])
        self.assertTrue(bool(second["state"]["last_recovered_utc"]))


if __name__ == "__main__":
    unittest.main()

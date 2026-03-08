import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.context_awareness import detect_context


class ContextAwarenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_context_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_normal_context(self) -> None:
        out = detect_context(str(self.base), "status check", "human")
        self.assertTrue(out["ok"])
        self.assertEqual("normal", out["reasoning_parameters"]["priority_mode"])
        self.assertEqual(9, out["reasoning_parameters"]["max_candidates"])

    def test_emergency_context_switches_parameters(self) -> None:
        (self.runtime / "zero_ai_output.txt").write_text(
            "[ENTERED_SAFE_STATE]\n[REJECTED_BY_SECURITY_INTEGRITY]\n[REJECTED_BY_SECURITY_INTEGRITY]\n[REJECTED_BY_INTERFACE]\n",
            encoding="utf-8",
        )
        (self.runtime / "zero_ai_heartbeat.json").write_text(
            json.dumps({"status": "running", "checkpoint_loaded": True}),
            encoding="utf-8",
        )
        out = detect_context(str(self.base), "status check", "human")
        self.assertTrue(out["context"]["context_changed"])
        self.assertEqual("safety", out["reasoning_parameters"]["priority_mode"])
        self.assertEqual(6, out["reasoning_parameters"]["max_candidates"])
        self.assertEqual("adaptive", out["reasoning_parameters"]["force_profile"])


if __name__ == "__main__":
    unittest.main()


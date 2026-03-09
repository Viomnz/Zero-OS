import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.self_continuity import (
    zero_ai_self_continuity_status,
    zero_ai_self_continuity_update,
    zero_ai_self_inspect_refresh,
)
from zero_os.zero_ai_identity import zero_ai_identity


class ZeroAISelfContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_self_continuity_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_builds_persistent_self_reference_state(self) -> None:
        zero_ai_identity(str(self.base))
        out = zero_ai_self_continuity_status(str(self.base))
        self.assertTrue(out["ok"])
        self.assertEqual("zero-ai-core", out["system"]["persistent_self_id"])
        self.assertTrue(out["continuity"]["same_system"])

    def test_tracks_recursive_state_updates(self) -> None:
        zero_ai_identity(str(self.base))
        first = zero_ai_self_continuity_update(str(self.base))
        second = zero_ai_self_continuity_update(str(self.base))
        self.assertGreater(
            second["recursive_state_tracking"]["state_versions"],
            first["recursive_state_tracking"]["state_versions"],
        )
        self.assertGreaterEqual(second["history_events"], 2)

    def test_detects_identity_contradiction(self) -> None:
        zero_ai_identity(str(self.base))
        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "self_mutation_engine"
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        out = zero_ai_self_continuity_update(str(self.base))
        self.assertTrue(out["contradiction_detection"]["has_contradiction"])
        self.assertIn("identity_classification_changed", out["contradiction_detection"]["issues"])
        self.assertIn("identity_claims_rsi", out["contradiction_detection"]["issues"])

    def test_self_inspect_refresh_returns_prioritized_steps(self) -> None:
        zero_ai_identity(str(self.base))
        out = zero_ai_self_inspect_refresh(str(self.base))
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(len(out["highest_value_steps"]), 1)
        self.assertIn("next_priority", out)


if __name__ == "__main__":
    unittest.main()

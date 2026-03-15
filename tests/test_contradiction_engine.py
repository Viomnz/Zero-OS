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

from zero_os.contradiction_engine import contradiction_engine_status, review_run


class ContradictionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_contradiction_engine_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_review_run_allows_stable_status_branch(self) -> None:
        review = review_run(
            str(self.base),
            "check system status",
            {
                "intent": {"intent": "status"},
                "steps": [{"kind": "system_status", "target": "health"}],
            },
            [{"ok": True, "kind": "system_status", "result": {"ok": True}}],
            run_ok=True,
        )

        self.assertEqual("allow", review["decision"])
        self.assertEqual(0, review["contradiction_count"])
        self.assertGreaterEqual(len(review["stable_claims"]), 1)

    def test_review_run_holds_when_self_contradiction_is_active(self) -> None:
        runtime_dir = self.base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "zero_ai_self_continuity.json").write_text(
            json.dumps(
                {
                    "continuity": {"same_system": True, "continuity_score": 82.0},
                    "contradiction_detection": {
                        "has_contradiction": True,
                        "issues": ["identity_missing_anti_contradiction_constraint"],
                    },
                    "policy_memory": {"contradiction_event_count": 1},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        review = review_run(
            str(self.base),
            "check system status",
            {
                "intent": {"intent": "status"},
                "steps": [{"kind": "system_status", "target": "health"}],
            },
            [{"ok": True, "kind": "system_status", "result": {"ok": True}}],
            run_ok=True,
        )

        self.assertEqual("hold", review["decision"])
        self.assertGreater(review["contradiction_count"], 0)
        self.assertIn("Resolve self contradictions", review["recommended_action"])

    def test_status_reflects_latest_review(self) -> None:
        review_run(
            str(self.base),
            "check system status",
            {
                "intent": {"intent": "status"},
                "steps": [{"kind": "system_status", "target": "health"}],
            },
            [{"ok": True, "kind": "system_status", "result": {"ok": True}}],
            run_ok=True,
        )

        status = contradiction_engine_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertEqual("allow", status["last_decision"])
        self.assertEqual(0, status["last_contradiction_count"])
        self.assertTrue(Path(status["path"]).exists())


if __name__ == "__main__":
    unittest.main()

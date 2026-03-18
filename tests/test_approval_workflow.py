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

from zero_os.approval_workflow import cleanup_expired, decide, latest_approved, latest_pending, mark_executed, request_approval, status


class ApprovalWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_approval_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_latest_approved_matches_exact_run_and_target_and_is_single_use(self) -> None:
        target = {"url": "https://example.com", "action": "click", "selector": "body"}
        approval = request_approval(
            str(self.base),
            "browser_action",
            "need approval",
            {"run_id": "run-1", "target": target},
        )["approval"]
        decided = decide(str(self.base), approval["id"], True)

        self.assertTrue(decided["ok"])
        self.assertTrue(latest_approved(str(self.base), "browser_action", run_id="run-1", target=target)["ok"])
        self.assertFalse(
            latest_approved(
                str(self.base),
                "browser_action",
                run_id="run-1",
                target={"url": "https://other.example", "action": "click", "selector": "body"},
            )["ok"]
        )

        executed = mark_executed(str(self.base), approval["id"], outcome="ok")
        self.assertTrue(executed["ok"])
        self.assertFalse(latest_approved(str(self.base), "browser_action", run_id="run-1", target=target)["ok"])
        self.assertEqual("executed", status(str(self.base))["items"][-1]["state"])

    def test_decide_refuses_to_rewrite_final_state(self) -> None:
        approval = request_approval(str(self.base), "self_repair", "need approval", {"run_id": "run-1", "target": "runtime"})["approval"]
        first = decide(str(self.base), approval["id"], True)
        second = decide(str(self.base), approval["id"], False)

        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertEqual("approval already decided", second["reason"])
        self.assertEqual("approved", status(str(self.base))["items"][-1]["state"])

    def test_latest_pending_matches_exact_run_and_target(self) -> None:
        target = {"url": "https://example.com", "action": "click", "selector": "body"}
        request_approval(
            str(self.base),
            "browser_action",
            "need approval",
            {"run_id": "run-1", "target": target},
        )

        self.assertTrue(latest_pending(str(self.base), "browser_action", run_id="run-1", target=target)["ok"])
        self.assertFalse(latest_pending(str(self.base), "browser_action", run_id="run-2", target=target)["ok"])

    def test_cleanup_expired_marks_stale_pending_approval(self) -> None:
        approval = request_approval(str(self.base), "self_repair", "need approval", {"run_id": "run-1", "target": "runtime"})["approval"]
        path = self.base / ".zero_os" / "assistant" / "approvals.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["items"][0]["expires_utc"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        cleaned = cleanup_expired(str(self.base))

        self.assertTrue(cleaned["ok"])
        self.assertEqual(1, cleaned["expired_count"])
        self.assertFalse(latest_pending(str(self.base), "self_repair", run_id="run-1", target="runtime")["ok"])
        self.assertEqual("expired", status(str(self.base))["items"][-1]["state"])
        self.assertEqual(0, status(str(self.base))["pending_count"])

    def test_latest_approved_ignores_expired_unused_approval(self) -> None:
        approval = request_approval(str(self.base), "store_install", "need approval", {"run_id": "run-1", "target": "nativecalc"})["approval"]
        decide(str(self.base), approval["id"], True)
        path = self.base / ".zero_os" / "assistant" / "approvals.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["items"][0]["expires_utc"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        self.assertFalse(latest_approved(str(self.base), "store_install", run_id="run-1", target="nativecalc")["ok"])
        self.assertEqual("expired", status(str(self.base))["items"][-1]["state"])


if __name__ == "__main__":
    unittest.main()

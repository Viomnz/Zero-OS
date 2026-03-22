import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.approval_workflow import decide as approval_decide
from zero_os.calendar_time import calendar_reminder_add, calendar_reminder_tick, calendar_time_refresh, calendar_time_status
from zero_os.communications import communications_draft_add, communications_refresh, communications_send_execute, communications_send_request, communications_status, communications_tick


class DomainSubsystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_domain_subsystems_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_communications_status_and_refresh_create_state(self) -> None:
        status = communications_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertTrue(Path(status["path"]).exists())
        refreshed = communications_refresh(str(self.base))
        self.assertTrue(refreshed["last_refreshed_utc"])
        self.assertIn("summary", refreshed)

    def test_calendar_time_status_and_refresh_create_state(self) -> None:
        status = calendar_time_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertTrue(Path(status["path"]).exists())
        refreshed = calendar_time_refresh(str(self.base))
        self.assertTrue(refreshed["last_refreshed_utc"])
        self.assertIn("summary", refreshed)

    def test_communications_draft_add_updates_state(self) -> None:
        out = communications_draft_add(str(self.base), "vincent@example.com", "ship the matrix update")
        self.assertTrue(out["ok"])
        self.assertEqual("vincent@example.com", out["draft"]["recipient"])
        status = communications_status(str(self.base))
        self.assertEqual(1, status["summary"]["draft_count"])

    def test_calendar_reminder_add_updates_state(self) -> None:
        out = calendar_reminder_add(str(self.base), "review zero ai", "2026-03-20T09:00:00-07:00")
        self.assertTrue(out["ok"])
        self.assertEqual("review zero ai", out["reminder"]["title"])
        status = calendar_time_status(str(self.base))
        self.assertEqual(1, status["summary"]["reminder_count"])

    def test_communications_send_requires_and_uses_approval(self) -> None:
        draft = communications_draft_add(str(self.base), "vincent@example.com", "ship now")["draft"]
        requested = communications_send_request(str(self.base), draft["id"])
        self.assertTrue(requested["ok"])
        self.assertEqual("pending", requested["approval"]["state"])

        blocked = communications_send_execute(str(self.base), draft["id"])
        self.assertFalse(blocked["ok"])
        self.assertEqual("approval_required", blocked["reason"])

        approval_decide(str(self.base), requested["approval"]["id"], True)
        sent = communications_send_execute(str(self.base), draft["id"])
        self.assertTrue(sent["ok"])
        status = communications_status(str(self.base))
        self.assertEqual(0, status["summary"]["draft_count"])
        self.assertEqual(1, status["summary"]["outbox_count"])

    def test_calendar_reminder_tick_executes_due_reminder(self) -> None:
        calendar_reminder_add(str(self.base), "review zero ai", "2026-03-20T09:00:00-07:00")
        tick = calendar_reminder_tick(str(self.base), "2026-03-20T10:00:00-07:00")
        self.assertTrue(tick["ok"])
        self.assertEqual(1, tick["executed_count"])
        status = calendar_time_status(str(self.base))
        self.assertEqual(0, status["summary"]["reminder_count"])
        self.assertEqual(1, status["summary"]["calendar_item_count"])

    def test_communications_tick_executes_approved_send(self) -> None:
        draft = communications_draft_add(str(self.base), "vincent@example.com", "ship now")["draft"]
        requested = communications_send_request(str(self.base), draft["id"])
        approval_decide(str(self.base), requested["approval"]["id"], True)
        tick = communications_tick(str(self.base))
        self.assertTrue(tick["ok"])
        self.assertEqual(1, tick["executed_count"])
        status = communications_status(str(self.base))
        self.assertEqual(0, status["summary"]["draft_count"])
        self.assertEqual(1, status["summary"]["outbox_count"])


if __name__ == "__main__":
    unittest.main()

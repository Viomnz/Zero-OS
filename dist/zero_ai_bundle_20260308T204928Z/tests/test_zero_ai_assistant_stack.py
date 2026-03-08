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

from zero_os.task_executor import run_task, run_task_resume
from zero_os.recovery import zero_ai_backup_create
from zero_os.api_connector_profiles import profile_set
from zero_os.approval_workflow import decide as approval_decide, status as approval_status
from zero_os.assistant_job_runner import schedule as job_schedule, tick as job_tick
from zero_os.playbook_memory import status as playbook_status


class ZeroAiAssistantStackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_assistant_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_run_task_collects_status(self) -> None:
        out = run_task(str(self.base), "check system status")
        self.assertTrue(out["ok"])
        self.assertTrue(any(step["kind"] == "system_status" for step in out["plan"]["steps"]))

    def test_run_task_verifies_url(self) -> None:
        out = run_task(str(self.base), "check https://example.com")
        self.assertTrue(out["ok"])
        self.assertTrue(any(step["kind"] == "web_verify" for step in out["plan"]["steps"]))

    def test_run_task_autonomy_gate_for_fix(self) -> None:
        out = run_task(str(self.base), "fix runtime issues")
        self.assertTrue(any(step["kind"] == "autonomy_gate" for step in out["plan"]["steps"]))

    def test_run_task_fetches_url(self) -> None:
        out = run_task(str(self.base), "fetch https://example.com")
        self.assertTrue(any(step["kind"] == "web_fetch" for step in out["plan"]["steps"]))

    def test_run_task_store_status(self) -> None:
        out = run_task(str(self.base), "native store status")
        self.assertTrue(any(step["kind"] == "store_status" for step in out["plan"]["steps"]))

    def test_run_task_recover_executes_with_snapshot(self) -> None:
        zero_ai_backup_create(str(self.base))
        out = run_task(str(self.base), "recover system")
        self.assertTrue(any(step["kind"] == "recover" for step in out["plan"]["steps"]))

    def test_run_task_browser_open_step(self) -> None:
        out = run_task(str(self.base), "open https://example.com")
        self.assertTrue(any(step["kind"] == "browser_open" for step in out["plan"]["steps"]))

    def test_run_task_api_request_step(self) -> None:
        profile_set(str(self.base), "demo", "https://example.com")
        out = run_task(str(self.base), "api profile demo fetch /")
        self.assertTrue(any(step["kind"] == "api_request" for step in out["plan"]["steps"]))

    def test_run_task_returns_synthesized_response(self) -> None:
        out = run_task(str(self.base), "check system status")
        self.assertIn("response", out)
        self.assertIn("summary", out["response"])
        self.assertIn("task_memory", out)

    def test_run_task_can_use_highway_dispatch(self) -> None:
        out = run_task(str(self.base), "whoami")
        self.assertTrue(any(step["kind"] == "highway_dispatch" for step in out["plan"]["steps"]))

    def test_run_task_browser_status(self) -> None:
        out = run_task(str(self.base), "browser status")
        self.assertTrue(any(step["kind"] == "browser_status" for step in out["plan"]["steps"]))

    def test_run_task_resume_continues_resumable_work(self) -> None:
        out = run_task(str(self.base), "recover system")
        self.assertFalse(out["ok"])
        resumed = run_task_resume(str(self.base))
        self.assertFalse(resumed["ok"] or resumed.get("reason") == "no resumable task")
        self.assertIn("task_memory", resumed)

    def test_run_task_browser_action_can_request_approval(self) -> None:
        out = run_task(str(self.base), "open https://example.com and click")
        approvals = approval_status(str(self.base))
        self.assertTrue(any(step["kind"] == "browser_action" for step in out["plan"]["steps"]))
        self.assertGreaterEqual(approvals["count"], 1)

    def test_approved_browser_action_allows_resume(self) -> None:
        out = run_task(str(self.base), "open https://example.com and click")
        approval = approval_status(str(self.base))["items"][-1]
        approval_decide(str(self.base), approval["id"], True)
        resumed = run_task_resume(str(self.base))
        self.assertIn("task_memory", resumed)

    def test_run_task_api_workflow(self) -> None:
        profile_set(str(self.base), "demo", "https://example.com")
        out = run_task(str(self.base), "api workflow demo paths /,/index.html")
        self.assertTrue(any(step["kind"] == "api_workflow" for step in out["plan"]["steps"]))

    def test_run_task_remembers_playbook(self) -> None:
        run_task(str(self.base), "check system status")
        status = playbook_status(str(self.base))
        self.assertGreaterEqual(status["count"], 1)

    def test_background_job_runner(self) -> None:
        job_schedule(str(self.base), "check system status")
        ticked = job_tick(str(self.base))
        self.assertTrue(ticked["ok"])

    def test_run_task_browser_dom_inspect(self) -> None:
        out = run_task(str(self.base), "inspect page https://example.com")
        self.assertTrue(any(step["kind"] == "browser_dom_inspect" for step in out["plan"]["steps"]))

    def test_run_task_github_connect(self) -> None:
        out = run_task(str(self.base), "github repo connect owner/repo")
        self.assertTrue(any(step["kind"] == "github_connect" for step in out["plan"]["steps"]))

    def test_run_task_cloud_deploy(self) -> None:
        out = run_task(str(self.base), "cloud target set prod provider aws")
        self.assertTrue(any(step["kind"] == "cloud_target_set" for step in out["plan"]["steps"]))


if __name__ == "__main__":
    unittest.main()

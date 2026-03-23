import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.approval_workflow import decide, request_approval, status as approval_status
from zero_os.agent_permission_policy import set_action_tier
from zero_os.unified_action_engine import execute_step


class UnifiedActionEngineApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_unified_action_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _approve(self, action: str, target, run_id: str = "run-1") -> dict:
        approval = request_approval(str(self.base), action, "need approval", {"run_id": run_id, "target": target})["approval"]
        decide(str(self.base), approval["id"], True)
        return approval

    @patch("zero_os.unified_action_engine.autonomy_evaluate", return_value={"decision": "allow"})
    @patch("zero_os.unified_action_engine.run_self_repair", return_value={"ok": True})
    def test_self_repair_executes_once_after_exact_approval(self, mock_repair, _mock_gate) -> None:
        self._approve("self_repair", "runtime")

        result = execute_step(str(self.base), {"kind": "self_repair", "target": "runtime"}, run_id="run-1")
        again = execute_step(str(self.base), {"kind": "self_repair", "target": "runtime"}, run_id="run-1")

        self.assertTrue(result["ok"])
        self.assertTrue(mock_repair.called)
        self.assertEqual("executed", approval_status(str(self.base))["items"][0]["state"])
        self.assertFalse(again["ok"])
        self.assertEqual("approval_required", again["reason"])

    @patch("zero_os.unified_action_engine.autonomy_evaluate", return_value={"decision": "allow"})
    @patch("zero_os.unified_action_engine.store_install", return_value={"ok": True, "installed": True})
    def test_store_install_executes_after_exact_approval(self, mock_install, _mock_gate) -> None:
        self._approve("store_install", "nativecalc")

        result = execute_step(str(self.base), {"kind": "store_install", "target": "nativecalc"}, run_id="run-1")

        self.assertTrue(result["ok"])
        self.assertTrue(mock_install.called)
        self.assertEqual("executed", approval_status(str(self.base))["items"][0]["state"])

    @patch("zero_os.unified_action_engine.browser_dom_act", return_value={"ok": True, "action": {"url": "https://example.com"}})
    def test_browser_action_requires_exact_target_match(self, mock_act) -> None:
        approved_target = {"url": "https://example.com", "action": "click", "selector": "body"}
        self._approve("browser_action", approved_target)

        mismatch = execute_step(
            str(self.base),
            {"kind": "browser_action", "target": {"url": "https://other.example", "action": "click", "selector": "body"}},
            run_id="run-1",
        )
        matched = execute_step(str(self.base), {"kind": "browser_action", "target": approved_target}, run_id="run-1")

        self.assertFalse(mismatch["ok"])
        self.assertEqual("approval_required", mismatch["reason"])
        self.assertTrue(matched["ok"])
        self.assertEqual("https://example.com", matched["result"]["action"]["url"])
        self.assertEqual(1, mock_act.call_count)

    @patch("zero_os.unified_action_engine.autonomy_evaluate", return_value={"decision": "allow"})
    @patch("zero_os.unified_action_engine.browser_dom_act", return_value={"ok": True, "action": {"url": "https://example.com"}})
    def test_browser_action_can_run_guarded_auto_without_manual_approval(self, mock_act, _mock_gate) -> None:
        set_action_tier(str(self.base), "browser_action", "guarded_auto")

        result = execute_step(
            str(self.base),
            {"kind": "browser_action", "target": {"url": "https://example.com", "action": "click", "selector": "body"}},
            run_id="run-1",
        )

        self.assertTrue(result["ok"])
        self.assertEqual("https://example.com", result["result"]["action"]["url"])
        self.assertEqual(1, mock_act.call_count)
        self.assertEqual(0, approval_status(str(self.base))["pending_count"])

    @patch("zero_os.unified_action_engine.autonomy_evaluate", return_value={"decision": "allow"})
    @patch("zero_os.unified_action_engine.browser_dom_act", return_value={"ok": True, "action": {"url": "https://example.com"}})
    def test_browser_action_passes_planner_context_into_autonomy_gate(self, mock_act, mock_gate) -> None:
        set_action_tier(str(self.base), "browser_action", "guarded_auto")

        result = execute_step(
            str(self.base),
            {"kind": "browser_action", "target": {"url": "https://example.com", "action": "click", "selector": "body"}},
            run_id="run-1",
            plan_context={"planner_confidence": 0.63, "risk_level": "medium", "ambiguity_flags": ["mixed_intents", "generic_browser_selector"]},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(1, mock_act.call_count)
        self.assertEqual(0.63, mock_gate.call_args.kwargs["planner_confidence"])
        self.assertEqual("medium", mock_gate.call_args.kwargs["planner_risk_level"])
        self.assertEqual(2, mock_gate.call_args.kwargs["planner_ambiguity_count"])

    @patch("zero_os.unified_action_engine.browser_dom_act", return_value={"ok": True, "action": {"url": "https://example.com"}})
    def test_browser_action_safe_mode_requires_specific_selector(self, mock_act) -> None:
        set_action_tier(str(self.base), "browser_action", "guarded_auto")

        result = execute_step(
            str(self.base),
            {"kind": "browser_action", "target": {"url": "https://example.com", "action": "click", "selector": "body"}},
            run_id="run-1",
            plan_context={"execution_mode": "safe"},
        )

        self.assertFalse(result["ok"])
        self.assertEqual("safe_mode_requires_specific_selector", result["reason"])
        self.assertEqual(0, mock_act.call_count)


if __name__ == "__main__":
    unittest.main()

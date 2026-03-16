import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.memory_tier_filter import build_memory_context, score_branch_support
from zero_os.playbook_memory import remember
from zero_os.task_memory import save_task_run


class MemoryTierFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_memory_tier_filter_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_build_memory_context_prefers_stable_recent_memory_and_core_law(self) -> None:
        remember(
            str(self.base),
            "status",
            {
                "intent": {"intent": "status"},
                "steps": [{"kind": "system_status", "target": "health"}],
            },
        )
        save_task_run(
            str(self.base),
            "check system status",
            {
                "ok": True,
                "plan": {
                    "intent": {"intent": "status"},
                    "steps": [{"kind": "system_status", "target": "health"}],
                },
                "results": [{"ok": True, "kind": "system_status", "result": {"ok": True}}],
                "response": {"contradiction_gate": {"decision": "allow"}},
                "contradiction_gate": {"decision": "allow"},
            },
        )

        context = build_memory_context(
            str(self.base),
            "check system status",
            {"intent": "status", "goals": ["check system status"]},
        )

        tiers = {item["tier"] for item in context["items"]}
        self.assertIn("tier1_current", tiers)
        self.assertIn("tier2_working", tiers)
        self.assertIn("tier3_playbook", tiers)
        self.assertIn("tier4_core", tiers)
        self.assertGreater(context["support_by_kind"]["system_status"], 0.0)
        self.assertGreater(context["memory_confidence"], 0.0)

    def test_score_branch_support_uses_filtered_memory(self) -> None:
        context = {
            "support_by_kind": {"system_status": 1.4},
            "items": [
                {"tier": "tier1_current", "source": "request", "key": "current_request", "evidence_weight": 1.0, "support_step_kinds": ["system_status"]},
                {"tier": "tier4_core", "source": "policy_memory", "key": "core_law", "evidence_weight": 1.0, "support_step_kinds": ["system_status"]},
            ],
            "memory_confidence": 0.9,
            "same_system": True,
            "contradiction_free": True,
        }

        evidence = score_branch_support(
            {
                "steps": [{"kind": "system_status", "target": "health"}],
            },
            context,
        )

        self.assertGreater(evidence["memory_weight"], 0.0)
        self.assertGreater(evidence["total_weight"], 0.5)
        self.assertEqual(["system_status"], evidence["supported_step_kinds"])


if __name__ == "__main__":
    unittest.main()

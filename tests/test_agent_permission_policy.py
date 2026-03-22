import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.agent_permission_policy import classify_action, policy_status, set_action_tier


class AgentPermissionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="agent_permission_policy_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_default_policy_exposes_action_tiers(self) -> None:
        status = policy_status(str(self.base))

        self.assertIn("actions", status)
        self.assertIn("tiers", status)
        self.assertEqual("approval_required", status["actions"]["self_repair"])
        self.assertEqual("safe_auto", status["actions"]["web_verify"])

    def test_set_action_tier_updates_classification(self) -> None:
        updated = set_action_tier(str(self.base), "self_repair", "guarded_auto")
        classification = classify_action(str(self.base), "self_repair")

        self.assertTrue(updated["ok"])
        self.assertEqual("guarded_auto", updated["tier"])
        self.assertEqual("allow", classification["decision"])
        self.assertEqual("guarded_auto", classification["tier"])
        self.assertTrue(classification["requires_rollback"])
        self.assertFalse(classification["requires_approval"])


if __name__ == "__main__":
    unittest.main()

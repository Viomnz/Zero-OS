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

from zero_os.domain_pack_factory import (
    domain_pack_factory_status,
    domain_pack_generate_feature,
    domain_pack_scaffold,
    domain_pack_verify,
)
from zero_os.fast_path_cache import clear_fast_path_cache


class DomainPackFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_fast_path_cache(namespace="domain_pack_factory_status")
        clear_fast_path_cache(namespace="capability_expansion_protocol_status")
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_domain_pack_factory_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        clear_fast_path_cache(namespace="domain_pack_factory_status")
        clear_fast_path_cache(namespace="capability_expansion_protocol_status")
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_scaffold_creates_domain_pack_and_factory_status(self) -> None:
        out = domain_pack_scaffold(str(self.base), "Research")
        self.assertTrue(out["ok"])
        self.assertEqual("research", out["domain_key"])

        domain_dir = self.base / ".zero_os" / "domain_packs" / "research"
        self.assertTrue((domain_dir / "README.md").exists())
        self.assertTrue((domain_dir / "intent.py").exists())
        self.assertTrue((domain_dir / "planner.py").exists())
        self.assertTrue((domain_dir / "executor.py").exists())
        self.assertTrue((domain_dir / "contradiction.py").exists())
        self.assertTrue((domain_dir / "audit.py").exists())
        self.assertTrue((domain_dir / "controller.json").exists())
        self.assertTrue((domain_dir / "tests" / "test_research_domain.py").exists())

        manifest = json.loads((domain_dir / "domain_pack.json").read_text(encoding="utf-8"))
        self.assertEqual("research", manifest["domain_key"])
        self.assertIn("typed_plan_steps", manifest["required_contracts"])

        status = domain_pack_factory_status(str(self.base))
        self.assertEqual(1, status["summary"]["domain_pack_count"])
        self.assertEqual(1, status["summary"]["ready_count"])

    def test_verify_reports_missing_stage_when_contract_file_removed(self) -> None:
        domain_pack_scaffold(str(self.base), "Communications")
        domain_dir = self.base / ".zero_os" / "domain_packs" / "communications"
        (domain_dir / "audit.py").unlink()

        out = domain_pack_verify(str(self.base), "Communications")
        self.assertTrue(out["ok"])
        self.assertFalse(out["admission_ready"])
        self.assertIn("rollback_and_audit", out["missing_stages"])

    def test_generate_feature_creates_auto_generated_domain_pack(self) -> None:
        out = domain_pack_generate_feature(str(self.base), "calendar reminders for billing follow-up")
        self.assertTrue(out["ok"])
        self.assertTrue(out["auto_generated"])
        self.assertEqual("zero_ai", out["generated_by"])

        domain_dir = self.base / ".zero_os" / "domain_packs" / "calendar_reminders_for_billing_follow_up"
        manifest = json.loads((domain_dir / "domain_pack.json").read_text(encoding="utf-8"))
        controller = json.loads((domain_dir / "controller.json").read_text(encoding="utf-8"))

        self.assertEqual("ready", manifest["status"])
        self.assertEqual("zero_ai", manifest["generated_by"])
        self.assertEqual("calendar reminders for billing follow-up", manifest["feature_request"])
        self.assertEqual("calendar_time", manifest["subsystem"])
        self.assertEqual("calendar reminders for billing follow-up", controller["generated_from_request"])
        self.assertTrue(out["verify"]["admission_ready"])

    def test_status_uses_fast_path_when_inputs_are_unchanged(self) -> None:
        domain_pack_scaffold(str(self.base), "Research")
        clear_fast_path_cache(namespace="domain_pack_factory_status")

        first = domain_pack_factory_status(str(self.base))
        second = domain_pack_factory_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])


if __name__ == "__main__":
    unittest.main()

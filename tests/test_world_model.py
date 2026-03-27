import shutil
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.world_model import build_world_model, persist_world_model, world_model_status


class WorldModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_world_model_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_build_world_model_tracks_blocking_domains(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": False, "missing": True, "runtime_score": 0.0},
                "runtime_loop": {"enabled": False},
                "runtime_agent": {"installed": False, "running": False},
                "continuity": {
                    "continuity": {"same_system": False, "continuity_score": 32.5},
                    "contradiction_detection": {"has_contradiction": True},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "approvals": {"pending_count": 2, "expired_count": 0},
                "jobs": {"count": 1},
            },
        )

        self.assertTrue(model["ok"])
        self.assertIn("runtime", model["blocked_domains"])
        self.assertIn("continuity", model["blocked_domains"])
        self.assertIn("approvals", model["blocked_domains"])
        self.assertGreaterEqual(model["observation_summary"]["blocking_count"], 3)

    def test_world_model_status_reads_persisted_store(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )
        persisted = persist_world_model(str(self.base), model, flush=True)

        self.assertTrue(persisted["ok"])
        saved = world_model_status(str(self.base))
        self.assertTrue(saved["ok"])
        self.assertEqual(model["domain_count"], saved["domain_count"])
        self.assertEqual(model["blocked_domains"], saved["blocked_domains"])

    def test_build_world_model_blocks_when_recovery_has_no_compatible_snapshot(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "recovery": {"snapshot_count": 2, "compatible_count": 0, "latest_compatible_snapshot_id": ""},
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        self.assertIn("recovery", model["blocked_domains"])
        self.assertFalse(model["domains"]["recovery"]["healthy"])
        self.assertTrue(model["domains"]["recovery"]["blocking"])

    def test_build_world_model_includes_codebase_domain_when_workbench_is_observed(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "code_workbench": {
                    "workspace_ready": True,
                    "requested_code_mutation": True,
                    "scope_ready": False,
                    "verification_ready": False,
                    "target_file_count": 1,
                    "in_scope_count": 0,
                    "out_of_scope_count": 1,
                    "missing_in_scope_count": 0,
                    "ready": False,
                },
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        self.assertIn("codebase", model["domains"])
        self.assertIn("codebase", model["blocked_domains"])
        self.assertFalse(model["domains"]["codebase"]["healthy"])


if __name__ == "__main__":
    unittest.main()

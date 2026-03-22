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

from zero_os.release_readiness import release_readiness_status


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="release_readiness_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_release_readiness_reports_blockers(self) -> None:
        with patch(
            "zero_os.release_readiness.workspace_status",
            return_value={"summary": {"indexed": True, "flow_score": 88.0, "flow_issue_count": 2}, "git": {"dirty": True, "change_count": 5}},
        ), patch(
            "zero_os.release_readiness.world_class_readiness_status",
            return_value={"overall_score": 100.0, "world_class_now": True},
        ), patch(
            "zero_os.release_readiness.zero_ai_recovery_inventory",
            return_value={"snapshot_count": 0, "latest_snapshot_id": "", "latest_compatible_snapshot_id": "", "compatible_count": 0},
        ):
            status = release_readiness_status(str(self.base))

        self.assertFalse(status["release_ready"])
        self.assertIn("dirty_worktree", status["blockers"])
        self.assertIn("flow_not_clean", status["blockers"])
        self.assertIn("latest_compatible_snapshot_missing", status["blockers"])

    def test_release_readiness_can_report_ready(self) -> None:
        with patch(
            "zero_os.release_readiness.workspace_status",
            return_value={"summary": {"indexed": True, "flow_score": 100.0, "flow_issue_count": 0}, "git": {"dirty": False, "change_count": 0}},
        ), patch(
            "zero_os.release_readiness.world_class_readiness_status",
            return_value={"overall_score": 100.0, "world_class_now": True},
        ), patch(
            "zero_os.release_readiness.zero_ai_recovery_inventory",
            return_value={"snapshot_count": 3, "latest_snapshot_id": "snap3", "latest_compatible_snapshot_id": "snap3", "compatible_count": 3},
        ):
            status = release_readiness_status(str(self.base))

        self.assertTrue(status["release_ready"])
        self.assertEqual([], status["blockers"])


if __name__ == "__main__":
    unittest.main()

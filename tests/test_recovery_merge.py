import json
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

from zero_os.recovery import (
    zero_ai_backup_create,
    zero_ai_backup_pin,
    zero_ai_backup_prune,
    zero_ai_recover,
    zero_ai_recovery_inventory,
)


class RecoveryMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_recovery_merge_")
        self.base = Path(self.tempdir)
        (self.base / "zero_os_config").mkdir(parents=True, exist_ok=True)
        (self.base / "src").mkdir(parents=True, exist_ok=True)
        (self.base / "ai_from_scratch").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_recovery_merges_existing_config_changes(self) -> None:
        config = self.base / "zero_os_config" / "settings.json"
        config.write_text(json.dumps({"theme": "blue", "local_only": True}, indent=2) + "\n", encoding="utf-8")
        snap = zero_ai_backup_create(str(self.base))
        config.write_text(json.dumps({"theme": "green", "post_backup": True}, indent=2) + "\n", encoding="utf-8")

        recovered = zero_ai_recover(str(self.base), snap["id"])
        self.assertTrue(recovered["ok"])
        merged = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual("blue", merged["theme"])
        self.assertTrue(merged["local_only"])
        self.assertTrue(merged["post_backup"])
        self.assertTrue(recovered["sync_results"])

    def test_recovery_rejects_snapshot_with_invalid_python(self) -> None:
        module = self.base / "src" / "broken.py"
        module.write_text("def ok():\n    return 1\n", encoding="utf-8")
        snap = zero_ai_backup_create(str(self.base))

        snapshot_module = self.base / ".zero_os" / "production" / "snapshots" / snap["id"] / "src" / "broken.py"
        snapshot_module.write_text("def broken(:\n", encoding="utf-8")

        recovered = zero_ai_recover(str(self.base), snap["id"])

        self.assertFalse(recovered["ok"])
        self.assertEqual("snapshot_verification_failed", recovered["reason"])
        self.assertIn("snapshot_src", recovered["verification"])

    def test_recovery_rejects_snapshot_missing_required_current_modules(self) -> None:
        required_src = self.base / "src" / "zero_os"
        required_ai = self.base / "ai_from_scratch"
        required_src.mkdir(parents=True, exist_ok=True)
        required_ai.mkdir(parents=True, exist_ok=True)
        (required_src / "contradiction_engine.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_src / "flow_monitor.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_src / "smart_workspace.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_src / "subsystem_controller_registry.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_src / "zero_ai_pressure_harness.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_src / "zero_ai_control_workflows.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_ai / "benchmark_history.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_ai / "benchmark_suite.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_ai / "eval.py").write_text("VALUE = 1\n", encoding="utf-8")
        (required_ai / "tokenizer_dataset.py").write_text("VALUE = 1\n", encoding="utf-8")

        snap = zero_ai_backup_create(str(self.base))
        snapshot_root = self.base / ".zero_os" / "production" / "snapshots" / snap["id"]
        (snapshot_root / "src" / "zero_os" / "zero_ai_pressure_harness.py").unlink()
        (snapshot_root / "ai_from_scratch" / "benchmark_history.py").unlink()

        recovered = zero_ai_recover(str(self.base), snap["id"])

        self.assertFalse(recovered["ok"])
        self.assertEqual("snapshot_module_set_incompatible", recovered["reason"])
        self.assertIn("src/zero_os/zero_ai_pressure_harness.py", recovered["module_compatibility"]["missing"]["src"])
        self.assertIn("ai_from_scratch/benchmark_history.py", recovered["module_compatibility"]["missing"]["ai_from_scratch"])

    def test_recovery_rolls_back_when_post_restore_python_is_invalid(self) -> None:
        live_module = self.base / "src" / "main.py"
        live_module.write_text("value = 'stable'\n", encoding="utf-8")
        snap = zero_ai_backup_create(str(self.base))

        post_recovery_module = self.base / ".zero_os" / "production" / "snapshots" / snap["id"] / "src" / "main.py"
        post_recovery_module.write_text("value = 'restored'\n", encoding="utf-8")
        verification_sequence = [
            {"ok": True, "root": "snapshot-src", "checked_files": 1, "error_count": 0, "errors": []},
            {"ok": True, "root": "snapshot-ai", "checked_files": 0, "error_count": 0, "errors": []},
            {"ok": True, "root": "snapshot-src", "checked_files": 1, "error_count": 0, "errors": []},
            {"ok": True, "root": "snapshot-ai", "checked_files": 0, "error_count": 0, "errors": []},
            {"ok": False, "root": "live-src", "checked_files": 2, "error_count": 1, "errors": [{"path": "broken_after_restore.py", "error": "synthetic"}]},
            {"ok": True, "root": "live-ai", "checked_files": 0, "error_count": 0, "errors": []},
        ]

        with patch("zero_os.recovery._verify_python_tree", side_effect=verification_sequence):
            recovered = zero_ai_recover(str(self.base), snap["id"])

        self.assertFalse(recovered["ok"])
        self.assertEqual("post_recovery_verification_failed", recovered["reason"])
        self.assertTrue(recovered["rollback"]["ok"])
        self.assertEqual("value = 'stable'\n", live_module.read_text(encoding="utf-8"))

    def test_recovery_latest_prefers_newest_compatible_snapshot(self) -> None:
        required_src = self.base / "src" / "zero_os"
        required_ai = self.base / "ai_from_scratch"
        required_src.mkdir(parents=True, exist_ok=True)
        required_ai.mkdir(parents=True, exist_ok=True)
        (required_src / "contradiction_engine.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_src / "flow_monitor.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_src / "smart_workspace.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_src / "subsystem_controller_registry.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_src / "zero_ai_pressure_harness.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_src / "zero_ai_control_workflows.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_ai / "benchmark_history.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_ai / "benchmark_suite.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_ai / "eval.py").write_text("VALUE = 'live'\n", encoding="utf-8")
        (required_ai / "tokenizer_dataset.py").write_text("VALUE = 'live'\n", encoding="utf-8")

        first = zero_ai_backup_create(str(self.base))
        older_snapshot = self.base / ".zero_os" / "production" / "snapshots" / first["id"]
        (older_snapshot / "src" / "zero_os" / "flow_monitor.py").write_text("VALUE = 'older-compatible'\n", encoding="utf-8")

        second = zero_ai_backup_create(str(self.base))
        newer_snapshot = self.base / ".zero_os" / "production" / "snapshots" / second["id"]
        (newer_snapshot / "src" / "zero_os" / "flow_monitor.py").write_text("VALUE = 'newer-incompatible'\n", encoding="utf-8")
        (newer_snapshot / "src" / "zero_os" / "zero_ai_pressure_harness.py").unlink()

        (self.base / "src" / "zero_os" / "flow_monitor.py").write_text("VALUE = 'mutated'\n", encoding="utf-8")

        recovered = zero_ai_recover(str(self.base), "latest")

        self.assertTrue(recovered["ok"])
        self.assertEqual(first["id"], recovered["snapshot_used"])
        self.assertEqual("VALUE = 'older-compatible'\n", (self.base / "src" / "zero_os" / "flow_monitor.py").read_text(encoding="utf-8"))

    def test_recovery_inventory_and_prune_preserve_known_good_snapshot(self) -> None:
        required_src = self.base / "src" / "zero_os"
        required_ai = self.base / "ai_from_scratch"
        required_src.mkdir(parents=True, exist_ok=True)
        required_ai.mkdir(parents=True, exist_ok=True)
        for rel in (
            "contradiction_engine.py",
            "flow_monitor.py",
            "smart_workspace.py",
            "subsystem_controller_registry.py",
            "zero_ai_pressure_harness.py",
            "zero_ai_control_workflows.py",
        ):
            (required_src / rel).write_text("VALUE = 1\n", encoding="utf-8")
        for rel in ("benchmark_history.py", "benchmark_suite.py", "eval.py", "tokenizer_dataset.py"):
            (required_ai / rel).write_text("VALUE = 1\n", encoding="utf-8")

        first = zero_ai_backup_create(str(self.base))
        second = zero_ai_backup_create(str(self.base))
        third = zero_ai_backup_create(str(self.base))

        pinned = zero_ai_backup_pin(str(self.base), first["id"], known_good=True)
        self.assertTrue(pinned["ok"])

        inventory = zero_ai_recovery_inventory(str(self.base))
        self.assertEqual(first["id"], inventory["known_good_snapshot_ids"][0])

        pruned = zero_ai_backup_prune(str(self.base), keep_latest=1)
        self.assertTrue(pruned["ok"])
        self.assertIn(first["id"], pruned["skipped_snapshot_ids"])
        self.assertTrue((self.base / ".zero_os" / "production" / "snapshots" / first["id"]).exists())
        self.assertTrue((self.base / ".zero_os" / "production" / "snapshots" / third["id"]).exists())
        self.assertFalse((self.base / ".zero_os" / "production" / "snapshots" / second["id"]).exists())


if __name__ == "__main__":
    unittest.main()

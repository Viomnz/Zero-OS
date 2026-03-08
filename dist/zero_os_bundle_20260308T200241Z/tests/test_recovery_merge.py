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

from zero_os.recovery import zero_ai_backup_create, zero_ai_recover


class RecoveryMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_recovery_merge_")
        self.base = Path(self.tempdir)
        (self.base / "zero_os_config").mkdir(parents=True, exist_ok=True)

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


if __name__ == "__main__":
    unittest.main()

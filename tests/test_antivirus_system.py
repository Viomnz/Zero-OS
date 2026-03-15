import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


class AntivirusSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_av_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_antivirus_scan_and_quarantine_restore(self) -> None:
        suspect = self.base / "suspect.ps1"
        suspect.write_text(
            "powershell -enc AAAA\n# quantum-virus-signature\n",
            encoding="utf-8",
        )

        scan = self.highway.dispatch("antivirus scan .", cwd=str(self.base))
        self.assertEqual("system", scan.capability)
        self.assertIn('"finding_count":', scan.summary)
        data = json.loads(scan.summary)
        self.assertGreaterEqual(data["finding_count"], 1)

        q = self.highway.dispatch("antivirus quarantine suspect.ps1", cwd=str(self.base))
        qd = json.loads(q.summary)
        self.assertTrue(qd["ok"])
        self.assertFalse(suspect.exists())

        qlist = self.highway.dispatch("antivirus quarantine list", cwd=str(self.base))
        qldata = json.loads(qlist.summary)
        self.assertGreaterEqual(qldata["count"], 1)
        qid = qd["id"]

        restored = self.highway.dispatch(f"antivirus restore {qid}", cwd=str(self.base))
        rdata = json.loads(restored.summary)
        self.assertTrue(rdata["ok"])
        self.assertTrue(suspect.exists())

    def test_antivirus_monitor_and_policy(self) -> None:
        on = self.highway.dispatch("antivirus monitor on interval=60", cwd=str(self.base))
        self.assertIn('"enabled": true', on.summary.lower())

        policy = self.highway.dispatch("antivirus policy set heuristic_threshold 40", cwd=str(self.base))
        pdata = json.loads(policy.summary)
        self.assertEqual(40, pdata["heuristic_threshold"])

        testf = self.base / "dropper.bat"
        testf.write_text("powershell -enc BBBB", encoding="utf-8")
        tick = self.highway.dispatch("antivirus monitor tick .", cwd=str(self.base))
        tdata = json.loads(tick.summary)
        self.assertTrue(tdata["ok"])
        self.assertTrue(tdata["ran"])

    def test_antivirus_signed_feed_export_import(self) -> None:
        signed = self.base / "feed.signed.json"
        exp = self.highway.dispatch(
            f"antivirus feed export signed {signed}",
            cwd=str(self.base),
        )
        edata = json.loads(exp.summary)
        self.assertTrue(edata["ok"])
        self.assertTrue(signed.exists())

        imp = self.highway.dispatch(
            f"antivirus feed import signed {signed}",
            cwd=str(self.base),
        )
        idata = json.loads(imp.summary)
        self.assertTrue(idata["ok"])
        self.assertTrue(idata["signature_valid"])

    def test_antivirus_nested_zip_detection(self) -> None:
        inner = self.base / "inner.zip"
        with zipfile.ZipFile(inner, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("payload.txt", "quantum-virus-signature")

        outer = self.base / "outer.zip"
        with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(inner, arcname="inner.zip")

        self.highway.dispatch("antivirus policy set archive_max_depth 3", cwd=str(self.base))
        scan = self.highway.dispatch("antivirus scan outer.zip", cwd=str(self.base))
        data = json.loads(scan.summary)
        self.assertGreaterEqual(data["finding_count"], 1)
        self.assertIn("archive_hits", data["findings"][0])

    def test_antivirus_restore_overwrite_guard(self) -> None:
        suspect = self.base / "replace_me.ps1"
        suspect.write_text("powershell -enc AAAA", encoding="utf-8")
        q = self.highway.dispatch("antivirus quarantine replace_me.ps1", cwd=str(self.base))
        qid = json.loads(q.summary)["id"]

        # Recreate destination to trigger overwrite guard.
        suspect.write_text("safe replacement", encoding="utf-8")
        restore = self.highway.dispatch(f"antivirus restore {qid}", cwd=str(self.base))
        rdata = json.loads(restore.summary)
        self.assertFalse(rdata["ok"])
        self.assertIn("destination exists", rdata["reason"])

        self.highway.dispatch("antivirus policy set restore_overwrite true", cwd=str(self.base))
        restore2 = self.highway.dispatch(f"antivirus restore {qid}", cwd=str(self.base))
        rdata2 = json.loads(restore2.summary)
        self.assertTrue(rdata2["ok"])

    def test_antivirus_monitor_tracks_changes(self) -> None:
        self.highway.dispatch("antivirus monitor on interval=60", cwd=str(self.base))
        self.highway.dispatch("antivirus monitor tick .", cwd=str(self.base))
        f = self.base / "new_dropper.cmd"
        f.write_text("powershell -enc BBBB", encoding="utf-8")
        tick = self.highway.dispatch("antivirus monitor tick .", cwd=str(self.base))
        data = json.loads(tick.summary)
        self.assertTrue(data["ok"])
        self.assertIn("changes", data)
        self.assertIn("new_dropper.cmd", "\n".join(data["changes"]["added"]))

    def test_antivirus_agent_run_and_status(self) -> None:
        f = self.base / "agent_suspect.ps1"
        f.write_text("powershell -enc AAAA\nquantum-virus-signature", encoding="utf-8")
        run = self.highway.dispatch("antivirus agent run . auto_quarantine=true", cwd=str(self.base))
        rdata = json.loads(run.summary)
        self.assertTrue(rdata["ok"])
        self.assertGreaterEqual(rdata["finding_count"], 1)
        self.assertIn("quarantined_count", rdata)

        status = self.highway.dispatch("antivirus agent status", cwd=str(self.base))
        sdata = json.loads(status.summary)
        self.assertTrue(sdata["ok"])
        self.assertIn("scan_report", sdata)

    def test_antivirus_suppression_blocks_signature_hit(self) -> None:
        f = self.base / "suppressed.ps1"
        f.write_text("quantum-virus-signature", encoding="utf-8")
        self.highway.dispatch("antivirus suppression add QVIR-SIM path=suppressed.ps1 hours=24", cwd=str(self.base))
        scan = self.highway.dispatch("antivirus scan suppressed.ps1", cwd=str(self.base))
        data = json.loads(scan.summary)
        self.assertEqual(0, data["finding_count"])

    def test_antivirus_response_mode_auto_quarantine_high(self) -> None:
        self.highway.dispatch("antivirus policy set response_mode quarantine_high", cwd=str(self.base))
        f = self.base / "autoq.ps1"
        f.write_text("powershell -enc AAAA\nquantum-virus-signature", encoding="utf-8")
        self.highway.dispatch("antivirus scan autoq.ps1", cwd=str(self.base))
        qlist = self.highway.dispatch("antivirus quarantine list", cwd=str(self.base))
        qd = json.loads(qlist.summary)
        self.assertGreaterEqual(qd["count"], 1)

    def test_antivirus_does_not_quarantine_its_own_source_surface(self) -> None:
        antivirus_source = self.base / "src" / "zero_os" / "antivirus.py"
        antivirus_source.parent.mkdir(parents=True, exist_ok=True)
        antivirus_source.write_text(
            "powershell -enc AAAA\nquantum-virus-signature\n",
            encoding="utf-8",
        )

        run = self.highway.dispatch("antivirus agent run src auto_quarantine=true", cwd=str(self.base))
        data = json.loads(run.summary)

        self.assertTrue(data["ok"])
        self.assertEqual(0, data["finding_count"])
        self.assertTrue(antivirus_source.exists())


if __name__ == "__main__":
    unittest.main()

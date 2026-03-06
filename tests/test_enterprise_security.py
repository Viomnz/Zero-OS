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

from zero_os.highway import Highway


class EnterpriseSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ent_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_enterprise_enable_status_and_siem_emit(self) -> None:
        on = self.highway.dispatch("enterprise security on", cwd=str(self.base))
        self.assertEqual("system", on.capability)
        self.assertIn('"enabled": true', on.summary.lower())

        status = self.highway.dispatch("enterprise security status", cwd=str(self.base))
        self.assertIn('"ok": true', status.summary.lower())

        emit = self.highway.dispatch("enterprise siem emit high malware-detected", cwd=str(self.base))
        ed = json.loads(emit.summary)
        self.assertTrue(ed["ok"])

    def test_enterprise_rollback_and_validation(self) -> None:
        rb = self.highway.dispatch("enterprise rollback run critical", cwd=str(self.base))
        data = json.loads(rb.summary)
        self.assertTrue(data["ok"])

        val = self.highway.dispatch("enterprise validate adversarial", cwd=str(self.base))
        v = json.loads(val.summary)
        self.assertIn("returncode", v)

    def test_enterprise_integration_config_and_probe(self) -> None:
        st = self.highway.dispatch("enterprise integration status", cwd=str(self.base))
        sdata = json.loads(st.summary)
        self.assertTrue(sdata["ok"])
        self.assertEqual(4, sdata["total"])

        cfg = self.highway.dispatch(
            "enterprise integration set siem on provider=splunk endpoint=https://example.com/hook",
            cwd=str(self.base),
        )
        cdata = json.loads(cfg.summary)
        self.assertTrue(cdata["ok"])

        probe = self.highway.dispatch("enterprise integration probe siem", cwd=str(self.base))
        pdata = json.loads(probe.summary)
        self.assertTrue(pdata["ok"])
        self.assertEqual("siem", pdata["integration"])


if __name__ == "__main__":
    unittest.main()

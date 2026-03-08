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

from tools.generate_sbom import generate_sbom
from tools.vuln_scan import scan_requirements
from tools.sign_artifacts import sign
from tools.export_compliance_evidence import export_evidence


class SecurityToolingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_tools_")
        self.base = Path(self.tempdir)
        (self.base / "security" / "artifacts").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_sbom_sign_and_evidence(self) -> None:
        (self.base / "README.md").write_text("hello", encoding="utf-8")
        sbom = generate_sbom(self.base)
        (self.base / "security" / "artifacts" / "sbom.json").write_text(json.dumps(sbom), encoding="utf-8")

        vuln = {"ok": True, "finding_count": 0}
        (self.base / "security" / "artifacts" / "vuln_scan.json").write_text(json.dumps(vuln), encoding="utf-8")

        sig = sign(self.base)
        (self.base / "security" / "artifacts" / "artifact_signatures.json").write_text(json.dumps(sig), encoding="utf-8")

        ev = export_evidence(self.base)
        self.assertTrue(ev["ok"])
        self.assertTrue((self.base / "security" / "artifacts" / "compliance_evidence.json").exists())

    def test_vuln_scan_no_requirements(self) -> None:
        rep = scan_requirements(self.base)
        self.assertTrue(rep["ok"])


if __name__ == "__main__":
    unittest.main()

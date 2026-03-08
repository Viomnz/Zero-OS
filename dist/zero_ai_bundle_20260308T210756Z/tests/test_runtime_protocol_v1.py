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


class RuntimeProtocolV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_rp1_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_protocol_workflow(self) -> None:
        st = self.highway.dispatch("runtime protocol status", cwd=str(self.base))
        self.assertTrue(json.loads(st.summary)["ok"])
        ad = self.highway.dispatch("runtime protocol adapter linux", cwd=str(self.base))
        self.assertTrue(json.loads(ad.summary)["ok"])
        hs = self.highway.dispatch(
            "runtime protocol handshake os=linux cpu=x86_64 arch=x86_64 security=strict",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(hs.summary)["ok"])

        payload = self.base / "artifact.bin"
        payload.write_bytes(b"abc")
        at = self.highway.dispatch("runtime protocol attest path=artifact.bin signer=store-ca", cwd=str(self.base))
        self.assertTrue(json.loads(at.summary)["ok"])

        cp1 = self.highway.dispatch("runtime protocol compatibility version=1.2.0", cwd=str(self.base))
        cp2 = self.highway.dispatch("runtime protocol compatibility version=2.0.0", cwd=str(self.base))
        self.assertTrue(json.loads(cp1.summary)["ok"])
        self.assertFalse(json.loads(cp2.summary)["ok"])

        dep = self.highway.dispatch("runtime protocol deprecate api=legacy_fs remove_after=2027-01-01", cwd=str(self.base))
        self.assertTrue(json.loads(dep.summary)["ok"])

    def test_security_hardening_controls(self) -> None:
        sec = self.highway.dispatch("runtime protocol security status", cwd=str(self.base))
        self.assertTrue(json.loads(sec.summary)["ok"])
        self.highway.dispatch("runtime protocol signer allow ops-ca", cwd=str(self.base))
        self.highway.dispatch("runtime protocol signer revoke bad-ca", cwd=str(self.base))
        rot = self.highway.dispatch("runtime protocol key rotate", cwd=str(self.base))
        self.assertTrue(json.loads(rot.summary)["ok"])

        payload = self.base / "secure.bin"
        payload.write_bytes(b"secure")
        att = self.highway.dispatch("runtime protocol attest path=secure.bin signer=ops-ca", cwd=str(self.base))
        ad = json.loads(att.summary)
        self.assertTrue(ad["ok"])
        sig = ad["attestation"]["signature"]
        ver = self.highway.dispatch(f"runtime protocol verify path=secure.bin signer=ops-ca signature={sig}", cwd=str(self.base))
        self.assertTrue(json.loads(ver.summary)["ok"])

        nonce = json.loads(self.highway.dispatch("runtime protocol nonce issue node=n1", cwd=str(self.base)).summary)["nonce"]
        proof = json.loads(
            self.highway.dispatch(
                f"runtime protocol proof preview os=linux cpu=x86_64 arch=x86_64 security=strict nonce={nonce}",
                cwd=str(self.base),
            ).summary
        )["proof"]
        hs = self.highway.dispatch(
            f"runtime protocol secure handshake os=linux cpu=x86_64 arch=x86_64 security=strict nonce={nonce} proof={proof}",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(hs.summary)["ok"])
        replay = self.highway.dispatch(
            f"runtime protocol secure handshake os=linux cpu=x86_64 arch=x86_64 security=strict nonce={nonce} proof={proof}",
            cwd=str(self.base),
        )
        self.assertFalse(json.loads(replay.summary)["ok"])

        # Adapter integrity allowlist
        c = json.loads(self.highway.dispatch("runtime protocol adapter linux", cwd=str(self.base)).summary)
        mh = c["module_hash"]
        self.highway.dispatch(f"runtime protocol adapter allowlist linux hash={mh}", cwd=str(self.base))
        c2 = self.highway.dispatch("runtime protocol adapter linux", cwd=str(self.base))
        self.assertTrue(json.loads(c2.summary)["ok"])

        audit = self.highway.dispatch("runtime protocol audit status", cwd=str(self.base))
        self.assertTrue(json.loads(audit.summary)["ok"])

    def test_security_grade_and_maximize(self) -> None:
        g1 = self.highway.dispatch("runtime protocol security grade", cwd=str(self.base))
        d1 = json.loads(g1.summary)
        self.assertTrue(d1["ok"])

        m = self.highway.dispatch("runtime protocol security maximize", cwd=str(self.base))
        md = json.loads(m.summary)
        self.assertTrue(md["ok"])

        g2 = self.highway.dispatch("runtime protocol security grade", cwd=str(self.base))
        d2 = json.loads(g2.summary)
        self.assertTrue(d2["grade_score"] >= d1["grade_score"])
        self.assertIn(d2["grade_tier"], {"A", "A+"})


if __name__ == "__main__":
    unittest.main()

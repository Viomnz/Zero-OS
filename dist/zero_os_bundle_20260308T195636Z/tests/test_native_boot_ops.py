import hashlib
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


class NativeBootOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_native_boot_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_uefi_scaffold_and_status(self) -> None:
        sc = self.highway.dispatch("kernel uefi scaffold", cwd=str(self.base))
        self.assertTrue(json.loads(sc.summary)["ok"])
        st = self.highway.dispatch("kernel uefi status", cwd=str(self.base))
        data = json.loads(st.summary)
        self.assertTrue(data["uefi"]["enabled"])

    def test_elf_module_and_measured_secure_boot(self) -> None:
        elf = self.base / "kernel.elf"
        elf.write_bytes(b"\x7fELF" + b"\x00" * 64)
        mod = self.base / "mod.bin"
        mod.write_bytes(b"module")

        e = self.highway.dispatch("kernel elf load kernel.elf", cwd=str(self.base))
        self.assertTrue(json.loads(e.summary)["ok"])
        m = self.highway.dispatch("kernel module load mod.bin", cwd=str(self.base))
        self.assertTrue(json.loads(m.summary)["ok"])

        sb = self.highway.dispatch("kernel secure boot on pk=abc123", cwd=str(self.base))
        self.assertTrue(json.loads(sb.summary)["secure_boot"]["enabled"])
        mb = self.highway.dispatch("kernel measured boot record kernel path=kernel.elf", cwd=str(self.base))
        self.assertTrue(json.loads(mb.summary)["ok"])

        digest = hashlib.sha256(elf.read_bytes()).hexdigest()
        bv = self.highway.dispatch(f"kernel boot verify kernel.elf sha256={digest}", cwd=str(self.base))
        self.assertTrue(json.loads(bv.summary)["ok"])

    def test_panic_dump_and_recovery(self) -> None:
        p = self.highway.dispatch("kernel panic trigger test-crash", cwd=str(self.base))
        pdata = json.loads(p.summary)
        self.assertTrue(pdata["ok"])
        self.assertFalse(pdata["panic"]["recovered"])
        dump_path = Path(pdata["panic"]["last_dump_path"])
        self.assertTrue(dump_path.exists())

        r = self.highway.dispatch("kernel panic recover", cwd=str(self.base))
        rdata = json.loads(r.summary)
        self.assertTrue(rdata["panic"]["recovered"])


if __name__ == "__main__":
    unittest.main()

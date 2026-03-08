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


class KernelStackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_kernel_stack_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_scheduler_memory_and_status(self) -> None:
        enq = self.highway.dispatch("kernel scheduler enqueue init priority=5 slice=20", cwd=str(self.base))
        self.assertTrue(json.loads(enq.summary)["ok"])
        tick = self.highway.dispatch("kernel scheduler tick", cwd=str(self.base))
        self.assertTrue(json.loads(tick.summary)["ok"])
        alloc = self.highway.dispatch("kernel memory alloc core pages=64", cwd=str(self.base))
        self.assertTrue(json.loads(alloc.summary)["ok"])

        status = self.highway.dispatch("kernel stack status", cwd=str(self.base))
        data = json.loads(status.summary)
        self.assertTrue(data["ok"])
        self.assertEqual(1, data["scheduler"]["queued"])
        self.assertEqual(64, data["memory"]["allocations"]["core"])

    def test_driver_fs_net_paths(self) -> None:
        d = self.highway.dispatch("kernel driver load netdrv version=1.0.0", cwd=str(self.base))
        self.assertTrue(json.loads(d.summary)["ok"])
        f = self.highway.dispatch("kernel fs mount root path=/ type=vfs", cwd=str(self.base))
        self.assertTrue(json.loads(f.summary)["ok"])
        i = self.highway.dispatch("kernel net iface add eth0 cidr=10.0.0.2/24", cwd=str(self.base))
        self.assertTrue(json.loads(i.summary)["ok"])
        r = self.highway.dispatch("kernel net route add 0.0.0.0/0 via=10.0.0.1", cwd=str(self.base))
        self.assertTrue(json.loads(r.summary)["ok"])

        status = self.highway.dispatch("kernel stack status", cwd=str(self.base))
        data = json.loads(status.summary)
        self.assertEqual(1, data["drivers"]["loaded_count"])
        self.assertEqual(1, data["filesystem"]["mount_count"])
        self.assertEqual(1, data["network"]["interface_count"])
        self.assertEqual(1, data["network"]["route_count"])

    def test_extended_native_subsystems(self) -> None:
        b = self.highway.dispatch("kernel block driver ahci on version=1.0", cwd=str(self.base))
        self.assertTrue(json.loads(b.summary)["ok"])

        self.highway.dispatch("kernel fs mount data path=/data type=ext2", cwd=str(self.base))
        j = self.highway.dispatch("kernel fs journal on", cwd=str(self.base))
        self.assertTrue(json.loads(j.summary)["ok"])
        w = self.highway.dispatch("kernel fs write data path=/hello.txt data=world", cwd=str(self.base))
        self.assertTrue(json.loads(w.summary)["ok"])
        r = self.highway.dispatch("kernel fs read data path=/hello.txt", cwd=str(self.base))
        self.assertEqual("world", json.loads(r.summary)["data"])
        rec = self.highway.dispatch("kernel fs recover", cwd=str(self.base))
        self.assertTrue(json.loads(rec.summary)["ok"])

        p1 = self.highway.dispatch("kernel net protocol arp on", cwd=str(self.base))
        p2 = self.highway.dispatch("kernel net protocol tcp on", cwd=str(self.base))
        self.assertTrue(json.loads(p1.summary)["ok"])
        self.assertTrue(json.loads(p2.summary)["ok"])
        nic = self.highway.dispatch("kernel nic driver set eth0 driver=e1000 on", cwd=str(self.base))
        self.assertTrue(json.loads(nic.summary)["ok"])

        kin = self.highway.dispatch("kernel input keyboard driver=ps2kbd on", cwd=str(self.base))
        din = self.highway.dispatch("kernel display driver vesa mode=1024x768x32", cwd=str(self.base))
        self.assertTrue(json.loads(kin.summary)["ok"])
        self.assertTrue(json.loads(din.summary)["ok"])

        plat = self.highway.dispatch("kernel platform set acpi=on apic=on smp=on cpus=4", cwd=str(self.base))
        self.assertTrue(json.loads(plat.summary)["ok"])

        status = self.highway.dispatch("kernel stack status", cwd=str(self.base))
        data = json.loads(status.summary)
        self.assertTrue(data["storage"]["block_drivers"]["ahci"]["enabled"])
        self.assertTrue(data["fs_journal"]["enabled"])
        self.assertTrue(data["net_stack"]["arp"])
        self.assertTrue(data["net_stack"]["tcp"])
        self.assertTrue(data["platform"]["smp_enabled"])
        self.assertEqual(4, data["platform"]["cpu_count"])


if __name__ == "__main__":
    unittest.main()

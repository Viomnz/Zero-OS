import hashlib
import shutil
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.kernel_rnd.boot_trust import verify_boot_image
from zero_os.kernel_rnd.foundation_status import kernel_foundation_status
from zero_os.kernel_rnd.interrupt_core import InterruptController
from zero_os.kernel_rnd.memory_manager import PageAllocator
from zero_os.kernel_rnd.process_model import ProcessTable
from zero_os.kernel_rnd.scheduler import RoundRobinScheduler, Task
from zero_os.kernel_rnd.syscall_abi import resolve_syscall


class KernelRndFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_kernel_rnd_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_boot_verify(self) -> None:
        img = self.base / "kernel.img"
        img.write_bytes(b"zero-kernel")
        expected = hashlib.sha256(b"zero-kernel").hexdigest()
        out = verify_boot_image(str(img), expected)
        self.assertTrue(out["ok"])

    def test_page_allocator(self) -> None:
        mm = PageAllocator(page_count=2)
        p0 = mm.alloc("a")
        p1 = mm.alloc("b")
        p2 = mm.alloc("c")
        self.assertIsNotNone(p0)
        self.assertIsNotNone(p1)
        self.assertIsNone(p2)
        self.assertTrue(mm.free(int(p0)))

    def test_scheduler_round_robin(self) -> None:
        s = RoundRobinScheduler()
        s.add(Task(1, "one"))
        s.add(Task(2, "two"))
        self.assertEqual(1, s.next_task().tid)
        self.assertEqual(2, s.next_task().tid)
        self.assertEqual(1, s.next_task().tid)

    def test_syscall_resolve(self) -> None:
        self.assertTrue(resolve_syscall(1)["ok"])
        self.assertFalse(resolve_syscall(999)["ok"])

    def test_interrupt_dispatch(self) -> None:
        ic = InterruptController()
        ic.register(14, "page_fault")
        out = ic.dispatch(14)
        self.assertTrue(out["ok"])
        self.assertEqual("page_fault", out["handler"])

    def test_process_table(self) -> None:
        pt = ProcessTable()
        p = pt.spawn("init")
        self.assertTrue(pt.exit(p.pid))
        rows = pt.list()
        self.assertEqual("exited", rows[0]["state"])

    def test_foundation_status(self) -> None:
        docs = self.base / "docs" / "kernel"
        docs.mkdir(parents=True, exist_ok=True)
        for name in [
            "README.md",
            "boot_trust_chain.md",
            "memory_manager.md",
            "scheduler.md",
            "syscall_abi.md",
            "interrupts_exceptions.md",
            "process_thread_model.md",
            "driver_framework.md",
        ]:
            (docs / name).write_text("ok\n", encoding="utf-8")
        status = kernel_foundation_status(str(self.base))
        self.assertEqual(100.0, status["kernel_rnd_foundation_score"])


if __name__ == "__main__":
    unittest.main()

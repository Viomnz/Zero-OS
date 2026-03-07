import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.hyperlayer.runtime_core import get_adapter, hyperlayer_status
from zero_os.hyperlayer.contracts import ZeroApi


class HyperlayerTests(unittest.TestCase):
    def test_status_shape(self) -> None:
        status = hyperlayer_status()
        self.assertTrue(status["zero_hyperlayer"])
        self.assertIn("active_backend", status)
        self.assertIn("system_info", status)
        self.assertIn("unified_api", status)
        self.assertIn("list_files", status["unified_api"])
        self.assertIn("network_probe", status["unified_api"])

    def test_adapter_has_backend_name(self) -> None:
        adapter = get_adapter()
        self.assertTrue(adapter.backend_name())

    def test_zero_api_default_methods_fail_closed(self) -> None:
        api = ZeroApi()
        self.assertEqual(api.backend_name(), "unknown")
        self.assertFalse(api.get_system_info().ok)
        self.assertFalse(api.list_processes().ok)
        self.assertFalse(api.run_shell("echo hi").ok)


if __name__ == "__main__":
    unittest.main()

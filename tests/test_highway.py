import sys
import tempfile
import shutil
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


class CoreRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_highway_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_core_status_route(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("core status", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Unified entity: Zero OS Unified Core", result.summary)

    def test_auto_upgrade(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("auto upgrade", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Auto-upgrade complete", result.summary)

    def test_plugin_scaffold(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("plugin scaffold sample", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Plugin scaffold created", result.summary)
        self.assertTrue((self.base / "plugins" / "sample.py").exists())

    def test_law_status_and_export(self) -> None:
        laws = self.base / "laws"
        laws.mkdir(parents=True, exist_ok=True)
        (laws / "recursion_law.txt").write_text("LAW-TEXT", encoding="utf-8")
        highway = Highway(cwd=str(self.base))

        status = highway.dispatch("law status", cwd=str(self.base))
        self.assertEqual("system", status.capability)
        self.assertIn("SHA256:", status.summary)

        exported = highway.dispatch("law export", cwd=str(self.base))
        self.assertEqual("system", exported.capability)
        self.assertEqual("LAW-TEXT", exported.summary)

    def test_cure_firewall_pressure_gate(self) -> None:
        target = self.base / "sample.txt"
        target.write_text("hello", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch(
            "cure firewall run sample.txt pressure 10", cwd=str(self.base)
        )
        self.assertEqual("system", result.capability)
        self.assertIn("activated: False", result.summary)

    def test_cure_firewall_beacon_on_survival(self) -> None:
        target = self.base / "sample2.txt"
        target.write_text("hello recursion", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch(
            "cure firewall run sample2.txt pressure 80", cwd=str(self.base)
        )
        self.assertEqual("system", result.capability)
        self.assertIn("survived: True", result.summary)
        self.assertIn("score:", result.summary)
        self.assertTrue((self.base / ".zero_os" / "beacons" / "sample2.beacon.json").exists())
        verify = highway.dispatch("cure firewall verify sample2.txt", cwd=str(self.base))
        self.assertIn("signature_valid: True", verify.summary)

    def test_mark_strict_toggle_and_status(self) -> None:
        target = self.base / "safe.txt"
        target.write_text("ok", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        on = highway.dispatch("mark strict on", cwd=str(self.base))
        self.assertIn("True", on.summary)
        show = highway.dispatch("mark strict show", cwd=str(self.base))
        self.assertIn("True", show.summary)
        status = highway.dispatch("mark status safe.txt", cwd=str(self.base))
        self.assertIn("exists: True", status.summary)

    def test_beacon_signature_tamper_detected(self) -> None:
        target = self.base / "tamper.txt"
        target.write_text("hello", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        highway.dispatch("cure firewall run tamper.txt pressure 80", cwd=str(self.base))
        beacon = self.base / ".zero_os" / "beacons" / "tamper.beacon.json"
        data = json.loads(beacon.read_text(encoding="utf-8"))
        data["digest"] = "deadbeef"
        beacon.write_text(json.dumps(data, indent=2), encoding="utf-8")
        verify = highway.dispatch("cure firewall verify tamper.txt", cwd=str(self.base))
        self.assertIn("signature_valid: False", verify.summary)

    def test_beacon_content_drift_detected(self) -> None:
        target = self.base / "drift.txt"
        target.write_text("initial", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        highway.dispatch("cure firewall run drift.txt pressure 80", cwd=str(self.base))
        target.write_text("changed", encoding="utf-8")
        verify = highway.dispatch("cure firewall verify drift.txt", cwd=str(self.base))
        self.assertIn("signature_valid: False", verify.summary)
        self.assertIn("content drift detected", verify.summary)

    def test_cure_firewall_net_beacon_and_verify(self) -> None:
        highway = Highway(cwd=str(self.base))
        run = highway.dispatch(
            "cure firewall net run https://example.com pressure 80",
            cwd=str(self.base),
        )
        self.assertIn("survived: True", run.summary)
        verify = highway.dispatch(
            "cure firewall net verify https://example.com",
            cwd=str(self.base),
        )
        self.assertIn("signature_valid: True", verify.summary)

    def test_net_strict_blocks_unverified_fetch(self) -> None:
        highway = Highway(cwd=str(self.base))
        highway.dispatch("net strict on", cwd=str(self.base))
        result = highway.dispatch("fetch https://example.com", cwd=str(self.base))
        self.assertEqual("web", result.capability)
        self.assertIn("Blocked by net strict mode", result.summary)

    def test_net_policy_deny_blocks_net_run(self) -> None:
        highway = Highway(cwd=str(self.base))
        highway.dispatch("net policy deny example.com", cwd=str(self.base))
        run = highway.dispatch(
            "cure firewall net run https://example.com pressure 80",
            cwd=str(self.base),
        )
        self.assertIn("survived: False", run.summary)
        self.assertIn("domain denied by policy", run.summary)

    def test_audit_status_chain(self) -> None:
        target = self.base / "audit.txt"
        target.write_text("x", encoding="utf-8")
        highway = Highway(cwd=str(self.base))
        highway.dispatch("cure firewall run audit.txt pressure 80", cwd=str(self.base))
        status = highway.dispatch("audit status", cwd=str(self.base))
        self.assertIn("audit entries:", status.summary)
        self.assertIn("chain_valid: True", status.summary)


if __name__ == "__main__":
    unittest.main()

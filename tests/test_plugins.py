import shutil
import sys
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


class PluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_plugin_")
        self.base = Path(self.tempdir)
        plugins = self.base / "plugins"
        plugins.mkdir(parents=True, exist_ok=True)
        plugin_code = '''
from zero_os.types import Result

class EchoCap:
    name = "echo"
    def can_handle(self, task):
        return task.text.lower().startswith("echo ")
    def run(self, task):
        return Result(self.name, task.text[5:])

def get_capability():
    return EchoCap()
'''
        (plugins / "echo_plugin.py").write_text(plugin_code, encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_plugin_loaded_and_routed(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("echo hello", cwd=str(self.base))
        self.assertEqual("echo", result.capability)
        self.assertEqual("hello", result.summary)

    def test_native_plugin_package_loaded_and_routed(self) -> None:
        native_dir = self.base / "plugins" / "native_echo"
        native_dir.mkdir(parents=True, exist_ok=True)
        (native_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "native_echo",
                    "version": "1.0.0",
                    "entry": "plugin.py",
                    "factory": "get_capability",
                    "description": "Native test plugin",
                }
            ),
            encoding="utf-8",
        )
        (native_dir / "plugin.py").write_text(
            (
                "from zero_os.types import Result\n\n"
                "class NativeEchoCapability:\n"
                "    name = \"native_echo\"\n\n"
                "    def can_handle(self, task):\n"
                "        return task.text.lower().startswith(\"native echo \")\n\n"
                "    def run(self, task):\n"
                "        return Result(self.name, task.text[len(\"native echo \"):])\n\n"
                "def get_capability():\n"
                "    return NativeEchoCapability()\n"
            ),
            encoding="utf-8",
        )

        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("native echo hello", cwd=str(self.base))
        self.assertEqual("native_echo", result.capability)
        self.assertEqual("hello", result.summary)

    def test_plugin_scaffold_creates_signed_native_package(self) -> None:
        scaffold = Highway(cwd=str(self.base)).dispatch("plugin scaffold sample_pack", cwd=str(self.base))
        scaffold_payload = json.loads(scaffold.summary)
        self.assertTrue(scaffold_payload["ok"])
        sample_dir = self.base / "plugins" / "sample_pack"
        self.assertTrue((sample_dir / "plugin.json").exists())
        self.assertTrue((sample_dir / "plugin.py").exists())

        status = Highway(cwd=str(self.base)).dispatch("plugin status sample_pack", cwd=str(self.base))
        status_payload = json.loads(status.summary)
        self.assertTrue(status_payload["ok"])
        plugin_payload = status_payload["plugins"][0]
        self.assertEqual("native", plugin_payload["kind"])
        self.assertTrue(plugin_payload["signature_valid"])
        self.assertTrue(plugin_payload["load_allowed"])
        self.assertEqual("private-local", plugin_payload["distribution"])
        self.assertTrue(plugin_payload["local_only"])
        self.assertTrue(plugin_payload["mutable"])

    def test_plugin_install_local_file_and_toggle_enablement(self) -> None:
        source = self.base / "shoutbox.py"
        source.write_text(
            (
                "from zero_os.types import Result\n\n"
                "class ShoutCapability:\n"
                "    name = \"shoutbox\"\n\n"
                "    def can_handle(self, task):\n"
                "        return task.text.lower().startswith(\"shout \")\n\n"
                "    def run(self, task):\n"
                "        return Result(self.name, task.text[len(\"shout \"):].upper())\n\n"
                "def get_capability():\n"
                "    return ShoutCapability()\n"
            ),
            encoding="utf-8",
        )

        install = Highway(cwd=str(self.base)).dispatch(f'plugin install local "{source}"', cwd=str(self.base))
        install_payload = json.loads(install.summary)
        self.assertTrue(install_payload["ok"])
        self.assertEqual("shoutbox", install_payload["plugin"])

        routed = Highway(cwd=str(self.base)).dispatch("shout hello", cwd=str(self.base))
        self.assertEqual("shoutbox", routed.capability)
        self.assertEqual("HELLO", routed.summary)

        disable = Highway(cwd=str(self.base)).dispatch("plugin disable shoutbox", cwd=str(self.base))
        disable_payload = json.loads(disable.summary)
        self.assertTrue(disable_payload["ok"])
        disabled_route = Highway(cwd=str(self.base)).dispatch("shout hello", cwd=str(self.base))
        self.assertNotEqual("shoutbox", disabled_route.capability)

        enable = Highway(cwd=str(self.base)).dispatch("plugin enable shoutbox", cwd=str(self.base))
        enable_payload = json.loads(enable.summary)
        self.assertTrue(enable_payload["ok"])
        enabled_route = Highway(cwd=str(self.base)).dispatch("shout again", cwd=str(self.base))
        self.assertEqual("shoutbox", enabled_route.capability)
        self.assertEqual("AGAIN", enabled_route.summary)

    def test_plugin_verify_blocks_tampered_native_package(self) -> None:
        scaffold = Highway(cwd=str(self.base)).dispatch("plugin scaffold guardme", cwd=str(self.base))
        self.assertTrue(json.loads(scaffold.summary)["ok"])
        plugin_file = self.base / "plugins" / "guardme" / "plugin.py"
        plugin_file.write_text(
            (
                "from zero_os.types import Result\n\n"
                "class GuardMeCapability:\n"
                "    name = \"guardme\"\n\n"
                "    def can_handle(self, task):\n"
                "        return task.text.lower().startswith(\"guardme \")\n\n"
                "    def run(self, task):\n"
                "        return Result(self.name, \"tampered\")\n\n"
                "def get_capability():\n"
                "    return GuardMeCapability()\n"
            ),
            encoding="utf-8",
        )

        verify = Highway(cwd=str(self.base)).dispatch("plugin verify guardme", cwd=str(self.base))
        verify_payload = json.loads(verify.summary)
        self.assertFalse(verify_payload["ok"])

        status = Highway(cwd=str(self.base)).dispatch("plugin status guardme", cwd=str(self.base))
        status_payload = json.loads(status.summary)
        self.assertFalse(status_payload["plugins"][0]["load_allowed"])

    def test_plugin_install_local_directory_without_manifest(self) -> None:
        source_dir = self.base / "my local mod"
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "plugin.py").write_text(
            (
                "from zero_os.types import Result\n\n"
                "class LocalModCapability:\n"
                "    name = \"my_local_mod\"\n\n"
                "    def can_handle(self, task):\n"
                "        return task.text.lower().startswith(\"wild \")\n\n"
                "    def run(self, task):\n"
                "        return Result(self.name, task.text[len(\"wild \"):])\n\n"
                "def get_capability():\n"
                "    return LocalModCapability()\n"
            ),
            encoding="utf-8",
        )

        install = Highway(cwd=str(self.base)).dispatch(f'plugin install local "{source_dir}"', cwd=str(self.base))
        install_payload = json.loads(install.summary)
        self.assertTrue(install_payload["ok"])
        self.assertEqual("my_local_mod", install_payload["plugin"])

        routed = Highway(cwd=str(self.base)).dispatch("wild west", cwd=str(self.base))
        self.assertEqual("my_local_mod", routed.capability)
        self.assertEqual("west", routed.summary)

        status = Highway(cwd=str(self.base)).dispatch("plugin status my_local_mod", cwd=str(self.base))
        status_payload = json.loads(status.summary)
        plugin_payload = status_payload["plugins"][0]
        self.assertEqual("private-local", plugin_payload["distribution"])
        self.assertTrue(plugin_payload["local_only"])
        self.assertTrue(plugin_payload["mutable"])


if __name__ == "__main__":
    unittest.main()

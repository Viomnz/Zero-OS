"""System capability."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import getpass
import re

from zero_os.core import CORE_POLICY
from zero_os.law_store import law_export, law_status
from zero_os.state import set_mode, set_profile_setting
from zero_os.types import Result, Task


class SystemCapability:
    name = "system"

    def can_handle(self, task: Task) -> bool:
        keys = (
            "system",
            "core status",
            "list files",
            "show files",
            "current directory",
            "current dir",
            "pwd",
            "whoami",
            "date",
            "time",
            "auto upgrade",
            "plugin scaffold",
            "law status",
            "law export",
        )
        text = task.text.lower()
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        text = task.text.lower()
        cwd = Path(task.cwd).resolve()

        if "list files" in text or "show files" in text:
            names = sorted(p.name for p in cwd.iterdir())
            if not names:
                return Result(self.name, f"{cwd}\n(empty)")
            return Result(self.name, f"{cwd}\n" + "\n".join(names))

        if "core status" in text:
            components = ", ".join(CORE_POLICY.merged_components)
            protocols = ", ".join(CORE_POLICY.survival_protocols)
            return Result(
                self.name,
                (
                    f"Unified entity: {CORE_POLICY.unified_entity_name}\n"
                    f"Immutable core: {CORE_POLICY.immutable_core}\n"
                    f"Auth required: {CORE_POLICY.authentication_required}\n"
                    f"Recursion enforced: {CORE_POLICY.recursion_enforced} "
                    f"(max_depth={CORE_POLICY.max_recursion_depth})\n"
                    f"Merged components: {components}\n"
                    f"Survival protocols: {protocols}"
                ),
            )

        if "auto upgrade" in text:
            mode = set_mode(task.cwd, "heavy")
            profile = set_profile_setting(task.cwd, "auto")
            return Result(
                self.name,
                (
                    "Auto-upgrade complete:\n"
                    f"- mode: {mode}\n"
                    f"- performance profile: {profile}\n"
                    "- core: immutable + no-auth active"
                ),
            )

        if text.strip() == "law status":
            return Result(self.name, law_status(task.cwd))

        if text.strip() == "law export":
            return Result(self.name, law_export(task.cwd))

        scaffold = re.match(r"^plugin scaffold\s+([a-zA-Z0-9_-]+)$", text.strip())
        if scaffold:
            plugin_name = scaffold.group(1)
            plugin_dir = cwd / "plugins"
            plugin_dir.mkdir(parents=True, exist_ok=True)
            plugin_path = plugin_dir / f"{plugin_name}.py"
            if plugin_path.exists():
                return Result(self.name, f"Plugin already exists: {plugin_path}")
            template = (
                "from zero_os.types import Result\n\n"
                f"class {plugin_name.title().replace('_', '').replace('-', '')}Capability:\n"
                f"    name = \"{plugin_name}\"\n\n"
                "    def can_handle(self, task):\n"
                f"        return task.text.lower().startswith(\"{plugin_name} \")\n\n"
                "    def run(self, task):\n"
                f"        return Result(self.name, \"{plugin_name} plugin executed\")\n\n"
                "def get_capability():\n"
                f"    return {plugin_name.title().replace('_', '').replace('-', '')}Capability()\n"
            )
            plugin_path.write_text(template, encoding="utf-8")
            return Result(self.name, f"Plugin scaffold created: {plugin_path}")

        if "current dir" in text or "current directory" in text or "pwd" in text:
            return Result(self.name, str(cwd))

        if "whoami" in text or "user" in text:
            return Result(self.name, getpass.getuser())

        if "time" in text or "date" in text:
            return Result(self.name, datetime.now().isoformat(timespec="seconds"))

        return Result(
            self.name,
            "Actionable system commands:\n"
            "- list files\n"
            "- current directory\n"
            "- whoami\n"
            "- date/time\n"
            "- core status\n"
            "- auto upgrade\n"
            "- plugin scaffold <name>\n"
            "- law status\n"
            "- law export",
        )

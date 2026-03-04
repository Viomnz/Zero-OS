"""System capability."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import getpass
import re

from zero_os.core import CORE_POLICY
from zero_os.cure_firewall import (
    audit_status,
    load_net_policy,
    run_cure_firewall,
    run_cure_firewall_net,
    set_net_policy,
    verify_beacon,
    verify_beacon_net,
)
from zero_os.law_store import law_export, law_status
from zero_os.readiness import apply_missing_fix, os_readiness
from zero_os.state import (
    get_mark_strict,
    get_net_strict,
    set_mark_strict,
    set_mode,
    set_net_strict,
    set_profile_setting,
)
from zero_os.types import Result, Task
from zero_os.universal_code_intake import intake_code


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
            "cure firewall",
            "mark strict",
            "mark status",
            "net strict",
            "net policy",
            "audit status",
            "code intake",
            "os readiness",
            "os missing fix",
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

        if text.strip() == "mark strict show":
            return Result(self.name, f"mark strict: {get_mark_strict(task.cwd)}")

        if text.strip() == "mark strict on":
            set_mark_strict(task.cwd, True)
            return Result(self.name, "mark strict: True")

        if text.strip() == "mark strict off":
            set_mark_strict(task.cwd, False)
            return Result(self.name, "mark strict: False")

        if text.strip() == "net strict show":
            return Result(self.name, f"net strict: {get_net_strict(task.cwd)}")

        if text.strip() == "net strict on":
            set_net_strict(task.cwd, True)
            return Result(self.name, "net strict: True")

        if text.strip() == "net strict off":
            set_net_strict(task.cwd, False)
            return Result(self.name, "net strict: False")

        if text.strip() == "audit status":
            return Result(self.name, audit_status(task.cwd))

        if text.strip() == "os readiness":
            r = os_readiness(task.cwd)
            return Result(
                self.name,
                (
                    f"os_readiness_score: {r['score']}\n"
                    f"missing: {', '.join(r['missing']) if r['missing'] else '(none)'}\n"
                    f"checks: {json.dumps(r['checks'], indent=2)}"
                ),
            )

        if text.strip() == "os missing fix":
            r = apply_missing_fix(task.cwd)
            return Result(
                self.name,
                (
                    f"created_count: {r['created_count']}\n"
                    + ("\n".join(r["created"]) if r["created"] else "nothing created")
                ),
            )

        code_intake = re.match(r"^code intake\s+(.+)$", text.strip(), flags=re.IGNORECASE)
        if code_intake:
            rel = code_intake.group(1).strip().strip("\"'")
            r = intake_code(task.cwd, rel)
            return Result(
                self.name,
                (
                    f"target: {r.target}\n"
                    f"exists: {r.exists}\n"
                    f"language_guess: {r.language_guess}\n"
                    f"bytes_size: {r.bytes_size}\n"
                    f"line_count: {r.line_count}\n"
                    f"token_count: {r.token_count}\n"
                    f"ascii_ratio: {r.ascii_ratio:.3f}\n"
                    f"sha256: {r.sha256}\n"
                    f"report: {r.report_path}"
                ),
            )

        if text.strip() == "net policy show":
            policy = load_net_policy(cwd)
            return Result(self.name, json.dumps(policy, indent=2))

        net_policy = re.match(r"^net policy (allow|deny|remove)\s+([a-z0-9.-]+)$", text.strip(), flags=re.IGNORECASE)
        if net_policy:
            mode = net_policy.group(1).lower()
            host = net_policy.group(2).lower()
            policy = set_net_policy(cwd, host, mode)
            return Result(self.name, f"net policy updated ({mode} {host})\n{json.dumps(policy, indent=2)}")

        mark_status = re.match(r"^mark status\s+(.+)$", text.strip(), flags=re.IGNORECASE)
        if mark_status:
            rel = mark_status.group(1).strip().strip("\"'")
            target = (cwd / rel).resolve()
            beacon = cwd / ".zero_os" / "beacons" / f"{target.stem}.beacon.json"
            exists = target.exists()
            marked = beacon.exists()
            valid, reason = verify_beacon(task.cwd, rel)
            return Result(
                self.name,
                f"target: {target}\nexists: {exists}\nmarked: {marked}\nsignature_valid: {valid}\nverify_reason: {reason}\nbeacon: {beacon}",
            )

        cure = re.match(
            r"^cure firewall run\s+(.+?)\s+pressure\s+(\d+)$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if cure:
            target = cure.group(1).strip().strip("\"'")
            pressure = int(cure.group(2))
            result = run_cure_firewall(task.cwd, target, pressure)
            lines = [
                f"target: {result.target}",
                f"activated: {result.activated}",
                f"survived: {result.survived}",
                f"pressure: {result.pressure}",
                f"score: {result.score}",
                f"notes: {result.notes}",
            ]
            if result.beacon_path:
                lines.append(f"beacon: {result.beacon_path}")
            return Result(self.name, "\n".join(lines))

        cure_net = re.match(
            r"^cure firewall net run\s+(.+?)\s+pressure\s+(\d+)$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if cure_net:
            url = cure_net.group(1).strip().strip("\"'")
            pressure = int(cure_net.group(2))
            result = run_cure_firewall_net(task.cwd, url, pressure)
            lines = [
                f"target: {result.target}",
                f"activated: {result.activated}",
                f"survived: {result.survived}",
                f"pressure: {result.pressure}",
                f"score: {result.score}",
                f"notes: {result.notes}",
            ]
            if result.beacon_path:
                lines.append(f"beacon: {result.beacon_path}")
            return Result(self.name, "\n".join(lines))

        cure_verify = re.match(r"^cure firewall verify\s+(.+)$", text.strip(), flags=re.IGNORECASE)
        if cure_verify:
            rel = cure_verify.group(1).strip().strip("\"'")
            valid, reason = verify_beacon(task.cwd, rel)
            return Result(self.name, f"signature_valid: {valid}\nverify_reason: {reason}")

        cure_net_verify = re.match(
            r"^cure firewall net verify\s+(.+)$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if cure_net_verify:
            url = cure_net_verify.group(1).strip().strip("\"'")
            valid, reason = verify_beacon_net(task.cwd, url)
            return Result(self.name, f"signature_valid: {valid}\nverify_reason: {reason}")

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
            "- law export\n"
            "- cure firewall run <path> pressure <0-100>\n"
            "- cure firewall verify <path>\n"
            "- cure firewall net run <url> pressure <0-100>\n"
            "- cure firewall net verify <url>\n"
            "- mark strict on|off|show\n"
            "- mark status <path>\n"
            "- net strict on|off|show\n"
            "- net policy show|allow|deny|remove <domain>\n"
            "- audit status\n"
            "- code intake <path>\n"
            "- os readiness\n"
            "- os missing fix",
        )

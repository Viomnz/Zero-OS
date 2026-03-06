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
    restore_from_cure_backup,
    run_cure_firewall,
    run_cure_firewall_net,
    set_net_policy,
    verify_beacon,
    verify_beacon_net,
)
from zero_os.law_store import law_export, law_status
from zero_os.hyperlayer.runtime_core import hyperlayer_status
from zero_os.readiness import apply_beginner_os_fix, apply_missing_fix, beginner_os_coverage, os_readiness
from zero_os.production_core import (
    api_token_create,
    api_token_verify,
    auto_optimize_set,
    auto_optimize_status,
    auto_merge_queue_run,
    auto_merge_set,
    auto_merge_status,
    ai_files_smart_optimize,
    ai_files_smart_set,
    ai_files_smart_status,
    benchmark_run,
    cleanup_apply,
    cleanup_status,
    deps_add,
    deps_list,
    isolation_list,
    isolation_set,
    jobs_add,
    jobs_list,
    jobs_run_one,
    memory_status,
    memory_smart_optimize,
    memory_smart_status,
    observability_report,
    process_kill,
    process_list,
    process_start,
    playbook_init,
    playbook_show,
    plugin_sign,
    plugin_verify,
    release_bump,
    release_init,
    freedom_mode_set,
    freedom_reset,
    freedom_status,
    sandbox_check,
    sandbox_status,
    sandbox_update,
    security_overview,
    snapshot_create,
    snapshot_list,
    snapshot_restore,
    system_optimize_all,
    storage_smart_optimize,
    storage_smart_restore,
    storage_smart_status,
    unified_shell_run,
    update_apply,
    update_create,
    update_rollback,
    znet_add_node,
    znet_add_service,
    znet_cure_apply,
    znet_cure_status,
    znet_init,
    znet_resolve,
    znet_status,
    znet_topology,
    zerofs_delete,
    zerofs_get,
    zerofs_init,
    zerofs_list,
    zerofs_put,
    zerofs_status,
    device_status,
    filesystem_status,
    hardware_capability_map,
)
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
from zero_os.cure_firewall_agent import (
    cure_firewall_agent_status,
    run_cure_firewall_agent,
)
from zero_os.antivirus import (
    threat_feed_export_signed as antivirus_threat_feed_export_signed,
    threat_feed_import_signed as antivirus_threat_feed_import_signed,
    monitor_set as antivirus_monitor_set,
    monitor_status as antivirus_monitor_status,
    monitor_tick as antivirus_monitor_tick,
    policy_set as antivirus_policy_set,
    policy_status as antivirus_policy_status,
    quarantine_file as antivirus_quarantine_file,
    quarantine_list as antivirus_quarantine_list,
    quarantine_restore as antivirus_quarantine_restore,
    scan_target as antivirus_scan_target,
    threat_feed_status as antivirus_threat_feed_status,
    threat_feed_update as antivirus_threat_feed_update,
    suppression_add as antivirus_suppression_add,
    suppression_list as antivirus_suppression_list,
    suppression_remove as antivirus_suppression_remove,
)
from zero_os.antivirus_agent import antivirus_agent_status, run_antivirus_agent
from zero_os.triad_balance import (
    run_triad_balance,
    triad_balance_status,
    triad_ops_set,
    triad_ops_status,
    triad_ops_tick,
)
from zero_os.self_repair import self_repair_run, self_repair_set, self_repair_status, self_repair_tick
from zero_os.security_hardening import harden_apply, harden_status, init_trust_root
from zero_os.enterprise_security import (
    adversarial_validate,
    enterprise_enable,
    enterprise_status,
    integration_configure,
    integration_probe,
    integration_status,
    preexec_check,
    rollback_playbook_run,
    set_role as enterprise_set_role,
    siem_emit,
    sign_action as enterprise_sign_action,
)


class SystemCapability:
    name = "system"

    def can_handle(self, task: Task) -> bool:
        keys = (
            "system",
            "core status",
            "system optimize all",
            "auto optimize",
            "auto merge",
            "ai files smart",
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
            "cure firewall agent",
            "mark strict",
            "mark status",
            "net strict",
            "net policy",
            "audit status",
            "code intake",
            "os readiness",
            "os missing fix",
            "beginner os",
            "sandbox",
            "update ",
            "deps ",
            "jobs ",
            "agent isolate",
            "observability",
            "snapshot ",
            "plugin sign",
            "plugin verify",
            "api token",
            "benchmark run",
            "error playbook",
            "release ",
            "znet ",
            "freedom ",
            "process ",
            "shell run ",
            "terminal run ",
            "powershell run ",
            "memory status",
            "memory smart",
            "filesystem status",
            "device status",
            "hardware capability map",
            "security overview",
            "zerofs ",
            "cleanup ",
            "storage smart",
            "hyperlayer",
            "antivirus",
            "triad balance",
            "balanced zero os",
            "triad ops",
            "zero ai agent monitor triad balance",
            "self repair",
            "auto self repair",
            "security harden",
            "trust root",
            "enterprise security",
            "enterprise role",
            "enterprise sign",
            "enterprise siem",
            "enterprise rollback",
            "enterprise validate",
            "enterprise integration",
        )
        text = task.text.lower()
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        raw = task.text.strip()
        text = raw.lower()
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

        if text.strip() == "antivirus status":
            data = {
                "feed": antivirus_threat_feed_status(task.cwd),
                "policy": antivirus_policy_status(task.cwd),
                "monitor": antivirus_monitor_status(task.cwd),
                "quarantine": antivirus_quarantine_list(task.cwd),
            }
            return Result(self.name, json.dumps(data, indent=2))
        if text.strip() in {"triad balance run", "balanced zero os", "3 balanced zero os"}:
            return Result(self.name, json.dumps(run_triad_balance(task.cwd), indent=2))
        if text.strip() == "triad balance status":
            return Result(self.name, json.dumps(triad_balance_status(task.cwd), indent=2))
        if text.strip() == "triad ops status":
            return Result(self.name, json.dumps(triad_ops_status(task.cwd), indent=2))
        triad_on = re.match(
            r"^triad ops on(?:\s+interval=(\d+))?(?:\s+sink=(log|inbox|log\+inbox))?$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if triad_on:
            iv = int(triad_on.group(1)) if triad_on.group(1) else None
            sink = triad_on.group(2) if triad_on.group(2) else None
            return Result(self.name, json.dumps(triad_ops_set(task.cwd, True, iv, sink), indent=2))
        if text.strip() == "triad ops off":
            return Result(self.name, json.dumps(triad_ops_set(task.cwd, False), indent=2))
        if text.strip() == "triad ops tick":
            return Result(self.name, json.dumps(triad_ops_tick(task.cwd), indent=2))
        if text.strip() in {
            "zero ai agent monitor triad balance",
            "zero ai monitor triad balance",
        }:
            tick = triad_ops_tick(task.cwd)
            if not tick.get("ran", False):
                triad_ops_set(task.cwd, True, 60, "log+inbox")
                tick = triad_ops_tick(task.cwd)
            report = tick.get("report", {})
            balanced = bool(report.get("balanced", False))
            alerts = report.get("antivirus_monitor", {}).get("finding_count", 0)
            readiness = report.get("zero_os", {}).get("readiness_score", 0)
            summary = (
                f"triad_balanced: {balanced}\n"
                f"triad_score: {report.get('triad_score', 0)}/{report.get('triad_total', 3)}\n"
                f"zero_os_readiness: {readiness}\n"
                f"antivirus_findings: {alerts}\n"
                f"playbook_actions: {json.dumps(report.get('playbook_actions', []))}\n"
                f"ops_enabled: {tick.get('ops', {}).get('enabled', False)}\n"
                f"last_tick_utc: {tick.get('ops', {}).get('last_tick_utc', '')}"
            )
            return Result(self.name, summary)
        if text.strip() in {"self repair run", "auto self repair everything", "add auto self repair everything"}:
            return Result(self.name, json.dumps(self_repair_run(task.cwd), indent=2))
        if text.strip() == "self repair status":
            return Result(self.name, json.dumps(self_repair_status(task.cwd), indent=2))
        self_on = re.match(r"^self repair on(?:\s+interval=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if self_on:
            iv = int(self_on.group(1)) if self_on.group(1) else None
            return Result(self.name, json.dumps(self_repair_set(task.cwd, True, iv), indent=2))
        if text.strip() == "self repair off":
            return Result(self.name, json.dumps(self_repair_set(task.cwd, False), indent=2))
        if text.strip() == "self repair tick":
            return Result(self.name, json.dumps(self_repair_tick(task.cwd), indent=2))
        if text.strip() in {"security harden apply", "go fix it all"}:
            return Result(self.name, json.dumps(harden_apply(task.cwd), indent=2))
        if text.strip() == "security harden status":
            return Result(self.name, json.dumps(harden_status(task.cwd), indent=2))
        if text.strip() == "security trust init":
            return Result(self.name, json.dumps(init_trust_root(task.cwd), indent=2))
        if text.strip() == "enterprise security status":
            return Result(self.name, json.dumps(enterprise_status(task.cwd), indent=2))
        if text.strip() == "enterprise integration status":
            return Result(self.name, json.dumps(integration_status(task.cwd), indent=2))
        ent_icfg = re.match(
            r"^enterprise integration set\s+(edr|siem|iam|zerotrust)\s+(on|off)(?:\s+provider=(\S+))?(?:\s+endpoint=(\S+))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if ent_icfg:
            name = ent_icfg.group(1).lower()
            enabled = ent_icfg.group(2).lower() == "on"
            provider = ent_icfg.group(3) or ""
            endpoint = ent_icfg.group(4) or ""
            return Result(self.name, json.dumps(integration_configure(task.cwd, name, enabled, provider, endpoint), indent=2))
        ent_iprobe = re.match(r"^enterprise integration probe\s+(edr|siem|iam|zerotrust)$", text.strip(), flags=re.IGNORECASE)
        if ent_iprobe:
            return Result(self.name, json.dumps(integration_probe(task.cwd, ent_iprobe.group(1)), indent=2))
        ent_on = re.match(r"^enterprise security on(?:\s+siem=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if ent_on:
            siem = ent_on.group(1) if ent_on.group(1) else None
            return Result(self.name, json.dumps(enterprise_enable(task.cwd, True, siem), indent=2))
        if text.strip() == "enterprise security off":
            return Result(self.name, json.dumps(enterprise_enable(task.cwd, False), indent=2))
        ent_role = re.match(r"^enterprise role set\s+([A-Za-z0-9._-]+)\s+(admin|operator|viewer)$", text.strip(), flags=re.IGNORECASE)
        if ent_role:
            return Result(self.name, json.dumps(enterprise_set_role(task.cwd, ent_role.group(1), ent_role.group(2)), indent=2))
        ent_sign = re.match(r"^enterprise sign action\s+user=([A-Za-z0-9._-]+)\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if ent_sign:
            return Result(self.name, json.dumps(enterprise_sign_action(task.cwd, ent_sign.group(1), ent_sign.group(2).strip()), indent=2))
        ent_siem = re.match(r"^enterprise siem emit\s+(low|medium|high|critical)\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if ent_siem:
            severity = ent_siem.group(1).lower()
            event = ent_siem.group(2).strip()
            return Result(self.name, json.dumps(siem_emit(task.cwd, event, severity, {"source": "system_command"}), indent=2))
        ent_rb = re.match(r"^enterprise rollback run\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if ent_rb:
            return Result(self.name, json.dumps(rollback_playbook_run(task.cwd, ent_rb.group(1)), indent=2))
        if text.strip() == "enterprise validate adversarial":
            return Result(self.name, json.dumps(adversarial_validate(task.cwd), indent=2))
        av_agent_run = re.match(
            r"^antivirus agent run(?:\s+(.+?))?(?:\s+auto_quarantine=(true|false|1|0|yes|no|on|off))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if av_agent_run:
            target = av_agent_run.group(1).strip().strip("\"'") if av_agent_run.group(1) else "."
            aq_raw = av_agent_run.group(2) or "false"
            aq = aq_raw.strip().lower() in {"1", "true", "yes", "on"}
            return Result(self.name, json.dumps(run_antivirus_agent(task.cwd, target=target, auto_quarantine=aq), indent=2))
        if text.strip() == "antivirus agent status":
            return Result(self.name, json.dumps(antivirus_agent_status(task.cwd), indent=2))
        if text.strip() == "antivirus feed status":
            return Result(self.name, json.dumps(antivirus_threat_feed_status(task.cwd), indent=2))
        if text.strip() == "antivirus feed update":
            return Result(self.name, json.dumps(antivirus_threat_feed_update(task.cwd), indent=2))
        av_feed_export = re.match(r"^antivirus feed export signed\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if av_feed_export:
            out_path = av_feed_export.group(1).strip().strip("\"'")
            return Result(self.name, json.dumps(antivirus_threat_feed_export_signed(task.cwd, out_path), indent=2))
        av_feed_import = re.match(r"^antivirus feed import signed\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if av_feed_import:
            in_path = av_feed_import.group(1).strip().strip("\"'")
            return Result(self.name, json.dumps(antivirus_threat_feed_import_signed(task.cwd, in_path), indent=2))
        av_scan = re.match(r"^antivirus scan(?:\s+(.+))?$", raw.strip(), flags=re.IGNORECASE)
        if av_scan:
            target = av_scan.group(1).strip().strip("\"'") if av_scan.group(1) else "."
            return Result(self.name, json.dumps(antivirus_scan_target(task.cwd, target), indent=2))
        if text.strip() == "antivirus quarantine list":
            return Result(self.name, json.dumps(antivirus_quarantine_list(task.cwd), indent=2))
        av_quarantine = re.match(r"^antivirus quarantine\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if av_quarantine:
            target = av_quarantine.group(1).strip().strip("\"'")
            return Result(self.name, json.dumps(antivirus_quarantine_file(task.cwd, target, reason="manual"), indent=2))
        av_restore = re.match(r"^antivirus restore\s+([a-z0-9]+)$", text.strip(), flags=re.IGNORECASE)
        if av_restore:
            return Result(self.name, json.dumps(antivirus_quarantine_restore(task.cwd, av_restore.group(1)), indent=2))
        av_policy = re.match(r"^antivirus policy set\s+([a-z_]+)\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if av_policy:
            key = av_policy.group(1).strip()
            value = av_policy.group(2).strip()
            try:
                updated = antivirus_policy_set(task.cwd, key, value)
            except ValueError:
                return Result(
                    self.name,
                    "supported policy keys: heuristic_threshold, auto_quarantine, max_files_per_scan, max_file_mb, archive_max_depth, archive_max_entries, restore_overwrite, response_mode",
                )
            return Result(self.name, json.dumps(updated, indent=2))
        if text.strip() == "antivirus policy show":
            return Result(self.name, json.dumps(antivirus_policy_status(task.cwd), indent=2))
        av_supp_add = re.match(
            r"^antivirus suppression add\s+([A-Za-z0-9._-]+)(?:\s+path=(\S+))?(?:\s+hours=(\d+))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if av_supp_add:
            sig = av_supp_add.group(1)
            pfx = av_supp_add.group(2) or ""
            hours = int(av_supp_add.group(3) or "24")
            return Result(self.name, json.dumps(antivirus_suppression_add(task.cwd, sig, pfx, hours), indent=2))
        if text.strip() == "antivirus suppression list":
            return Result(self.name, json.dumps(antivirus_suppression_list(task.cwd), indent=2))
        av_supp_rm = re.match(r"^antivirus suppression remove\s+([a-z0-9]+)$", text.strip(), flags=re.IGNORECASE)
        if av_supp_rm:
            return Result(self.name, json.dumps(antivirus_suppression_remove(task.cwd, av_supp_rm.group(1)), indent=2))
        av_mon_on = re.match(r"^antivirus monitor on(?:\s+interval=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if av_mon_on:
            iv = int(av_mon_on.group(1)) if av_mon_on.group(1) else None
            return Result(self.name, json.dumps(antivirus_monitor_set(task.cwd, True, iv), indent=2))
        if text.strip() == "antivirus monitor off":
            return Result(self.name, json.dumps(antivirus_monitor_set(task.cwd, False), indent=2))
        if text.strip() == "antivirus monitor status":
            return Result(self.name, json.dumps(antivirus_monitor_status(task.cwd), indent=2))
        av_mon_tick = re.match(r"^antivirus monitor tick(?:\s+(.+))?$", raw.strip(), flags=re.IGNORECASE)
        if av_mon_tick:
            target = av_mon_tick.group(1).strip().strip("\"'") if av_mon_tick.group(1) else "."
            return Result(self.name, json.dumps(antivirus_monitor_tick(task.cwd, target), indent=2))

        if text.strip() == "system optimize all":
            return Result(self.name, json.dumps(system_optimize_all(task.cwd), indent=2))
        if text.strip() == "auto optimize status":
            return Result(self.name, json.dumps(auto_optimize_status(task.cwd), indent=2))
        auto_on_m = re.match(r"^auto optimize on(?:\s+interval=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if auto_on_m:
            iv = int(auto_on_m.group(1)) if auto_on_m.group(1) else None
            return Result(self.name, json.dumps(auto_optimize_set(task.cwd, True, iv), indent=2))
        if text.strip() == "auto optimize off":
            return Result(self.name, json.dumps(auto_optimize_set(task.cwd, False), indent=2))
        if text.strip() == "auto merge status":
            return Result(self.name, json.dumps(auto_merge_status(task.cwd), indent=2))
        auto_merge_on_m = re.match(r"^auto merge on(?:\s+threshold=(0?\.\d+|\d{1,2}))?$", text.strip(), flags=re.IGNORECASE)
        if auto_merge_on_m:
            raw_th = auto_merge_on_m.group(1)
            threshold = float(raw_th) if raw_th is not None else None
            return Result(self.name, json.dumps(auto_merge_set(task.cwd, True, threshold), indent=2))
        if text.strip() == "auto merge off":
            return Result(self.name, json.dumps(auto_merge_set(task.cwd, False), indent=2))
        if text.strip() == "auto merge run":
            return Result(self.name, json.dumps(auto_merge_queue_run(task.cwd), indent=2))
        if text.strip() == "ai files smart status":
            return Result(self.name, json.dumps(ai_files_smart_status(task.cwd), indent=2))
        ai_files_on_m = re.match(r"^ai files smart on(?:\s+interval=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if ai_files_on_m:
            iv = int(ai_files_on_m.group(1)) if ai_files_on_m.group(1) else None
            return Result(self.name, json.dumps(ai_files_smart_set(task.cwd, True, iv), indent=2))
        if text.strip() == "ai files smart off":
            return Result(self.name, json.dumps(ai_files_smart_set(task.cwd, False), indent=2))
        if text.strip() == "ai files smart optimize":
            return Result(self.name, json.dumps(ai_files_smart_optimize(task.cwd), indent=2))

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

        if text.strip() == "os readiness --json":
            r = os_readiness(task.cwd)
            return Result(self.name, json.dumps(r, indent=2))

        if text.strip() == "os missing fix":
            r = apply_missing_fix(task.cwd)
            return Result(
                self.name,
                (
                    f"created_count: {r['created_count']}\n"
                    + ("\n".join(r["created"]) if r["created"] else "nothing created")
                ),
            )

        if text.strip() == "beginner os status":
            r = beginner_os_coverage(task.cwd)
            return Result(
                self.name,
                (
                    f"beginner_os_score: {r['score']}\n"
                    f"passed: {r['passed']}/{r['total']}\n"
                    f"missing: {', '.join(r['missing']) if r['missing'] else '(none)'}\n"
                    f"checks: {json.dumps(r['checks'], indent=2)}"
                ),
            )

        if text.strip() == "beginner os fix":
            r = apply_beginner_os_fix(task.cwd)
            return Result(
                self.name,
                (
                    f"created_count: {r['created_count']}\n"
                    + ("\n".join(r["created"]) if r["created"] else "nothing created")
                ),
            )

        if text.strip() == "sandbox status":
            return Result(self.name, json.dumps(sandbox_status(task.cwd), indent=2))
        sand = re.match(r"^sandbox (allow|deny)\s+(.+)$", text.strip(), flags=re.IGNORECASE)
        if sand:
            return Result(self.name, json.dumps(sandbox_update(task.cwd, sand.group(1).lower(), sand.group(2).strip()), indent=2))
        sand_check = re.match(r"^sandbox check\s+(.+)$", text.strip(), flags=re.IGNORECASE)
        if sand_check:
            ok, reason = sandbox_check(task.cwd, sand_check.group(1).strip())
            return Result(self.name, f"allowed: {ok}\nreason: {reason}")

        up_create = re.match(r"^update package create\s+([0-9A-Za-z._-]+)$", text.strip(), flags=re.IGNORECASE)
        if up_create:
            return Result(self.name, json.dumps(update_create(task.cwd, up_create.group(1)), indent=2))
        up_apply = re.match(r"^update apply\s+([0-9A-Za-z._-]+)$", text.strip(), flags=re.IGNORECASE)
        if up_apply:
            return Result(self.name, json.dumps(update_apply(task.cwd, up_apply.group(1)), indent=2))
        if text.strip() == "update rollback":
            return Result(self.name, json.dumps(update_rollback(task.cwd), indent=2))

        deps_add_m = re.match(r"^deps add\s+([A-Za-z0-9._-]+)\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if deps_add_m:
            return Result(self.name, json.dumps(deps_add(task.cwd, deps_add_m.group(1), deps_add_m.group(2)), indent=2))
        if text.strip() == "deps list":
            return Result(self.name, json.dumps(deps_list(task.cwd), indent=2))

        jobs_add_m = re.match(r"^jobs add\s+(\d+)\s+(.+)$", text.strip(), flags=re.IGNORECASE)
        if jobs_add_m:
            return Result(self.name, json.dumps(jobs_add(task.cwd, int(jobs_add_m.group(1)), jobs_add_m.group(2).strip()), indent=2))
        if text.strip() == "jobs list":
            return Result(self.name, json.dumps(jobs_list(task.cwd), indent=2))
        if text.strip() == "jobs run one":
            return Result(self.name, json.dumps(jobs_run_one(task.cwd), indent=2))

        isolate_set_m = re.match(r"^agent isolate set\s+([A-Za-z0-9._-]+)\s+cpu=(\d+)\s+mem=(\d+)$", text.strip(), flags=re.IGNORECASE)
        if isolate_set_m:
            return Result(self.name, json.dumps(isolation_set(task.cwd, isolate_set_m.group(1), int(isolate_set_m.group(2)), int(isolate_set_m.group(3))), indent=2))
        if text.strip() == "agent isolate list":
            return Result(self.name, json.dumps(isolation_list(task.cwd), indent=2))

        if text.strip() == "observability report":
            return Result(self.name, json.dumps(observability_report(task.cwd), indent=2))

        if text.strip() == "snapshot create":
            return Result(self.name, json.dumps(snapshot_create(task.cwd), indent=2))
        if text.strip() == "snapshot list":
            return Result(self.name, json.dumps(snapshot_list(task.cwd), indent=2))
        snap_restore_m = re.match(r"^snapshot restore\s+([0-9TZ]+)$", text.strip(), flags=re.IGNORECASE)
        if snap_restore_m:
            return Result(self.name, json.dumps(snapshot_restore(task.cwd, snap_restore_m.group(1)), indent=2))

        plugin_sign_m = re.match(r"^plugin sign\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if plugin_sign_m:
            return Result(self.name, json.dumps(plugin_sign(task.cwd, plugin_sign_m.group(1)), indent=2))
        plugin_verify_m = re.match(r"^plugin verify\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if plugin_verify_m:
            return Result(self.name, json.dumps(plugin_verify(task.cwd, plugin_verify_m.group(1)), indent=2))

        if text.strip() == "api token create":
            return Result(self.name, json.dumps(api_token_create(task.cwd), indent=2))
        api_verify_m = re.match(r"^api token verify\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if api_verify_m:
            return Result(self.name, json.dumps(api_token_verify(task.cwd, api_verify_m.group(1).strip()), indent=2))

        if text.strip() == "benchmark run":
            return Result(self.name, json.dumps(benchmark_run(task.cwd), indent=2))

        if text.strip() == "error playbook init":
            return Result(self.name, json.dumps(playbook_init(task.cwd), indent=2))
        if text.strip() == "error playbook show":
            return Result(self.name, json.dumps(playbook_show(task.cwd), indent=2))

        if text.strip() == "release init":
            return Result(self.name, json.dumps(release_init(task.cwd), indent=2))
        rel_bump_m = re.match(r"^release bump\s+([0-9A-Za-z._-]+)$", text.strip(), flags=re.IGNORECASE)
        if rel_bump_m:
            return Result(self.name, json.dumps(release_bump(task.cwd, rel_bump_m.group(1)), indent=2))

        if text.strip() == "freedom status":
            return Result(self.name, json.dumps(freedom_status(task.cwd), indent=2))
        freedom_mode_m = re.match(r"^freedom mode\s+(open|guarded)$", text.strip(), flags=re.IGNORECASE)
        if freedom_mode_m:
            return Result(self.name, json.dumps(freedom_mode_set(task.cwd, freedom_mode_m.group(1)), indent=2))
        if text.strip() == "freedom reset":
            return Result(self.name, json.dumps(freedom_reset(task.cwd), indent=2))

        if text.strip() == "process list":
            return Result(self.name, json.dumps(process_list(limit=20), indent=2))
        process_start_m = re.match(r"^process start\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if process_start_m:
            return Result(self.name, json.dumps(process_start(process_start_m.group(1), task.cwd), indent=2))
        process_kill_m = re.match(r"^process kill\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if process_kill_m:
            return Result(self.name, json.dumps(process_kill(process_kill_m.group(1)), indent=2))
        shell_run_m = re.match(r"^(?:shell|terminal|powershell) run\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if shell_run_m:
            cmd = shell_run_m.group(1).strip()
            allowed, reason = sandbox_check(task.cwd, cmd)
            if not allowed:
                return Result(self.name, json.dumps({"ok": False, "reason": reason, "command": cmd}, indent=2))
            ent_allowed, ent_reason = preexec_check(task.cwd, f"shell run {cmd}", user="owner")
            if not ent_allowed:
                return Result(self.name, json.dumps({"ok": False, "reason": ent_reason, "command": cmd}, indent=2))
            return Result(self.name, json.dumps(unified_shell_run(cmd, task.cwd), indent=2))

        if text.strip() == "memory status":
            return Result(self.name, json.dumps(memory_status(), indent=2))
        if text.strip() == "memory smart status":
            return Result(self.name, json.dumps(memory_smart_status(task.cwd), indent=2))
        if text.strip() == "memory smart optimize":
            return Result(self.name, json.dumps(memory_smart_optimize(task.cwd), indent=2))
        if text.strip() == "filesystem status":
            return Result(self.name, json.dumps(filesystem_status(task.cwd), indent=2))
        if text.strip() == "device status":
            return Result(self.name, json.dumps(device_status(), indent=2))
        if text.strip() == "hardware capability map":
            return Result(self.name, json.dumps(hardware_capability_map(task.cwd), indent=2))
        if text.strip() == "security overview":
            return Result(self.name, json.dumps(security_overview(task.cwd), indent=2))

        if text.strip() in {"cleanup status", "cleanup dry run"}:
            return Result(self.name, json.dumps(cleanup_status(task.cwd), indent=2))
        cleanup_apply_m = re.match(r"^cleanup apply(?:\s+stale=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if cleanup_apply_m:
            stale = int(cleanup_apply_m.group(1) or "30")
            return Result(self.name, json.dumps(cleanup_apply(task.cwd, stale_days=stale), indent=2))

        if text.strip() == "storage smart status":
            return Result(self.name, json.dumps(storage_smart_status(task.cwd), indent=2))
        storage_opt_m = re.match(r"^storage smart optimize(?:\s+min_kb=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if storage_opt_m:
            min_kb = int(storage_opt_m.group(1) or "64")
            return Result(self.name, json.dumps(storage_smart_optimize(task.cwd, min_kb=min_kb), indent=2))
        storage_restore_m = re.match(r"^storage smart restore\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if storage_restore_m:
            return Result(self.name, json.dumps(storage_smart_restore(task.cwd, storage_restore_m.group(1).strip().strip("\"'")), indent=2))
        if text.strip() == "hyperlayer status":
            return Result(self.name, json.dumps(hyperlayer_status(), indent=2))

        if text.strip() == "zerofs init":
            return Result(self.name, json.dumps(zerofs_init(task.cwd), indent=2))
        if text.strip() == "zerofs status":
            return Result(self.name, json.dumps(zerofs_status(task.cwd), indent=2))
        zerofs_put_m = re.match(r"^zerofs put\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if zerofs_put_m:
            return Result(self.name, json.dumps(zerofs_put(task.cwd, zerofs_put_m.group(1).strip().strip("\"'")), indent=2))
        zerofs_get_m = re.match(r"^zerofs get\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if zerofs_get_m:
            return Result(self.name, json.dumps(zerofs_get(task.cwd, zerofs_get_m.group(1).strip().strip("\"'")), indent=2))
        if text.strip() == "zerofs list":
            return Result(self.name, json.dumps(zerofs_list(task.cwd), indent=2))
        zerofs_del_m = re.match(r"^zerofs delete\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if zerofs_del_m:
            return Result(self.name, json.dumps(zerofs_delete(task.cwd, zerofs_del_m.group(1).strip().strip("\"'")), indent=2))

        znet_init_m = re.match(r"^znet init\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if znet_init_m:
            return Result(self.name, json.dumps(znet_init(task.cwd, znet_init_m.group(1)), indent=2))
        if text.strip() == "znet status":
            return Result(self.name, json.dumps(znet_status(task.cwd), indent=2))
        znet_node_m = re.match(r"^znet node add\s+([A-Za-z0-9._-]+)\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if znet_node_m:
            return Result(self.name, json.dumps(znet_add_node(task.cwd, znet_node_m.group(1), znet_node_m.group(2)), indent=2))
        znet_service_m = re.match(
            r"^znet service add\s+([A-Za-z0-9._-]+)\s+node=([A-Za-z0-9._-]+)\s+path=(\S+)$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if znet_service_m:
            return Result(
                self.name,
                json.dumps(
                    znet_add_service(task.cwd, znet_service_m.group(1), znet_service_m.group(2), znet_service_m.group(3)),
                    indent=2,
                ),
            )
        znet_resolve_m = re.match(r"^znet resolve\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if znet_resolve_m:
            return Result(self.name, json.dumps(znet_resolve(task.cwd, znet_resolve_m.group(1)), indent=2))
        if text.strip() == "znet topology":
            return Result(self.name, json.dumps(znet_topology(task.cwd), indent=2))
        znet_cure_m = re.match(r"^znet cure apply pressure\s+(\d+)$", text.strip(), flags=re.IGNORECASE)
        if znet_cure_m:
            return Result(self.name, json.dumps(znet_cure_apply(task.cwd, int(znet_cure_m.group(1))), indent=2))
        if text.strip() == "znet cure status":
            return Result(self.name, json.dumps(znet_cure_status(task.cwd), indent=2))

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
            if result.backup_path:
                lines.append(f"backup: {result.backup_path}")
            return Result(self.name, "\n".join(lines))

        cure_agent_run = re.match(
            r"^cure firewall agent run(?:\s+pressure\s+(\d+))?$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if cure_agent_run:
            pressure = int(cure_agent_run.group(1) or "80")
            report = run_cure_firewall_agent(task.cwd, pressure=pressure)
            return Result(self.name, json.dumps(report, indent=2))

        cure_agent_file = re.match(
            r"^cure firewall agent file\s+(.+?)(?:\s+pressure\s+(\d+))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if cure_agent_file:
            target = cure_agent_file.group(1).strip().strip("\"'")
            pressure = int(cure_agent_file.group(2) or "80")
            report = run_cure_firewall_agent(task.cwd, pressure=pressure, targets=[target])
            return Result(self.name, json.dumps(report, indent=2))

        cure_agent_net = re.match(
            r"^cure firewall agent net\s+(.+?)(?:\s+pressure\s+(\d+))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if cure_agent_net:
            url = cure_agent_net.group(1).strip().strip("\"'")
            pressure = int(cure_agent_net.group(2) or "80")
            report = run_cure_firewall_agent(task.cwd, pressure=pressure, urls=[url])
            return Result(self.name, json.dumps(report, indent=2))

        if text.strip() == "cure firewall agent status":
            return Result(self.name, json.dumps(cure_firewall_agent_status(task.cwd), indent=2))

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
        cure_restore = re.match(r"^cure firewall restore\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if cure_restore:
            rel = cure_restore.group(1).strip().strip("\"'")
            return Result(self.name, json.dumps(restore_from_cure_backup(task.cwd, rel), indent=2))

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
            "- system optimize all\n"
            "- auto optimize status\n"
            "- auto optimize on [interval=<minutes>]\n"
            "- auto optimize off\n"
            "- auto merge status\n"
            "- auto merge on [threshold=<0.50..0.99>]\n"
            "- auto merge off\n"
            "- auto merge run\n"
            "- ai files smart status\n"
            "- ai files smart on [interval=<minutes>]\n"
            "- ai files smart off\n"
            "- ai files smart optimize\n"
            "- auto upgrade\n"
            "- plugin scaffold <name>\n"
            "- law status\n"
            "- law export\n"
            "- cure firewall run <path> pressure <0-100>\n"
            "- cure firewall verify <path>\n"
            "- cure firewall restore <path>\n"
            "- cure firewall net run <url> pressure <0-100>\n"
            "- cure firewall net verify <url>\n"
            "- cure firewall agent run [pressure <0-100>]\n"
            "- cure firewall agent file <path> [pressure <0-100>]\n"
            "- cure firewall agent net <url> [pressure <0-100>]\n"
            "- cure firewall agent status\n"
            "- mark strict on|off|show\n"
            "- mark status <path>\n"
            "- net strict on|off|show\n"
            "- net policy show|allow|deny|remove <domain>\n"
            "- audit status\n"
            "- code intake <path>\n"
            "- os readiness\n"
            "- os readiness --json\n"
            "- os missing fix\n"
            "- beginner os status\n"
            "- beginner os fix\n"
            "- shell run <command>\n"
            "- terminal run <command>\n"
            "- powershell run <command>\n"
            "- hardware capability map\n"
            "- cleanup status\n"
            "- cleanup dry run\n"
            "- cleanup apply [stale=<days>]\n"
            "- storage smart status\n"
            "- storage smart optimize [min_kb=<n>]\n"
            "- storage smart restore <path>\n"
            "- hyperlayer status\n"
            "- znet init <name>\n"
            "- znet status\n"
            "- znet node add <node> <https://endpoint>\n"
            "- znet service add <service> node=<node> path=</route>\n"
            "- znet resolve <service|node>\n"
            "- znet topology\n"
            "- znet cure apply pressure <0-100>\n"
            "- znet cure status\n"
            "- antivirus status\n"
            "- triad balance run\n"
            "- triad balance status\n"
            "- triad ops status\n"
            "- triad ops on [interval=<seconds>] [sink=log|inbox|log+inbox]\n"
            "- triad ops off\n"
            "- triad ops tick\n"
            "- zero ai agent monitor triad balance\n"
            "- self repair run\n"
            "- self repair status\n"
            "- self repair on [interval=<seconds>]\n"
            "- self repair off\n"
            "- self repair tick\n"
            "- security harden apply\n"
            "- security harden status\n"
            "- security trust init\n"
            "- enterprise security status\n"
            "- enterprise security on [siem=<webhook_url>]\n"
            "- enterprise security off\n"
            "- enterprise role set <user> <admin|operator|viewer>\n"
            "- enterprise integration status\n"
            "- enterprise integration set <edr|siem|iam|zerotrust> <on|off> [provider=<name>] [endpoint=<url_or_tenant>]\n"
            "- enterprise integration probe <edr|siem|iam|zerotrust>\n"
            "- enterprise sign action user=<user> <action_text>\n"
            "- enterprise siem emit <low|medium|high|critical> <event>\n"
            "- enterprise rollback run <critical|ransomware|integrity_failure>\n"
            "- enterprise validate adversarial\n"
            "- antivirus agent run [path] [auto_quarantine=true|false]\n"
            "- antivirus agent status\n"
            "- antivirus feed status\n"
            "- antivirus feed update\n"
            "- antivirus feed export signed <path>\n"
            "- antivirus feed import signed <path>\n"
            "- antivirus scan [path]\n"
            "- antivirus quarantine <path>\n"
            "- antivirus quarantine list\n"
            "- antivirus restore <id>\n"
            "- antivirus policy show\n"
            "- antivirus policy set heuristic_threshold <0-100>\n"
            "- antivirus policy set auto_quarantine <true|false>\n"
            "- antivirus policy set max_files_per_scan <n>\n"
            "- antivirus policy set max_file_mb <n>\n"
            "- antivirus policy set archive_max_depth <n>\n"
            "- antivirus policy set archive_max_entries <n>\n"
            "- antivirus policy set restore_overwrite <true|false>\n"
            "- antivirus policy set response_mode <manual|quarantine_high|quarantine_critical>\n"
            "- antivirus suppression add <signature_id> [path=<prefix>] [hours=<n>]\n"
            "- antivirus suppression list\n"
            "- antivirus suppression remove <id>\n"
            "- antivirus monitor on [interval=<seconds>]\n"
            "- antivirus monitor off\n"
            "- antivirus monitor status\n"
            "- antivirus monitor tick [path]"
        )

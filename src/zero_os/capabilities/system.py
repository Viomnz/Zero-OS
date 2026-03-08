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
from zero_os.security_hardening import (
    harden_apply,
    harden_status,
    init_trust_root,
    zero_ai_security_apply,
    zero_ai_security_status,
)
from zero_os.enterprise_security import (
    adversarial_validate,
    enterprise_enable,
    enterprise_status,
    integration_bootstrap_local,
    integration_configure,
    integration_probe,
    integration_status,
    policy_lock_apply,
    preexec_check,
    rollout_set,
    rollout_status,
    rollback_playbook_run,
    set_role as enterprise_set_role,
    siem_emit,
    sign_action as enterprise_sign_action,
)
from zero_os.maturity import maturity_scaffold_all, maturity_status
from zero_os.smart_logic_governance import decide_false_positive, list_false_positive_reviews
from zero_os.harmony import zero_ai_harmony_status
from zero_os.knowledge_map import build_knowledge_index, knowledge_find, knowledge_status
from zero_os.recovery import zero_ai_backup_create, zero_ai_backup_status, zero_ai_recover
from zero_os.brain_awareness import brain_awareness_status, build_brain_awareness
from zero_os.zero_ai_sync import zero_ai_sync_all
from zero_os.zero_ai_identity import zero_ai_identity
from zero_os.consciousness_core import consciousness_status, consciousness_tick
from zero_os.gap_coverage import zero_ai_gap_fix, zero_ai_gap_status
from zero_os.conscious_machine_architecture import (
    consciousness_architecture_long_term_memory_status,
    consciousness_architecture_silicon_awareness_status,
    consciousness_architecture_hybrid_crystal_status,
    consciousness_architecture_clc_status,
    consciousness_architecture_tif_status,
    consciousness_architecture_sgoe_status,
    consciousness_architecture_rce_status,
    consciousness_architecture_phase9_status,
    consciousness_architecture_phase8_status,
    consciousness_architecture_phase7_status,
    consciousness_architecture_phase6_status,
    consciousness_architecture_phase5_status,
    consciousness_architecture_phase4_status,
    consciousness_architecture_phase3_status,
    consciousness_architecture_phase2_status,
    consciousness_architecture_status,
)
from zero_os.ops_maturity import (
    alert_routing_emit,
    alert_routing_set,
    alert_routing_status,
    dr_drill,
    enterprise_max_maturity_apply,
    immutable_audit_export,
    key_revoke,
    key_rotate,
    key_status,
    rollout_apply,
    runbooks_sync,
)
from zero_os.phase_runtime import zero_ai_runtime_run, zero_ai_runtime_status
from zero_os.runtime_coupling import (
    adversarial_runtime_validate,
    benchmark_dashboard_export,
    independent_validate,
    node_bus_consensus,
    node_bus_publish,
    runtime_preexec_gate,
    slo_monitor,
    telemetry_ingest,
)
from zero_os.architecture_runtime import (
    architecture_explain,
    architecture_measure,
    architecture_run,
    architecture_status,
    architecture_verify,
)
from zero_os.kernel_rnd.foundation_status import kernel_foundation_status
from zero_os.kernel_rnd.runtime_stack import (
    block_driver_set,
    display_driver_set,
    driver_load,
    driver_unload,
    fs_journal_set,
    fs_mount,
    fs_read,
    fs_recovery_run,
    fs_write,
    input_driver_set,
    kernel_stack_status,
    memory_alloc,
    memory_free,
    net_protocol_set,
    net_iface_add,
    nic_driver_set,
    net_route_add,
    platform_topology_set,
    scheduler_enqueue,
    scheduler_tick,
)
from zero_os.kernel_rnd.native_boot_ops import (
    boot_verify,
    elf_load,
    loader_status,
    measured_boot_record,
    measured_boot_status,
    module_load,
    panic_recover,
    panic_status,
    panic_trigger,
    secure_boot_set,
    uefi_scaffold,
    uefi_status,
)
from zero_os.real_os_status import real_os_status
from zero_os.rate_limit import check_and_record
from zero_os.app_store_universal import (
    detect_device as store_detect_device,
    list_packages as store_list_packages,
    publish_package as store_publish_package,
    resolve_package as store_resolve_package,
    security_scan as store_security_scan,
    validate_package as store_validate_package,
)
from zero_os.universal_runtime_ecosystem import (
    adapter_set as ure_adapter_set,
    adapters_status as ure_adapters_status,
    coverage_status as ure_coverage_status,
    execution_flow as ure_execution_flow,
    infrastructure_status as ure_infra_status,
    runtime_install as ure_runtime_install,
    runtime_status as ure_runtime_status,
    security_status as ure_security_status,
)
from zero_os.app_store_production_ops import (
    abuse_block_ip as store_abuse_block_ip,
    account_create as store_account_create,
    analytics_status as store_analytics_status,
    billing_charge as store_billing_charge,
    compliance_set as store_compliance_set,
    compliance_status as store_compliance_status,
    install_app as store_install_app,
    license_grant as store_license_grant,
    review_add as store_review_add,
    search_apps as store_search_apps,
    security_enforce as store_security_enforce,
    slo_set as store_slo_set,
    storage_replicate as store_storage_replicate,
    storage_rollback as store_storage_rollback,
    telemetry_status as store_telemetry_status,
    uninstall_app as store_uninstall_app,
    upgrade_app as store_upgrade_app,
)
from zero_os.global_runtime_network import (
    adaptive_mode as grn_adaptive_mode,
    cache_put as grn_cache_put,
    cache_status as grn_cache_status,
    network_status as grn_network_status,
    node_discovery as grn_node_discovery,
    node_register as grn_node_register,
    runtime_release_propagate as grn_runtime_release_propagate,
    security_validate as grn_security_validate,
    telemetry_status as grn_telemetry_status,
)
from zero_os.runtime_protocol_v1 import (
    adapter_allowlist_set as rp_adapter_allowlist_set,
    adapter_contract as rp_adapter_contract,
    audit_status as rp_audit_status,
    capability_handshake as rp_capability_handshake,
    capability_handshake_secure as rp_capability_handshake_secure,
    compatibility_check as rp_compatibility_check,
    deprecation_add as rp_deprecation_add,
    handshake_proof_preview as rp_handshake_proof_preview,
    key_rotate as rp_key_rotate,
    nonce_issue as rp_nonce_issue,
    package_attest as rp_package_attest,
    package_verify as rp_package_verify,
    protocol_status as rp_protocol_status,
    security_grade as rp_security_grade,
    maximize_security as rp_maximize_security,
    security_set as rp_security_set,
    security_status as rp_security_status,
    signer_allow as rp_signer_allow,
    signer_revoke as rp_signer_revoke,
)
from zero_os.runtime_protocol_ecosystem import (
    ecosystem_grade as rpe_grade,
    ecosystem_maximize as rpe_maximize,
    ecosystem_status as rpe_status,
)
from zero_os.rcrp import (
    device_profile_set as rcrp_device_profile_set,
    graph_register as rcrp_graph_register,
    learning_observe as rcrp_learning_observe,
    mesh_node_register as rcrp_mesh_node_register,
    migrate as rcrp_migrate,
    plan_build as rcrp_plan_build,
    status as rcrp_status,
    token_set as rcrp_token_set,
)
from zero_os.serp import (
    analyze as serp_analyze,
    deploy_staged as serp_deploy_staged,
    mutation_propose as serp_mutation_propose,
    rollback as serp_rollback,
    state_export as serp_state_export,
    state_import as serp_state_import,
    status as serp_status,
    telemetry_submit as serp_telemetry_submit,
)
from zero_os.autonomous_runtime_ecosystem import (
    ai_optimize as are_ai_optimize,
    ecosystem_grade as are_grade,
    governance_propose as are_gov_propose,
    governance_rollout as are_gov_rollout,
    governance_simulate as are_gov_simulate,
    governance_validate as are_gov_validate,
    maximize as are_maximize,
    node_register as are_node_register,
    status as are_status,
)
from zero_os.hardware_runtime_fabric import (
    evolve_application as hrf_evolve_application,
    fabric_dispatch as hrf_fabric_dispatch,
    fabric_node_register as hrf_fabric_node_register,
    fabric_status as hrf_fabric_status,
    hardware_maximize as hrf_hardware_maximize,
    hardware_set as hrf_hardware_set,
    memory_get as hrf_memory_get,
    memory_learn as hrf_memory_learn,
    status as hrf_status,
)
from zero_os.ria import (
    execute as ria_execute,
    program_register as ria_program_register,
    program_validate as ria_program_validate,
    status as ria_status,
)
from zero_os.runtime_economy import (
    actor_register as re_actor_register,
    contribution_record as re_contribution_record,
    payout as re_payout,
    status as re_status,
)
from zero_os.platform_blueprint import (
    scaffold as pb_scaffold,
    status as pb_status,
)
from zero_os.native_store_backend import (
    backup_db as nsb_backup_db,
    charge_user as nsb_charge_user,
    create_user as nsb_create_user,
    init_db as nsb_init_db,
    issue_token as nsb_issue_token,
    record_event as nsb_record_event,
    restore_db as nsb_restore_db,
    scaffold_deploy as nsb_scaffold_deploy,
    status as nsb_status,
)
from zero_os.native_store_desktop import (
    launch as nsd_launch,
    scaffold as nsd_scaffold,
)
from zero_os.native_store_enterprise_ops import (
    backend_prod_set as nseo_backend_prod_set,
    deployed_test_record as nseo_deployed_test_record,
    desktop_prod_set as nseo_desktop_prod_set,
    ops_governance_set as nseo_ops_governance_set,
    secrets_platform_set as nseo_secrets_platform_set,
    signing_provider_set as nseo_signing_provider_set,
    status as nseo_status,
    vendor_channel_configure as nseo_vendor_channel_configure,
)
from zero_os.native_app_store import (
    backend_integrate as nas_backend_integrate,
    build_linux_native as nas_build_linux_native,
    build_macos_native as nas_build_macos_native,
    build_mobile_distribution as nas_build_mobile_distribution,
    build_windows_native as nas_build_windows_native,
    cert_rotate as nas_cert_rotate,
    e2e_runner as nas_e2e_runner,
    gui_set as nas_gui_set,
    incident_open as nas_incident_open,
    install as nas_install,
    installer_service_set as nas_installer_service_set,
    maximize as nas_maximize,
    notarize_release as nas_notarize_release,
    pipeline_run as nas_pipeline_run,
    release_prepare as nas_release_prepare,
    rollback_checkpoint as nas_rollback_checkpoint,
    rollback_restore as nas_rollback_restore,
    scaffold_backend as nas_scaffold_backend,
    scaffold_desktop_production as nas_scaffold_desktop_production,
    scaffold_gui_client as nas_scaffold_gui_client,
    scaffold_installer_services as nas_scaffold_installer_services,
    scaffold_vendor_artifacts as nas_scaffold_vendor_artifacts,
    secret_set as nas_secret_set,
    sign_artifact as nas_sign_artifact,
    status as nas_status,
    stress_test as nas_stress_test,
    trust_channel_set as nas_trust_channel_set,
    uninstall as nas_uninstall,
    upgrade as nas_upgrade,
    verify_artifact as nas_verify_artifact,
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
            "rollout",
            "policy lock",
            "maturity status",
            "maturity scaffold all",
            "false positive",
            "zero ai harmony",
            "zero ai knowledge",
            "zero ai know everything",
            "zero ai backup",
            "zero ai recover",
            "zero ai security",
            "zero ai brain awareness",
            "zero ai fix all",
            "go fix all",
            "fix all now",
            "zero ai identity",
            "zero ai consciousness",
            "conscious machine architecture",
            "reflexive causality engine",
            "self-generating ontology engine",
            "temporal identity field",
            "crystal lattice cognition",
            "hybrid crystal cognition architecture",
            "silicon awareness machine",
            "strong persistent long-term memory",
            "zero ai gap",
            "cover gap",
            "enterprise key",
            "immutable audit",
            "alert routing",
            "dr drill",
            "max maturity",
            "runbooks",
            "zero ai runtime",
            "phase runtime",
            "runtime telemetry",
            "runtime node",
            "runtime adversarial",
            "runtime dashboard",
            "runtime slo",
            "runtime validate",
            "architecture run",
            "architecture verify",
            "architecture measure",
            "architecture explain",
            "kernel foundation",
            "real os status",
            "os reality status",
            "kernel stack",
            "kernel scheduler",
            "kernel memory",
            "kernel driver",
            "kernel fs",
            "kernel net",
            "kernel block",
            "kernel nic",
            "kernel journal",
            "kernel fs write",
            "kernel fs read",
            "kernel fs recover",
            "kernel net protocol",
            "kernel input",
            "kernel display",
            "kernel acpi",
            "kernel apic",
            "kernel smp",
            "kernel platform",
            "kernel uefi",
            "kernel elf",
            "kernel module",
            "kernel panic",
            "kernel secure boot",
            "kernel measured boot",
            "kernel boot verify",
            "store ",
            "app store",
            "universal runtime",
            "universal ",
            "os adapter",
            "ecosystem coverage",
            "runtime network",
            "runtime node",
            "runtime protocol",
            "runtime protocol ecosystem",
            "rcrp ",
            "recursive capability runtime protocol",
            "serp ",
            "self-evolving runtime protocol",
            "autonomous runtime ecosystem",
            "hardware runtime",
            "runtime fabric",
            "ria ",
            "runtime economy",
            "platform blueprint",
            "idea to platform",
            "native store",
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

        if text.strip() in {"kernel foundation status", "kernel status"}:
            return Result(self.name, json.dumps(kernel_foundation_status(task.cwd), indent=2))
        if text.strip() in {"real os status", "os reality status"}:
            return Result(self.name, json.dumps(real_os_status(task.cwd), indent=2))
        if text.strip() in {"kernel stack status", "kernel runtime status"}:
            return Result(self.name, json.dumps(kernel_stack_status(task.cwd), indent=2))
        ks_enq = re.match(
            r"^kernel scheduler enqueue\s+([A-Za-z0-9._-]+)(?:\s+priority=(-?\d+))?(?:\s+slice=(\d+))?$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if ks_enq:
            pri = int(ks_enq.group(2)) if ks_enq.group(2) else 0
            slc = int(ks_enq.group(3)) if ks_enq.group(3) else 10
            return Result(self.name, json.dumps(scheduler_enqueue(task.cwd, ks_enq.group(1), pri, slc), indent=2))
        if text.strip() == "kernel scheduler tick":
            return Result(self.name, json.dumps(scheduler_tick(task.cwd), indent=2))
        km_alloc = re.match(r"^kernel memory alloc\s+([A-Za-z0-9._-]+)(?:\s+pages=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if km_alloc:
            pages = int(km_alloc.group(2)) if km_alloc.group(2) else 1
            return Result(self.name, json.dumps(memory_alloc(task.cwd, km_alloc.group(1), pages), indent=2))
        km_free = re.match(r"^kernel memory free\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if km_free:
            return Result(self.name, json.dumps(memory_free(task.cwd, km_free.group(1)), indent=2))
        kd_load = re.match(r"^kernel driver load\s+([A-Za-z0-9._-]+)(?:\s+version=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if kd_load:
            ver = kd_load.group(2) if kd_load.group(2) else "dev"
            return Result(self.name, json.dumps(driver_load(task.cwd, kd_load.group(1), ver), indent=2))
        kd_unload = re.match(r"^kernel driver unload\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if kd_unload:
            return Result(self.name, json.dumps(driver_unload(task.cwd, kd_unload.group(1)), indent=2))
        kfs_mount = re.match(
            r"^kernel fs mount\s+([A-Za-z0-9._-]+)\s+path=(\S+)(?:\s+type=(\S+))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if kfs_mount:
            fs_type = kfs_mount.group(3) if kfs_mount.group(3) else "vfs"
            return Result(self.name, json.dumps(fs_mount(task.cwd, kfs_mount.group(1), kfs_mount.group(2), fs_type), indent=2))
        kn_if = re.match(r"^kernel net iface add\s+([A-Za-z0-9._-]+)\s+cidr=(\S+)$", text.strip(), flags=re.IGNORECASE)
        if kn_if:
            return Result(self.name, json.dumps(net_iface_add(task.cwd, kn_if.group(1), kn_if.group(2)), indent=2))
        kn_route = re.match(r"^kernel net route add\s+(\S+)\s+via=(\S+)$", text.strip(), flags=re.IGNORECASE)
        if kn_route:
            return Result(self.name, json.dumps(net_route_add(task.cwd, kn_route.group(1), kn_route.group(2)), indent=2))
        kb_drv = re.match(r"^kernel block driver\s+(ahci|nvme|virtio-blk)\s+(on|off)(?:\s+version=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if kb_drv:
            ver = kb_drv.group(3) if kb_drv.group(3) else "dev"
            return Result(self.name, json.dumps(block_driver_set(task.cwd, kb_drv.group(1), kb_drv.group(2).lower() == "on", ver), indent=2))
        kfs_j = re.match(r"^kernel fs journal\s+(on|off)$", text.strip(), flags=re.IGNORECASE)
        if kfs_j:
            return Result(self.name, json.dumps(fs_journal_set(task.cwd, kfs_j.group(1).lower() == "on"), indent=2))
        kfs_w = re.match(r"^kernel fs write\s+([A-Za-z0-9._-]+)\s+path=(\S+)\s+data=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if kfs_w:
            return Result(self.name, json.dumps(fs_write(task.cwd, kfs_w.group(1), kfs_w.group(2), kfs_w.group(3)), indent=2))
        kfs_r = re.match(r"^kernel fs read\s+([A-Za-z0-9._-]+)\s+path=(\S+)$", text.strip(), flags=re.IGNORECASE)
        if kfs_r:
            return Result(self.name, json.dumps(fs_read(task.cwd, kfs_r.group(1), kfs_r.group(2)), indent=2))
        if text.strip() == "kernel fs recover":
            return Result(self.name, json.dumps(fs_recovery_run(task.cwd), indent=2))
        kn_proto = re.match(r"^kernel net protocol\s+(arp|ip|tcp|udp|dhcp|dns)\s+(on|off)$", text.strip(), flags=re.IGNORECASE)
        if kn_proto:
            return Result(self.name, json.dumps(net_protocol_set(task.cwd, kn_proto.group(1), kn_proto.group(2).lower() == "on"), indent=2))
        kn_nic = re.match(r"^kernel nic driver set\s+([A-Za-z0-9._-]+)\s+driver=(\S+)(?:\s+(on|off))?$", raw.strip(), flags=re.IGNORECASE)
        if kn_nic:
            enabled = (kn_nic.group(3) or "on").lower() == "on"
            return Result(self.name, json.dumps(nic_driver_set(task.cwd, kn_nic.group(1), kn_nic.group(2), enabled), indent=2))
        kin = re.match(r"^kernel input\s+(keyboard|mouse)\s+driver=(\S+)\s+(on|off)$", text.strip(), flags=re.IGNORECASE)
        if kin:
            return Result(self.name, json.dumps(input_driver_set(task.cwd, kin.group(1), kin.group(2), kin.group(3).lower() == "on"), indent=2))
        kdisp = re.match(r"^kernel display driver\s+(\S+)\s+mode=(\S+)$", text.strip(), flags=re.IGNORECASE)
        if kdisp:
            return Result(self.name, json.dumps(display_driver_set(task.cwd, kdisp.group(1), kdisp.group(2)), indent=2))
        ktop = re.match(
            r"^kernel platform set(?:\s+acpi=(on|off))?(?:\s+apic=(on|off))?(?:\s+smp=(on|off))?(?:\s+cpus=(\d+))?$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if ktop:
            acpi = None if not ktop.group(1) else (ktop.group(1).lower() == "on")
            apic = None if not ktop.group(2) else (ktop.group(2).lower() == "on")
            smp = None if not ktop.group(3) else (ktop.group(3).lower() == "on")
            cpus = None if not ktop.group(4) else int(ktop.group(4))
            return Result(self.name, json.dumps(platform_topology_set(task.cwd, acpi, apic, smp, cpus), indent=2))
        if text.strip() == "kernel uefi status":
            return Result(self.name, json.dumps(uefi_status(task.cwd), indent=2))
        if text.strip() == "kernel uefi scaffold":
            return Result(self.name, json.dumps(uefi_scaffold(task.cwd), indent=2))
        kelf = re.match(r"^kernel elf load\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if kelf:
            return Result(self.name, json.dumps(elf_load(task.cwd, kelf.group(1)), indent=2))
        kmod = re.match(r"^kernel module load\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if kmod:
            return Result(self.name, json.dumps(module_load(task.cwd, kmod.group(1)), indent=2))
        if text.strip() in {"kernel modules status", "kernel loaders status"}:
            return Result(self.name, json.dumps(loader_status(task.cwd), indent=2))
        kpanic = re.match(r"^kernel panic trigger\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if kpanic:
            return Result(self.name, json.dumps(panic_trigger(task.cwd, kpanic.group(1)), indent=2))
        if text.strip() == "kernel panic status":
            return Result(self.name, json.dumps(panic_status(task.cwd), indent=2))
        if text.strip() == "kernel panic recover":
            return Result(self.name, json.dumps(panic_recover(task.cwd), indent=2))
        ksboot = re.match(r"^kernel secure boot\s+(on|off)(?:\s+pk=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if ksboot:
            return Result(self.name, json.dumps(secure_boot_set(task.cwd, ksboot.group(1).lower() == "on", ksboot.group(2) or ""), indent=2))
        kmb = re.match(r"^kernel measured boot record\s+([A-Za-z0-9._-]+)\s+path=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if kmb:
            return Result(self.name, json.dumps(measured_boot_record(task.cwd, kmb.group(1), kmb.group(2)), indent=2))
        if text.strip() == "kernel measured boot status":
            return Result(self.name, json.dumps(measured_boot_status(task.cwd), indent=2))
        kbv = re.match(r"^kernel boot verify\s+(\S+)\s+sha256=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if kbv:
            return Result(self.name, json.dumps(boot_verify(task.cwd, kbv.group(1), kbv.group(2)), indent=2))
        s_validate = re.match(r"^store validate\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if s_validate:
            return Result(self.name, json.dumps(store_validate_package(task.cwd, s_validate.group(1)), indent=2))
        s_publish = re.match(r"^store publish\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if s_publish:
            return Result(self.name, json.dumps(store_publish_package(task.cwd, s_publish.group(1)), indent=2))
        if text.strip() == "store list":
            return Result(self.name, json.dumps(store_list_packages(task.cwd), indent=2))
        s_resolve = re.match(r"^store resolve\s+([A-Za-z0-9._-]+)(?:\s+os=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if s_resolve:
            return Result(self.name, json.dumps(store_resolve_package(task.cwd, s_resolve.group(1), s_resolve.group(2) or ""), indent=2))
        s_resolve_dev = re.match(
            r"^store resolve device\s+([A-Za-z0-9._-]+)(?:\s+os=(\S+))?(?:\s+cpu=(\S+))?(?:\s+arch=(\S+))?(?:\s+security=(\S+))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if s_resolve_dev:
            return Result(
                self.name,
                json.dumps(
                    store_resolve_package(
                        task.cwd,
                        s_resolve_dev.group(1),
                        s_resolve_dev.group(2) or "",
                        s_resolve_dev.group(3) or "",
                        s_resolve_dev.group(4) or "",
                        s_resolve_dev.group(5) or "",
                    ),
                    indent=2,
                ),
            )
        if text.strip() == "store client detect":
            return Result(self.name, json.dumps({"ok": True, "device": store_detect_device()}, indent=2))
        s_scan = re.match(r"^store security scan\s+([A-Za-z0-9._-]+)$", raw.strip(), flags=re.IGNORECASE)
        if s_scan:
            return Result(self.name, json.dumps(store_security_scan(task.cwd, s_scan.group(1)), indent=2))
        u_install = re.match(r"^universal runtime install(?:\s+version=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if u_install:
            return Result(self.name, json.dumps(ure_runtime_install(task.cwd, u_install.group(1) or "0.1"), indent=2))
        if text.strip() == "universal runtime status":
            return Result(self.name, json.dumps(ure_runtime_status(task.cwd), indent=2))
        if text.strip() == "universal adapters status":
            return Result(self.name, json.dumps(ure_adapters_status(task.cwd), indent=2))
        u_adapter = re.match(r"^universal adapter set\s+(windows|linux|macos|android|ios)\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if u_adapter:
            return Result(self.name, json.dumps(ure_adapter_set(task.cwd, u_adapter.group(1), u_adapter.group(2)), indent=2))
        u_flow = re.match(r"^universal execution flow\s+([A-Za-z0-9._-]+)(?:\s+os=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if u_flow:
            return Result(self.name, json.dumps(ure_execution_flow(task.cwd, u_flow.group(1), u_flow.group(2) or ""), indent=2))
        if text.strip() == "universal security status":
            return Result(self.name, json.dumps(ure_security_status(task.cwd), indent=2))
        if text.strip() == "universal infrastructure status":
            return Result(self.name, json.dumps(ure_infra_status(task.cwd), indent=2))
        if text.strip() == "universal ecosystem coverage":
            return Result(self.name, json.dumps(ure_coverage_status(task.cwd), indent=2))
        acct = re.match(r"^store account create\s+email=(\S+)(?:\s+tier=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if acct:
            return Result(self.name, json.dumps(store_account_create(task.cwd, acct.group(1), acct.group(2) or "free"), indent=2))
        bill = re.match(r"^store billing charge\s+user=(\S+)\s+amount=(\d+(?:\.\d+)?)(?:\s+currency=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if bill:
            return Result(self.name, json.dumps(store_billing_charge(task.cwd, bill.group(1), float(bill.group(2)), bill.group(3) or "USD"), indent=2))
        lic = re.match(r"^store license grant\s+user=(\S+)\s+app=([A-Za-z0-9._-]+)$", raw.strip(), flags=re.IGNORECASE)
        if lic:
            return Result(self.name, json.dumps(store_license_grant(task.cwd, lic.group(1), lic.group(2)), indent=2))
        inst = re.match(r"^store install\s+user=(\S+)\s+app=([A-Za-z0-9._-]+)(?:\s+os=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if inst:
            return Result(self.name, json.dumps(store_install_app(task.cwd, inst.group(1), inst.group(2), inst.group(3) or ""), indent=2))
        uninst = re.match(r"^store uninstall\s+id=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if uninst:
            return Result(self.name, json.dumps(store_uninstall_app(task.cwd, uninst.group(1)), indent=2))
        upg = re.match(r"^store upgrade\s+id=(\S+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if upg:
            return Result(self.name, json.dumps(store_upgrade_app(task.cwd, upg.group(1), upg.group(2)), indent=2))
        enf = re.match(r"^store security enforce\s+app=([A-Za-z0-9._-]+)$", raw.strip(), flags=re.IGNORECASE)
        if enf:
            return Result(self.name, json.dumps(store_security_enforce(task.cwd, enf.group(1)), indent=2))
        repl = re.match(r"^store replicate\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if repl:
            return Result(self.name, json.dumps(store_storage_replicate(task.cwd, repl.group(1), repl.group(2)), indent=2))
        rb = re.match(r"^store rollback\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rb:
            return Result(self.name, json.dumps(store_storage_rollback(task.cwd, rb.group(1), rb.group(2)), indent=2))
        rev = re.match(r"^store review add\s+app=([A-Za-z0-9._-]+)\s+user=(\S+)\s+rating=(\d)(?:\s+text=(.+))?$", raw.strip(), flags=re.IGNORECASE)
        if rev:
            return Result(self.name, json.dumps(store_review_add(task.cwd, rev.group(1), rev.group(2), int(rev.group(3)), rev.group(4) or ""), indent=2))
        srch = re.match(r"^store search\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if srch:
            return Result(self.name, json.dumps(store_search_apps(task.cwd, srch.group(1)), indent=2))
        if text.strip() == "store analytics status":
            return Result(self.name, json.dumps(store_analytics_status(task.cwd), indent=2))
        pol = re.match(r"^store policy ios external\s+(on|off)$", text.strip(), flags=re.IGNORECASE)
        if pol:
            return Result(self.name, json.dumps(store_compliance_set(task.cwd, pol.group(1).lower() == "on"), indent=2))
        if text.strip() == "store compliance status":
            return Result(self.name, json.dumps(store_compliance_status(task.cwd), indent=2))
        if text.strip() == "store telemetry status":
            return Result(self.name, json.dumps(store_telemetry_status(task.cwd), indent=2))
        slo = re.match(r"^store slo set\s+availability=(\d+(?:\.\d+)?)\s+p95=(\d+)$", raw.strip(), flags=re.IGNORECASE)
        if slo:
            return Result(self.name, json.dumps(store_slo_set(task.cwd, float(slo.group(1)), int(slo.group(2))), indent=2))
        blk = re.match(r"^store abuse block ip\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if blk:
            return Result(self.name, json.dumps(store_abuse_block_ip(task.cwd, blk.group(1)), indent=2))
        nreg = re.match(r"^runtime network node register\s+os=(\S+)\s+device=(\S+)\s+mode=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nreg:
            return Result(self.name, json.dumps(grn_node_register(task.cwd, nreg.group(1), nreg.group(2), nreg.group(3)), indent=2))
        ndisc = re.match(r"^runtime network node discover(?:\s+os=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if ndisc:
            return Result(self.name, json.dumps(grn_node_discovery(task.cwd, ndisc.group(1) or ""), indent=2))
        cput = re.match(r"^runtime network cache put\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)\s+region=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if cput:
            return Result(self.name, json.dumps(grn_cache_put(task.cwd, cput.group(1), cput.group(2), cput.group(3)), indent=2))
        if text.strip() == "runtime network cache status":
            return Result(self.name, json.dumps(grn_cache_status(task.cwd), indent=2))
        rprop = re.match(r"^runtime network release propagate\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rprop:
            return Result(self.name, json.dumps(grn_runtime_release_propagate(task.cwd, rprop.group(1)), indent=2))
        sval = re.match(r"^runtime network security validate\s+signed=(true|false)$", text.strip(), flags=re.IGNORECASE)
        if sval:
            return Result(self.name, json.dumps(grn_security_validate(task.cwd, sval.group(1).lower() == "true"), indent=2))
        adap = re.match(r"^runtime network adaptive mode\s+device=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if adap:
            return Result(self.name, json.dumps(grn_adaptive_mode(task.cwd, adap.group(1)), indent=2))
        if text.strip() == "runtime network status":
            return Result(self.name, json.dumps(grn_network_status(task.cwd), indent=2))
        if text.strip() == "runtime network telemetry":
            return Result(self.name, json.dumps(grn_telemetry_status(task.cwd), indent=2))
        if text.strip() == "runtime protocol status":
            return Result(self.name, json.dumps(rp_protocol_status(task.cwd), indent=2))
        rp_ad = re.match(r"^runtime protocol adapter\s+(windows|linux|macos|android|ios)$", raw.strip(), flags=re.IGNORECASE)
        if rp_ad:
            return Result(self.name, json.dumps(rp_adapter_contract(task.cwd, rp_ad.group(1)), indent=2))
        rp_hs = re.match(
            r"^runtime protocol handshake\s+os=(\S+)\s+cpu=(\S+)\s+arch=(\S+)\s+security=(\S+)$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if rp_hs:
            return Result(
                self.name,
                json.dumps(rp_capability_handshake(task.cwd, rp_hs.group(1), rp_hs.group(2), rp_hs.group(3), rp_hs.group(4)), indent=2),
            )
        rp_at = re.match(r"^runtime protocol attest\s+path=(\S+)\s+signer=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rp_at:
            return Result(self.name, json.dumps(rp_package_attest(task.cwd, rp_at.group(1), rp_at.group(2)), indent=2))
        rp_ver = re.match(r"^runtime protocol verify\s+path=(\S+)\s+signer=(\S+)\s+signature=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rp_ver:
            return Result(self.name, json.dumps(rp_package_verify(task.cwd, rp_ver.group(1), rp_ver.group(2), rp_ver.group(3)), indent=2))
        rp_cp = re.match(r"^runtime protocol compatibility\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rp_cp:
            return Result(self.name, json.dumps(rp_compatibility_check(task.cwd, rp_cp.group(1)), indent=2))
        rp_dep = re.match(r"^runtime protocol deprecate\s+api=(\S+)\s+remove_after=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rp_dep:
            return Result(self.name, json.dumps(rp_deprecation_add(task.cwd, rp_dep.group(1), rp_dep.group(2)), indent=2))
        if text.strip() == "runtime protocol security status":
            return Result(self.name, json.dumps(rp_security_status(task.cwd), indent=2))
        if text.strip() == "runtime protocol security grade":
            return Result(self.name, json.dumps(rp_security_grade(task.cwd), indent=2))
        if text.strip() in {"runtime protocol security maximize", "maximize runtime protocol security"}:
            return Result(self.name, json.dumps(rp_maximize_security(task.cwd), indent=2))
        rp_sec = re.match(r"^runtime protocol security set\s+strict=(on|off)\s+min=(low|baseline|strict|high)$", text.strip(), flags=re.IGNORECASE)
        if rp_sec:
            return Result(
                self.name,
                json.dumps(rp_security_set(task.cwd, rp_sec.group(1).lower() == "on", rp_sec.group(2).lower()), indent=2),
            )
        rp_sa = re.match(r"^runtime protocol signer allow\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rp_sa:
            return Result(self.name, json.dumps(rp_signer_allow(task.cwd, rp_sa.group(1)), indent=2))
        rp_sr = re.match(r"^runtime protocol signer revoke\s+(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rp_sr:
            return Result(self.name, json.dumps(rp_signer_revoke(task.cwd, rp_sr.group(1)), indent=2))
        if text.strip() == "runtime protocol key rotate":
            return Result(self.name, json.dumps(rp_key_rotate(task.cwd), indent=2))
        rp_n = re.match(r"^runtime protocol nonce issue\s+node=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rp_n:
            return Result(self.name, json.dumps(rp_nonce_issue(task.cwd, rp_n.group(1)), indent=2))
        rp_hs2 = re.match(
            r"^runtime protocol secure handshake\s+os=(\S+)\s+cpu=(\S+)\s+arch=(\S+)\s+security=(\S+)\s+nonce=(\S+)\s+proof=(\S+)$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if rp_hs2:
            return Result(
                self.name,
                json.dumps(
                    rp_capability_handshake_secure(
                        task.cwd,
                        rp_hs2.group(1),
                        rp_hs2.group(2),
                        rp_hs2.group(3),
                        rp_hs2.group(4),
                        rp_hs2.group(5),
                        rp_hs2.group(6),
                    ),
                    indent=2,
                ),
            )
        rp_pf = re.match(
            r"^runtime protocol proof preview\s+os=(\S+)\s+cpu=(\S+)\s+arch=(\S+)\s+security=(\S+)\s+nonce=(\S+)$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if rp_pf:
            return Result(
                self.name,
                json.dumps(
                    rp_handshake_proof_preview(task.cwd, rp_pf.group(1), rp_pf.group(2), rp_pf.group(3), rp_pf.group(4), rp_pf.group(5)),
                    indent=2,
                ),
            )
        rp_al = re.match(r"^runtime protocol adapter allowlist\s+(windows|linux|macos|android|ios)\s+hash=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rp_al:
            return Result(self.name, json.dumps(rp_adapter_allowlist_set(task.cwd, rp_al.group(1), rp_al.group(2)), indent=2))
        if text.strip() == "runtime protocol audit status":
            return Result(self.name, json.dumps(rp_audit_status(task.cwd), indent=2))
        if text.strip() == "runtime protocol ecosystem status":
            return Result(self.name, json.dumps(rpe_status(task.cwd), indent=2))
        if text.strip() == "runtime protocol ecosystem grade":
            return Result(self.name, json.dumps(rpe_grade(task.cwd), indent=2))
        if text.strip() in {"runtime protocol ecosystem maximize", "maximize runtime protocol layer ecosystem"}:
            return Result(self.name, json.dumps(rpe_maximize(task.cwd), indent=2))
        if text.strip() in {"rcrp status", "recursive capability runtime protocol status"}:
            return Result(self.name, json.dumps(rcrp_status(task.cwd), indent=2))
        rcrp_dev = re.match(
            r"^rcrp device set(?:\s+cpu=(\S+))?(?:\s+gpu=(\S+))?(?:\s+ram=(\d+))?(?:\s+network=(\S+))?(?:\s+energy=(\S+))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if rcrp_dev:
            ram = int(rcrp_dev.group(3)) if rcrp_dev.group(3) else None
            return Result(
                self.name,
                json.dumps(
                    rcrp_device_profile_set(
                        task.cwd,
                        rcrp_dev.group(1) or "",
                        rcrp_dev.group(2) or "",
                        ram,
                        rcrp_dev.group(4) or "",
                        rcrp_dev.group(5) or "",
                    ),
                    indent=2,
                ),
            )
        rcrp_graph = re.match(r"^rcrp graph register\s+app=([A-Za-z0-9._-]+)\s+json=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if rcrp_graph:
            return Result(self.name, json.dumps(rcrp_graph_register(task.cwd, rcrp_graph.group(1), rcrp_graph.group(2)), indent=2))
        rcrp_token = re.match(r"^rcrp token set\s+(\S+)\s+(on|off)$", raw.strip(), flags=re.IGNORECASE)
        if rcrp_token:
            return Result(self.name, json.dumps(rcrp_token_set(task.cwd, rcrp_token.group(1), rcrp_token.group(2).lower() == "on"), indent=2))
        rcrp_plan = re.match(r"^rcrp plan build\s+app=([A-Za-z0-9._-]+)$", raw.strip(), flags=re.IGNORECASE)
        if rcrp_plan:
            return Result(self.name, json.dumps(rcrp_plan_build(task.cwd, rcrp_plan.group(1)), indent=2))
        rcrp_node = re.match(r"^rcrp mesh node register\s+name=(\S+)\s+power=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rcrp_node:
            return Result(self.name, json.dumps(rcrp_mesh_node_register(task.cwd, rcrp_node.group(1), rcrp_node.group(2)), indent=2))
        rcrp_m = re.match(r"^rcrp migrate\s+app=([A-Za-z0-9._-]+)\s+plan=(\S+)\s+target=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rcrp_m:
            return Result(self.name, json.dumps(rcrp_migrate(task.cwd, rcrp_m.group(1), rcrp_m.group(2), rcrp_m.group(3)), indent=2))
        rcrp_l = re.match(r"^rcrp learning observe\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if rcrp_l:
            return Result(self.name, json.dumps(rcrp_learning_observe(task.cwd, rcrp_l.group(1)), indent=2))
        if text.strip() in {"serp status", "self-evolving runtime protocol status"}:
            return Result(self.name, json.dumps(serp_status(task.cwd), indent=2))
        serp_t = re.match(
            r"^serp telemetry submit\s+node=(\S+)\s+region=(\S+)\s+cpu=(\d+(?:\.\d+)?)\s+memory=(\d+(?:\.\d+)?)\s+gpu=(\d+(?:\.\d+)?)\s+latency=(\d+(?:\.\d+)?)\s+energy=(\d+(?:\.\d+)?)$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if serp_t:
            return Result(
                self.name,
                json.dumps(
                    serp_telemetry_submit(
                        task.cwd,
                        serp_t.group(1),
                        serp_t.group(2),
                        float(serp_t.group(3)),
                        float(serp_t.group(4)),
                        float(serp_t.group(5)),
                        float(serp_t.group(6)),
                        float(serp_t.group(7)),
                    ),
                    indent=2,
                ),
            )
        if text.strip() == "serp analyze":
            return Result(self.name, json.dumps(serp_analyze(task.cwd), indent=2))
        serp_m = re.match(r"^serp mutation propose\s+component=(\S+)\s+strategy=(\S+)\s+signer=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if serp_m:
            return Result(self.name, json.dumps(serp_mutation_propose(task.cwd, serp_m.group(1), serp_m.group(2), serp_m.group(3)), indent=2))
        serp_d = re.match(r"^serp deploy staged\s+mutation=(\S+)\s+percent=(\d+)$", raw.strip(), flags=re.IGNORECASE)
        if serp_d:
            return Result(self.name, json.dumps(serp_deploy_staged(task.cwd, serp_d.group(1), int(serp_d.group(2))), indent=2))
        if text.strip() == "serp rollback":
            return Result(self.name, json.dumps(serp_rollback(task.cwd), indent=2))
        serp_se = re.match(r"^serp state export\s+app=([A-Za-z0-9._-]+)\s+json=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if serp_se:
            return Result(self.name, json.dumps(serp_state_export(task.cwd, serp_se.group(1), serp_se.group(2)), indent=2))
        serp_si = re.match(r"^serp state import\s+id=(\S+)\s+target=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if serp_si:
            return Result(self.name, json.dumps(serp_state_import(task.cwd, serp_si.group(1), serp_si.group(2)), indent=2))
        if text.strip() in {"autonomous runtime ecosystem status", "global autonomous runtime ecosystem status"}:
            return Result(self.name, json.dumps(are_status(task.cwd), indent=2))
        are_node = re.match(r"^autonomous runtime ecosystem node register\s+role=(\S+)\s+name=(\S+)(?:\s+os=(\S+))?(?:\s+power=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if are_node:
            return Result(
                self.name,
                json.dumps(
                    are_node_register(
                        task.cwd,
                        are_node.group(1),
                        are_node.group(2),
                        are_node.group(3) or "linux",
                        are_node.group(4) or "normal",
                    ),
                    indent=2,
                ),
            )
        if text.strip() == "autonomous runtime ecosystem optimize":
            return Result(self.name, json.dumps(are_ai_optimize(task.cwd), indent=2))
        are_prop = re.match(r"^autonomous runtime ecosystem governance propose\s+component=(\S+)\s+strategy=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if are_prop:
            return Result(self.name, json.dumps(are_gov_propose(task.cwd, are_prop.group(1), are_prop.group(2)), indent=2))
        if text.strip() == "autonomous runtime ecosystem governance simulate":
            return Result(self.name, json.dumps(are_gov_simulate(task.cwd), indent=2))
        are_roll = re.match(r"^autonomous runtime ecosystem governance rollout\s+percent=(\d+)$", raw.strip(), flags=re.IGNORECASE)
        if are_roll:
            return Result(self.name, json.dumps(are_gov_rollout(task.cwd, int(are_roll.group(1))), indent=2))
        if text.strip() == "autonomous runtime ecosystem governance validate":
            return Result(self.name, json.dumps(are_gov_validate(task.cwd), indent=2))
        if text.strip() == "autonomous runtime ecosystem grade":
            return Result(self.name, json.dumps(are_grade(task.cwd), indent=2))
        if text.strip() in {"autonomous runtime ecosystem maximize", "maximize autonomous runtime protocol ecosystem"}:
            return Result(self.name, json.dumps(are_maximize(task.cwd), indent=2))
        if text.strip() == "hardware runtime status":
            return Result(self.name, json.dumps(hrf_status(task.cwd), indent=2))
        hrf_hw = re.match(
            r"^hardware runtime set(?:\s+accelerator=(on|off))?(?:\s+security=(on|off))?(?:\s+memory=(on|off))?(?:\s+network=(on|off))?$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if hrf_hw:
            return Result(
                self.name,
                json.dumps(
                    hrf_hardware_set(
                        task.cwd,
                        None if not hrf_hw.group(1) else (hrf_hw.group(1).lower() == "on"),
                        None if not hrf_hw.group(2) else (hrf_hw.group(2).lower() == "on"),
                        None if not hrf_hw.group(3) else (hrf_hw.group(3).lower() == "on"),
                        None if not hrf_hw.group(4) else (hrf_hw.group(4).lower() == "on"),
                    ),
                    indent=2,
                ),
            )
        if text.strip() == "hardware runtime maximize":
            return Result(self.name, json.dumps(hrf_hardware_maximize(task.cwd), indent=2))
        hrf_evo = re.match(r"^runtime evolve app\s+([A-Za-z0-9._-]+)$", raw.strip(), flags=re.IGNORECASE)
        if hrf_evo:
            return Result(self.name, json.dumps(hrf_evolve_application(task.cwd, hrf_evo.group(1)), indent=2))
        hrf_ml = re.match(r"^runtime memory learn\s+app=([A-Za-z0-9._-]+)\s+key=(\S+)\s+value=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if hrf_ml:
            return Result(self.name, json.dumps(hrf_memory_learn(task.cwd, hrf_ml.group(1), hrf_ml.group(2), hrf_ml.group(3)), indent=2))
        hrf_mg = re.match(r"^runtime memory get\s+app=([A-Za-z0-9._-]+)$", raw.strip(), flags=re.IGNORECASE)
        if hrf_mg:
            return Result(self.name, json.dumps(hrf_memory_get(task.cwd, hrf_mg.group(1)), indent=2))
        hrf_fn = re.match(r"^runtime fabric node register\s+name=(\S+)\s+power=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if hrf_fn:
            return Result(self.name, json.dumps(hrf_fabric_node_register(task.cwd, hrf_fn.group(1), hrf_fn.group(2)), indent=2))
        hrf_fd = re.match(r"^runtime fabric dispatch\s+app=([A-Za-z0-9._-]+)\s+task=(\S+)(?:\s+nodes=(\d+))?$", raw.strip(), flags=re.IGNORECASE)
        if hrf_fd:
            nodes = int(hrf_fd.group(3)) if hrf_fd.group(3) else 1
            return Result(self.name, json.dumps(hrf_fabric_dispatch(task.cwd, hrf_fd.group(1), hrf_fd.group(2), nodes), indent=2))
        if text.strip() == "runtime fabric status":
            return Result(self.name, json.dumps(hrf_fabric_status(task.cwd), indent=2))
        if text.strip() == "ria status":
            return Result(self.name, json.dumps(ria_status(task.cwd), indent=2))
        ria_reg = re.match(r"^ria program register\s+app=([A-Za-z0-9._-]+)\s+json=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if ria_reg:
            return Result(self.name, json.dumps(ria_program_register(task.cwd, ria_reg.group(1), ria_reg.group(2)), indent=2))
        ria_val = re.match(r"^ria program validate\s+id=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if ria_val:
            return Result(self.name, json.dumps(ria_program_validate(task.cwd, ria_val.group(1)), indent=2))
        ria_ex = re.match(r"^ria execute\s+id=(\S+)(?:\s+caps=(.+))?$", raw.strip(), flags=re.IGNORECASE)
        if ria_ex:
            return Result(self.name, json.dumps(ria_execute(task.cwd, ria_ex.group(1), ria_ex.group(2) or "{}"), indent=2))
        if text.strip() == "runtime economy status":
            return Result(self.name, json.dumps(re_status(task.cwd), indent=2))
        rea = re.match(r"^runtime economy actor register\s+role=(\S+)\s+name=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if rea:
            return Result(self.name, json.dumps(re_actor_register(task.cwd, rea.group(1), rea.group(2)), indent=2))
        rec = re.match(r"^runtime economy contribution\s+actor=(\S+)\s+kind=(\S+)\s+units=(\d+(?:\.\d+)?)$", raw.strip(), flags=re.IGNORECASE)
        if rec:
            return Result(self.name, json.dumps(re_contribution_record(task.cwd, rec.group(1), rec.group(2), float(rec.group(3))), indent=2))
        rep = re.match(r"^runtime economy payout\s+actor=(\S+)\s+amount=(\d+(?:\.\d+)?)$", raw.strip(), flags=re.IGNORECASE)
        if rep:
            return Result(self.name, json.dumps(re_payout(task.cwd, rep.group(1), float(rep.group(2))), indent=2))
        if text.strip() in {"platform blueprint status", "idea to platform status"}:
            return Result(self.name, json.dumps(pb_status(task.cwd), indent=2))
        if text.strip() in {"platform blueprint scaffold", "idea to platform scaffold"}:
            return Result(self.name, json.dumps(pb_scaffold(task.cwd), indent=2))
        if text.strip() == "native store status":
            return Result(self.name, json.dumps(nas_status(task.cwd), indent=2))
        if text.strip() == "native store enterprise status":
            return Result(self.name, json.dumps(nseo_status(task.cwd), indent=2))
        nseos = re.match(r"^native store enterprise signing set\s+type=(\S+)\s+name=(\S+)\s+key=(\S+)\s+hsm=(on|off)$", raw.strip(), flags=re.IGNORECASE)
        if nseos:
            return Result(self.name, json.dumps(nseo_signing_provider_set(task.cwd, nseos.group(1), nseos.group(2), nseos.group(3), nseos.group(4).lower() == "on"), indent=2))
        nseov = re.match(r"^native store enterprise vendor configure\s+channel=(\S+)\s+identity=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nseov:
            return Result(self.name, json.dumps(nseo_vendor_channel_configure(task.cwd, nseov.group(1), nseov.group(2)), indent=2))
        nseob = re.match(
            r"^native store enterprise backend set\s+replicas=(\d+)\s+tls=(on|off)\s+monitoring=(on|off)\s+alerting=(on|off)\s+storage=(on|off)\s+dr=(\S+)$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if nseob:
            return Result(
                self.name,
                json.dumps(
                    nseo_backend_prod_set(
                        task.cwd,
                        int(nseob.group(1)),
                        nseob.group(2).lower() == "on",
                        nseob.group(3).lower() == "on",
                        nseob.group(4).lower() == "on",
                        nseob.group(5).lower() == "on",
                        nseob.group(6),
                    ),
                    indent=2,
                ),
            )
        nseod = re.match(
            r"^native store enterprise desktop set\s+binary=(on|off)\s+updater=(on|off)\s+service=(on|off)\s+registration=(on|off)\s+crash=(on|off)$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if nseod:
            return Result(
                self.name,
                json.dumps(
                    nseo_desktop_prod_set(
                        task.cwd,
                        nseod.group(1).lower() == "on",
                        nseod.group(2).lower() == "on",
                        nseod.group(3).lower() == "on",
                        nseod.group(4).lower() == "on",
                        nseod.group(5).lower() == "on",
                    ),
                    indent=2,
                ),
            )
        nseosp = re.match(r"^native store enterprise secrets set\s+provider=(\S+)\s+ca=(\S+)\s+revocation=(on|off)$", raw.strip(), flags=re.IGNORECASE)
        if nseosp:
            return Result(self.name, json.dumps(nseo_secrets_platform_set(task.cwd, nseosp.group(1), nseosp.group(2), nseosp.group(3).lower() == "on"), indent=2))
        nseog = re.match(r"^native store enterprise governance set\s+oncall=(\S+)\s+approvers=(\S+)\s+freeze=(on|off)$", raw.strip(), flags=re.IGNORECASE)
        if nseog:
            oncall = [x for x in nseog.group(1).split(",") if x]
            approvers = [x for x in nseog.group(2).split(",") if x]
            return Result(self.name, json.dumps(nseo_ops_governance_set(task.cwd, oncall, approvers, nseog.group(3).lower() == "on"), indent=2))
        nseot = re.match(r"^native store enterprise deployed test\s+target=(\S+)\s+passed=(on|off)$", raw.strip(), flags=re.IGNORECASE)
        if nseot:
            return Result(self.name, json.dumps(nseo_deployed_test_record(task.cwd, nseot.group(1), nseot.group(2).lower() == "on"), indent=2))
        nsv = re.match(r"^native store scaffold vendor\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsv:
            return Result(self.name, json.dumps(nas_scaffold_vendor_artifacts(task.cwd, nsv.group(1), nsv.group(2)), indent=2))
        if text.strip() == "native store scaffold services":
            return Result(self.name, json.dumps(nas_scaffold_installer_services(task.cwd), indent=2))
        if text.strip() == "native store scaffold backend":
            return Result(self.name, json.dumps(nas_scaffold_backend(task.cwd), indent=2))
        if text.strip() == "native store scaffold gui":
            return Result(self.name, json.dumps(nas_scaffold_gui_client(task.cwd), indent=2))
        if text.strip() == "native store backend init":
            return Result(self.name, json.dumps(nsb_init_db(task.cwd), indent=2))
        if text.strip() == "native store backend status":
            return Result(self.name, json.dumps(nsb_status(task.cwd), indent=2))
        if text.strip() == "native store backend deploy scaffold":
            return Result(self.name, json.dumps(nsb_scaffold_deploy(task.cwd), indent=2))
        nsbb = re.match(r"^native store backend backup(?:\s+name=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if nsbb:
            return Result(self.name, json.dumps(nsb_backup_db(task.cwd, nsbb.group(1) or ""), indent=2))
        nsbr = re.match(r"^native store backend restore\s+path=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if nsbr:
            return Result(self.name, json.dumps(nsb_restore_db(task.cwd, nsbr.group(1)), indent=2))
        nsbu = re.match(r"^native store backend user create\s+id=(\S+)\s+email=(\S+)\s+tier=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsbu:
            return Result(self.name, json.dumps(nsb_create_user(task.cwd, nsbu.group(1), nsbu.group(2), nsbu.group(3)), indent=2))
        nsbt = re.match(r"^native store backend token issue\s+id=(\S+)\s+scope=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsbt:
            return Result(self.name, json.dumps(nsb_issue_token(task.cwd, nsbt.group(1), nsbt.group(2)), indent=2))
        nsbc = re.match(r"^native store backend charge\s+id=(\S+)\s+user=(\S+)\s+amount=(\d+(?:\.\d+)?)\s+currency=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsbc:
            return Result(self.name, json.dumps(nsb_charge_user(task.cwd, nsbc.group(1), nsbc.group(2), float(nsbc.group(3)), nsbc.group(4)), indent=2))
        nsbe = re.match(r"^native store backend event\s+kind=(\S+)\s+json=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if nsbe:
            try:
                payload = json.loads(nsbe.group(2))
            except Exception as exc:
                return Result(self.name, json.dumps({"ok": False, "reason": f"invalid json: {exc}"}, indent=2))
            return Result(self.name, json.dumps(nsb_record_event(task.cwd, nsbe.group(1), payload), indent=2))
        if text.strip() == "native store desktop scaffold":
            return Result(self.name, json.dumps(nsd_scaffold(task.cwd), indent=2))
        if text.strip() == "native store desktop launch":
            return Result(self.name, json.dumps(nsd_launch(task.cwd), indent=2))
        nsw = re.match(r"^native store build windows\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsw:
            return Result(self.name, json.dumps(nas_build_windows_native(task.cwd, nsw.group(1), nsw.group(2)), indent=2))
        nsl = re.match(r"^native store build linux\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsl:
            return Result(self.name, json.dumps(nas_build_linux_native(task.cwd, nsl.group(1), nsl.group(2)), indent=2))
        nsm = re.match(r"^native store build macos\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)(?:\s+signer=(.+))?$", raw.strip(), flags=re.IGNORECASE)
        if nsm:
            return Result(self.name, json.dumps(nas_build_macos_native(task.cwd, nsm.group(1), nsm.group(2), nsm.group(3) or "Developer ID Application: Zero OS"), indent=2))
        nsmob = re.match(r"^native store build mobile\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsmob:
            return Result(self.name, json.dumps(nas_build_mobile_distribution(task.cwd, nsmob.group(1), nsmob.group(2)), indent=2))
        nsp = re.match(r"^native store pipeline run\s+app=([A-Za-z0-9._-]+)\s+os=(\S+)(?:\s+format=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if nsp:
            return Result(self.name, json.dumps(nas_pipeline_run(task.cwd, nsp.group(1), nsp.group(2), nsp.group(3) or ""), indent=2))
        nsi = re.match(r"^native store install\s+app=([A-Za-z0-9._-]+)(?:\s+os=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if nsi:
            return Result(self.name, json.dumps(nas_install(task.cwd, nsi.group(1), nsi.group(2) or ""), indent=2))
        nsu = re.match(r"^native store uninstall\s+id=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsu:
            return Result(self.name, json.dumps(nas_uninstall(task.cwd, nsu.group(1)), indent=2))
        nsg = re.match(r"^native store upgrade\s+id=(\S+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsg:
            return Result(self.name, json.dumps(nas_upgrade(task.cwd, nsg.group(1), nsg.group(2)), indent=2))
        nss = re.match(r"^native store service set\s+os=(\S+)\s+enabled=(on|off)$", raw.strip(), flags=re.IGNORECASE)
        if nss:
            return Result(self.name, json.dumps(nas_installer_service_set(task.cwd, nss.group(1), nss.group(2).lower() == "on"), indent=2))
        nst = re.match(r"^native store trust channel set\s+name=(\S+)\s+signed=(on|off)\s+notarization=(on|off)$", raw.strip(), flags=re.IGNORECASE)
        if nst:
            return Result(
                self.name,
                json.dumps(nas_trust_channel_set(task.cwd, nst.group(1), nst.group(2).lower() == "on", nst.group(3).lower() == "on"), indent=2),
            )
        nsn = re.match(r"^native store notarize\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)\s+signer=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsn:
            return Result(self.name, json.dumps(nas_notarize_release(task.cwd, nsn.group(1), nsn.group(2), nsn.group(3)), indent=2))
        nsb = re.match(r"^native store backend integrate\s+component=(\S+)\s+provider=(\S+)\s+enabled=(on|off)$", raw.strip(), flags=re.IGNORECASE)
        if nsb:
            return Result(
                self.name,
                json.dumps(nas_backend_integrate(task.cwd, nsb.group(1), nsb.group(2), nsb.group(3).lower() == "on"), indent=2),
            )
        nsgu = re.match(r"^native store gui set(?:\s+first_run=(on|off))?(?:\s+deep=(on|off))?$", raw.strip(), flags=re.IGNORECASE)
        if nsgu:
            first_run = None if not nsgu.group(1) else (nsgu.group(1).lower() == "on")
            deep = None if not nsgu.group(2) else (nsgu.group(2).lower() == "on")
            return Result(self.name, json.dumps(nas_gui_set(task.cwd, first_run, deep), indent=2))
        nsdp = re.match(r"^native store desktop package\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsdp:
            return Result(self.name, json.dumps(nas_scaffold_desktop_production(task.cwd, nsdp.group(1), nsdp.group(2)), indent=2))
        nsss = re.match(r"^native store secret set\s+name=(\S+)\s+value=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if nsss:
            return Result(self.name, json.dumps(nas_secret_set(task.cwd, nsss.group(1), nsss.group(2)), indent=2))
        nscr = re.match(r"^native store cert rotate\s+name=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if nscr:
            return Result(self.name, json.dumps(nas_cert_rotate(task.cwd, nscr.group(1)), indent=2))
        nsrc = re.match(r"^native store rollback checkpoint\s+name=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsrc:
            return Result(self.name, json.dumps(nas_rollback_checkpoint(task.cwd, nsrc.group(1)), indent=2))
        nsrr = re.match(r"^native store rollback restore\s+name=(\S+)$", raw.strip(), flags=re.IGNORECASE)
        if nsrr:
            return Result(self.name, json.dumps(nas_rollback_restore(task.cwd, nsrr.group(1)), indent=2))
        nsio = re.match(r"^native store incident open\s+severity=(\S+)\s+summary=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if nsio:
            return Result(self.name, json.dumps(nas_incident_open(task.cwd, nsio.group(1), nsio.group(2)), indent=2))
        nsst = re.match(r"^native store stress test\s+traffic=(\d+)\s+abuse=(\d+)\s+failures=(\d+)$", raw.strip(), flags=re.IGNORECASE)
        if nsst:
            return Result(self.name, json.dumps(nas_stress_test(task.cwd, int(nsst.group(1)), int(nsst.group(2)), int(nsst.group(3))), indent=2))
        nsrp = re.match(r"^native store release prepare\s+version=(\S+)(?:\s+channel=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if nsrp:
            return Result(self.name, json.dumps(nas_release_prepare(task.cwd, nsrp.group(1), nsrp.group(2) or "stable"), indent=2))
        nssa = re.match(r"^native store artifact sign\s+path=(.+?)\s+signer=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if nssa:
            return Result(self.name, json.dumps(nas_sign_artifact(task.cwd, nssa.group(1), nssa.group(2)), indent=2))
        nsvf = re.match(r"^native store artifact verify\s+path=(.+)$", raw.strip(), flags=re.IGNORECASE)
        if nsvf:
            return Result(self.name, json.dumps(nas_verify_artifact(task.cwd, nsvf.group(1)), indent=2))
        nse2e = re.match(r"^native store e2e run\s+app=([A-Za-z0-9._-]+)\s+version=(\S+)\s+traffic=(\d+)\s+abuse=(\d+)\s+failures=(\d+)$", raw.strip(), flags=re.IGNORECASE)
        if nse2e:
            return Result(
                self.name,
                json.dumps(
                    nas_e2e_runner(task.cwd, nse2e.group(1), nse2e.group(2), int(nse2e.group(3)), int(nse2e.group(4)), int(nse2e.group(5))),
                    indent=2,
                ),
            )
        if text.strip() == "native store maximize":
            return Result(self.name, json.dumps(nas_maximize(task.cwd), indent=2))

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
        if text.strip() in {"zero ai security apply", "zero ai security harden apply"}:
            return Result(self.name, json.dumps(zero_ai_security_apply(task.cwd), indent=2))
        if text.strip() in {"zero ai security status", "zero ai security harden status"}:
            return Result(self.name, json.dumps(zero_ai_security_status(task.cwd), indent=2))
        if text.strip() in {"zero ai brain awareness build", "zero ai brain build", "make zero ai have everything brain awareness"}:
            return Result(self.name, json.dumps(build_brain_awareness(task.cwd), indent=2))
        if text.strip() in {"zero ai brain awareness status", "zero ai brain status"}:
            return Result(self.name, json.dumps(brain_awareness_status(task.cwd), indent=2))
        if text.strip() in {"zero ai identity", "zero ai rsi status"}:
            return Result(self.name, json.dumps(zero_ai_identity(), indent=2))
        if text.strip() in {"zero ai consciousness status", "zero ai consciousness"}:
            return Result(self.name, json.dumps(consciousness_status(task.cwd), indent=2))
        if text.strip() in {
            "strong persistent long-term memory",
            "zero ai architecture long-term memory",
            "conscious machine architecture long-term memory",
        }:
            return Result(self.name, json.dumps(consciousness_architecture_long_term_memory_status(), indent=2))
        if text.strip() in {"silicon awareness machine", "conscious machine architecture silicon awareness", "zero ai architecture silicon awareness"}:
            return Result(self.name, json.dumps(consciousness_architecture_silicon_awareness_status(), indent=2))
        if text.strip() in {
            "hybrid crystal cognition architecture",
            "hybrid crystal intelligence system",
            "conscious machine architecture hybrid crystal",
            "zero ai architecture hybrid crystal",
        }:
            return Result(self.name, json.dumps(consciousness_architecture_hybrid_crystal_status(), indent=2))
        if text.strip() in {"crystal lattice cognition", "conscious machine architecture clc", "zero ai architecture clc"}:
            return Result(self.name, json.dumps(consciousness_architecture_clc_status(), indent=2))
        if text.strip() in {"temporal identity field", "conscious machine architecture tif", "zero ai architecture tif"}:
            return Result(self.name, json.dumps(consciousness_architecture_tif_status(), indent=2))
        if text.strip() in {"self-generating ontology engine", "conscious machine architecture sgoe", "zero ai architecture sgoe"}:
            return Result(self.name, json.dumps(consciousness_architecture_sgoe_status(), indent=2))
        if text.strip() in {"reflexive causality engine", "conscious machine architecture rce", "zero ai architecture rce"}:
            return Result(self.name, json.dumps(consciousness_architecture_rce_status(), indent=2))
        if text.strip() in {"conscious machine architecture phase 9", "zero ai architecture phase 9"}:
            return Result(self.name, json.dumps(consciousness_architecture_phase9_status(), indent=2))
        if text.strip() in {"conscious machine architecture phase 8", "zero ai architecture phase 8"}:
            return Result(self.name, json.dumps(consciousness_architecture_phase8_status(), indent=2))
        if text.strip() in {"conscious machine architecture phase 7", "zero ai architecture phase 7"}:
            return Result(self.name, json.dumps(consciousness_architecture_phase7_status(), indent=2))
        if text.strip() in {"conscious machine architecture phase 6", "zero ai architecture phase 6"}:
            return Result(self.name, json.dumps(consciousness_architecture_phase6_status(), indent=2))
        if text.strip() in {"conscious machine architecture phase 5", "zero ai architecture phase 5"}:
            return Result(self.name, json.dumps(consciousness_architecture_phase5_status(), indent=2))
        if text.strip() in {"conscious machine architecture phase 4", "zero ai architecture phase 4"}:
            return Result(self.name, json.dumps(consciousness_architecture_phase4_status(), indent=2))
        if text.strip() in {"conscious machine architecture phase 3", "zero ai architecture phase 3"}:
            return Result(self.name, json.dumps(consciousness_architecture_phase3_status(), indent=2))
        if text.strip() in {"conscious machine architecture phase 2", "zero ai architecture phase 2"}:
            return Result(self.name, json.dumps(consciousness_architecture_phase2_status(), indent=2))
        if text.strip() in {"zero ai conscious architecture", "conscious machine architecture", "zero ai architecture"}:
            return Result(self.name, json.dumps(consciousness_architecture_status(), indent=2))
        ctick = re.match(r"^zero ai consciousness tick(?:\s+(.+))?$", raw.strip(), flags=re.IGNORECASE)
        if ctick:
            prompt = (ctick.group(1) or "").strip()
            return Result(self.name, json.dumps(consciousness_tick(task.cwd, prompt=prompt), indent=2))
        if text.strip() in {"zero ai fix all", "go fix all", "fix all now"}:
            return Result(self.name, json.dumps(zero_ai_sync_all(task.cwd), indent=2))
        if text.strip() in {"zero ai gap status", "zero ai cover gap status"}:
            return Result(self.name, json.dumps(zero_ai_gap_status(task.cwd), indent=2))
        if text.strip() in {"zero ai gap fix", "zero ai cover gap fix", "maximize zero ai cover gap or missing"}:
            return Result(self.name, json.dumps(zero_ai_gap_fix(task.cwd), indent=2))
        if text.strip() in {"zero ai runtime status", "phase runtime status"}:
            return Result(self.name, json.dumps(zero_ai_runtime_status(task.cwd), indent=2))
        if text.strip() in {"zero ai runtime run", "phase runtime run", "zero ai runtime all"}:
            return Result(self.name, json.dumps(zero_ai_runtime_run(task.cwd), indent=2))
        rt_ing = re.match(r"^runtime telemetry ingest(?:\s+source=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if rt_ing:
            return Result(self.name, json.dumps(telemetry_ingest(task.cwd, rt_ing.group(1) or "runtime"), indent=2))
        rt_pub = re.match(r"^runtime node publish\s+([A-Za-z0-9._-]+)\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if rt_pub:
            try:
                payload = json.loads(rt_pub.group(2))
            except Exception:
                return Result(self.name, json.dumps({"ok": False, "reason": "payload must be valid json"}, indent=2))
            return Result(self.name, json.dumps(node_bus_publish(task.cwd, rt_pub.group(1), payload), indent=2))
        if text.strip() == "runtime node consensus":
            return Result(self.name, json.dumps(node_bus_consensus(task.cwd), indent=2))
        if text.strip() == "runtime adversarial validate":
            return Result(self.name, json.dumps(adversarial_runtime_validate(task.cwd), indent=2))
        if text.strip() == "runtime dashboard export":
            return Result(self.name, json.dumps(benchmark_dashboard_export(task.cwd), indent=2))
        rt_slo = re.match(r"^runtime slo check(?:\s+min=(\d+(?:\.\d+)?))?$", text.strip(), flags=re.IGNORECASE)
        if rt_slo:
            return Result(self.name, json.dumps(slo_monitor(task.cwd, float(rt_slo.group(1) or "95")), indent=2))
        if text.strip() == "runtime validate independent":
            return Result(self.name, json.dumps(independent_validate(task.cwd), indent=2))
        if text.strip() in {"architecture run", "zero ai architecture run"}:
            return Result(self.name, json.dumps(architecture_run(task.cwd), indent=2))
        if text.strip() in {"architecture verify", "zero ai architecture verify"}:
            return Result(self.name, json.dumps(architecture_verify(task.cwd), indent=2))
        if text.strip() in {"architecture measure", "zero ai architecture measure"}:
            return Result(self.name, json.dumps(architecture_measure(task.cwd), indent=2))
        if text.strip() in {"architecture explain", "zero ai architecture explain"}:
            return Result(self.name, json.dumps(architecture_explain(task.cwd), indent=2))
        if text.strip() in {"architecture status", "zero ai architecture status"}:
            return Result(self.name, json.dumps(architecture_status(task.cwd), indent=2))
        if text.strip() == "security trust init":
            return Result(self.name, json.dumps(init_trust_root(task.cwd), indent=2))
        if text.strip() == "enterprise security status":
            return Result(self.name, json.dumps(enterprise_status(task.cwd), indent=2))
        if text.strip() == "enterprise integration status":
            return Result(self.name, json.dumps(integration_status(task.cwd), indent=2))
        if text.strip() == "enterprise integration bootstrap local":
            return Result(self.name, json.dumps(integration_bootstrap_local(task.cwd), indent=2))
        if text.strip() == "enterprise rollout status":
            return Result(self.name, json.dumps(rollout_status(task.cwd), indent=2))
        rollout_m = re.match(r"^enterprise rollout set\s+(dev|stage|prod)$", text.strip(), flags=re.IGNORECASE)
        if rollout_m:
            return Result(self.name, json.dumps(rollout_set(task.cwd, rollout_m.group(1)), indent=2))
        if text.strip() == "enterprise policy lock apply":
            return Result(self.name, json.dumps(policy_lock_apply(task.cwd), indent=2))
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
        if text.strip() == "enterprise key status":
            return Result(self.name, json.dumps(key_status(task.cwd), indent=2))
        ent_key_rotate = re.match(r"^enterprise key rotate(?:\s+([A-Za-z0-9._-]+))?$", text.strip(), flags=re.IGNORECASE)
        if ent_key_rotate:
            key_name = ent_key_rotate.group(1) or "operator_actions.key"
            return Result(self.name, json.dumps(key_rotate(task.cwd, key_name), indent=2))
        ent_key_revoke = re.match(r"^enterprise key revoke\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
        if ent_key_revoke:
            return Result(self.name, json.dumps(key_revoke(task.cwd, ent_key_revoke.group(1)), indent=2))
        if text.strip() == "enterprise immutable audit export":
            return Result(self.name, json.dumps(immutable_audit_export(task.cwd), indent=2))
        if text.strip() == "enterprise runbooks sync":
            return Result(self.name, json.dumps(runbooks_sync(task.cwd), indent=2))
        ent_rollout_apply = re.match(
            r"^enterprise rollout apply\s+(dev|stage|prod)(?:\s+canary=(\d+))?$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if ent_rollout_apply:
            canary = int(ent_rollout_apply.group(2) or "10")
            return Result(self.name, json.dumps(rollout_apply(task.cwd, ent_rollout_apply.group(1), canary), indent=2))
        if text.strip() == "enterprise alert routing status":
            return Result(self.name, json.dumps(alert_routing_status(task.cwd), indent=2))
        ent_route = re.match(
            r"^enterprise alert routing set\s+webhook=(\S+)(?:\s+critical=(low|medium|high|critical))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if ent_route:
            sev = ent_route.group(2) or "high"
            return Result(self.name, json.dumps(alert_routing_set(task.cwd, ent_route.group(1), sev), indent=2))
        ent_emit = re.match(r"^enterprise alert routing emit\s+(low|medium|high|critical)\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
        if ent_emit:
            return Result(
                self.name,
                json.dumps(alert_routing_emit(task.cwd, ent_emit.group(2).strip(), ent_emit.group(1).lower(), {"source": "routing"}), indent=2),
            )
        ent_dr = re.match(r"^enterprise dr drill(?:\s+rto=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if ent_dr:
            return Result(self.name, json.dumps(dr_drill(task.cwd, int(ent_dr.group(1) or "120")), indent=2))
        if text.strip() in {"enterprise max maturity apply", "max maturity apply", "max maturity all"}:
            return Result(self.name, json.dumps(enterprise_max_maturity_apply(task.cwd), indent=2))
        if text.strip() == "maturity status":
            return Result(self.name, json.dumps(maturity_status(task.cwd), indent=2))
        if text.strip() in {"maturity scaffold all", "maturity apply all", "go all"}:
            return Result(self.name, json.dumps(maturity_scaffold_all(task.cwd), indent=2))
        if text.strip() in {"zero ai harmony", "zero ai harmony status"}:
            return Result(self.name, json.dumps(zero_ai_harmony_status(task.cwd, autocorrect=True), indent=2))
        if text.strip() in {"zero ai knowledge build", "zero ai know everything"}:
            out = build_knowledge_index(task.cwd)
            st = knowledge_status(task.cwd)
            return Result(self.name, json.dumps({"build": out, "status": st}, indent=2))
        if text.strip() == "zero ai backup status":
            return Result(self.name, json.dumps(zero_ai_backup_status(task.cwd), indent=2))
        if text.strip() == "zero ai backup create":
            return Result(self.name, json.dumps(zero_ai_backup_create(task.cwd), indent=2))
        rec = re.match(r"^zero ai recover(?:\s+snapshot=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
        if rec:
            snap = rec.group(1) or "latest"
            return Result(self.name, json.dumps(zero_ai_recover(task.cwd, snapshot_id=snap), indent=2))
        if text.strip() == "zero ai knowledge status":
            return Result(self.name, json.dumps(knowledge_status(task.cwd), indent=2))
        kfind = re.match(r"^zero ai knowledge find\s+(.+?)(?:\s+limit=(\d+))?$", raw.strip(), flags=re.IGNORECASE)
        if kfind:
            query = kfind.group(1).strip().strip("\"'")
            limit = int(kfind.group(2) or "20")
            return Result(self.name, json.dumps(knowledge_find(task.cwd, query, limit=limit), indent=2))
        fp_list = re.match(r"^false positive review list(?:\s+limit=(\d+))?$", text.strip(), flags=re.IGNORECASE)
        if fp_list:
            limit = int(fp_list.group(1) or "100")
            return Result(self.name, json.dumps(list_false_positive_reviews(task.cwd, limit=limit), indent=2))
        fp_decide = re.match(
            r"^false positive review decide\s+index=(\d+)\s+verdict=(confirmed|false_positive)(?:\s+note=(.+))?$",
            raw.strip(),
            flags=re.IGNORECASE,
        )
        if fp_decide:
            idx = int(fp_decide.group(1))
            verdict = fp_decide.group(2)
            note = (fp_decide.group(3) or "").strip()
            return Result(self.name, json.dumps(decide_false_positive(task.cwd, idx, verdict, note), indent=2))
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
            rl_allowed, rl_state = check_and_record(task.cwd, "shell", limit=20, window_seconds=60)
            if not rl_allowed:
                return Result(
                    self.name,
                    json.dumps(
                        {
                            "ok": False,
                            "reason": "rate_limited",
                            "channel": "shell",
                            "retry_after_seconds": rl_state["retry_after_seconds"],
                        },
                        indent=2,
                    ),
                )
            allowed, reason = sandbox_check(task.cwd, cmd)
            if not allowed:
                return Result(self.name, json.dumps({"ok": False, "reason": reason, "command": cmd}, indent=2))
            rt_allowed, rt_reason = runtime_preexec_gate(task.cwd, f"shell run {cmd}")
            if not rt_allowed:
                return Result(self.name, json.dumps({"ok": False, "reason": rt_reason, "command": cmd}, indent=2))
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
            "- real os status\n"
            "- os reality status\n"
            "- kernel stack status\n"
            "- kernel scheduler enqueue <name> [priority=<n>] [slice=<ms>]\n"
            "- kernel scheduler tick\n"
            "- kernel memory alloc <owner> [pages=<n>]\n"
            "- kernel memory free <owner>\n"
            "- kernel driver load <name> [version=<v>]\n"
            "- kernel driver unload <name>\n"
            "- kernel block driver <ahci|nvme|virtio-blk> <on|off> [version=<v>]\n"
            "- kernel fs mount <name> path=<path> [type=<fs_type>]\n"
            "- kernel fs journal <on|off>\n"
            "- kernel fs write <mount> path=<path> data=<text>\n"
            "- kernel fs read <mount> path=<path>\n"
            "- kernel fs recover\n"
            "- kernel net iface add <name> cidr=<cidr>\n"
            "- kernel net route add <destination> via=<gateway>\n"
            "- kernel net protocol <arp|ip|tcp|udp|dhcp|dns> <on|off>\n"
            "- kernel nic driver set <nic> driver=<name> [on|off]\n"
            "- kernel input <keyboard|mouse> driver=<name> <on|off>\n"
            "- kernel display driver <name> mode=<mode>\n"
            "- kernel platform set [acpi=on|off] [apic=on|off] [smp=on|off] [cpus=<n>]\n"
            "- kernel uefi status\n"
            "- kernel uefi scaffold\n"
            "- kernel elf load <path>\n"
            "- kernel module load <path>\n"
            "- kernel modules status\n"
            "- kernel panic trigger <reason>\n"
            "- kernel panic status\n"
            "- kernel panic recover\n"
            "- kernel secure boot <on|off> [pk=<hash>]\n"
            "- kernel measured boot record <component> path=<path>\n"
            "- kernel measured boot status\n"
            "- kernel boot verify <path> sha256=<hex>\n"
            "- store validate <package_dir>\n"
            "- store publish <package_dir>\n"
            "- store list\n"
            "- store resolve <app_name> [os=<windows|linux|macos|android|ios>]\n"
            "- store resolve device <app_name> [os=<...>] [cpu=<...>] [arch=<...>] [security=<...>]\n"
            "- store client detect\n"
            "- store security scan <app_name>\n"
            "- store account create email=<email> [tier=<free|pro|enterprise>]\n"
            "- store billing charge user=<id> amount=<n> [currency=<code>]\n"
            "- store license grant user=<id> app=<name>\n"
            "- store install user=<id> app=<name> [os=<target_os>]\n"
            "- store uninstall id=<install_id>\n"
            "- store upgrade id=<install_id> version=<v>\n"
            "- store security enforce app=<name>\n"
            "- store replicate app=<name> version=<v>\n"
            "- store rollback app=<name> version=<v>\n"
            "- store review add app=<name> user=<id> rating=<1..5> [text=<msg>]\n"
            "- store search <query>\n"
            "- store analytics status\n"
            "- store policy ios external <on|off>\n"
            "- store compliance status\n"
            "- store telemetry status\n"
            "- store slo set availability=<n> p95=<sec>\n"
            "- store abuse block ip <ip>\n"
            "- runtime network node register os=<os> device=<class> mode=<mode>\n"
            "- runtime network node discover [os=<os>]\n"
            "- runtime network cache put app=<name> version=<v> region=<r>\n"
            "- runtime network cache status\n"
            "- runtime network release propagate version=<v>\n"
            "- runtime network security validate signed=<true|false>\n"
            "- runtime network adaptive mode device=<class>\n"
            "- runtime network status\n"
            "- runtime network telemetry\n"
            "- runtime protocol status\n"
            "- runtime protocol security status\n"
            "- runtime protocol security grade\n"
            "- runtime protocol security maximize\n"
            "- runtime protocol security set strict=<on|off> min=<low|baseline|strict|high>\n"
            "- runtime protocol signer allow <name>\n"
            "- runtime protocol signer revoke <name>\n"
            "- runtime protocol key rotate\n"
            "- runtime protocol adapter <windows|linux|macos|android|ios>\n"
            "- runtime protocol adapter allowlist <windows|linux|macos|android|ios> hash=<sha256>\n"
            "- runtime protocol nonce issue node=<id>\n"
            "- runtime protocol handshake os=<os> cpu=<cpu> arch=<arch> security=<level>\n"
            "- runtime protocol secure handshake os=<os> cpu=<cpu> arch=<arch> security=<level> nonce=<n> proof=<p>\n"
            "- runtime protocol proof preview os=<os> cpu=<cpu> arch=<arch> security=<level> nonce=<n>\n"
            "- runtime protocol attest path=<path> signer=<name>\n"
            "- runtime protocol verify path=<path> signer=<name> signature=<sig>\n"
            "- runtime protocol compatibility version=<v>\n"
            "- runtime protocol deprecate api=<name> remove_after=<date>\n"
            "- runtime protocol audit status\n"
            "- runtime protocol ecosystem status\n"
            "- runtime protocol ecosystem grade\n"
            "- runtime protocol ecosystem maximize\n"
            "- rcrp status\n"
            "- rcrp device set [cpu=<c>] [gpu=<g>] [ram=<gb>] [network=<n>] [energy=<mode>]\n"
            "- rcrp graph register app=<name> json=<graph_json>\n"
            "- rcrp token set <token_name> <on|off>\n"
            "- rcrp plan build app=<name>\n"
            "- rcrp mesh node register name=<node> power=<tier>\n"
            "- rcrp migrate app=<name> plan=<plan_id> target=<node_id>\n"
            "- rcrp learning observe <observation>\n"
            "- serp status\n"
            "- serp telemetry submit node=<n> region=<r> cpu=<p> memory=<p> gpu=<p> latency=<ms> energy=<p>\n"
            "- serp analyze\n"
            "- serp mutation propose component=<scheduler|memory|translator|gpu> strategy=<name> signer=<id>\n"
            "- serp deploy staged mutation=<id> percent=<1..100>\n"
            "- serp rollback\n"
            "- serp state export app=<name> json=<state_json>\n"
            "- serp state import id=<state_id> target=<node>\n"
            "- autonomous runtime ecosystem status\n"
            "- autonomous runtime ecosystem node register role=<edge|compute|coordination|archive> name=<n> [os=<os>] [power=<p>]\n"
            "- autonomous runtime ecosystem optimize\n"
            "- autonomous runtime ecosystem governance propose component=<name> strategy=<name>\n"
            "- autonomous runtime ecosystem governance simulate\n"
            "- autonomous runtime ecosystem governance rollout percent=<1..100>\n"
            "- autonomous runtime ecosystem governance validate\n"
            "- autonomous runtime ecosystem grade\n"
            "- autonomous runtime ecosystem maximize\n"
            "- hardware runtime status\n"
            "- hardware runtime set [accelerator=on|off] [security=on|off] [memory=on|off] [network=on|off]\n"
            "- hardware runtime maximize\n"
            "- runtime evolve app <app_name>\n"
            "- runtime memory learn app=<name> key=<k> value=<v>\n"
            "- runtime memory get app=<name>\n"
            "- runtime fabric node register name=<node> power=<tier>\n"
            "- runtime fabric dispatch app=<name> task=<task> [nodes=<n>]\n"
            "- runtime fabric status\n"
            "- ria status\n"
            "- ria program register app=<name> json=<instruction_json>\n"
            "- ria program validate id=<program_id>\n"
            "- ria execute id=<program_id> [caps=<json>]\n"
            "- runtime economy status\n"
            "- runtime economy actor register role=<developer|runtime_node_operator|storage_node|optimization_node> name=<name>\n"
            "- runtime economy contribution actor=<id> kind=<compute|bandwidth|optimization> units=<n>\n"
            "- runtime economy payout actor=<id> amount=<n>\n"
            "- platform blueprint status\n"
            "- platform blueprint scaffold\n"
            "- native store status\n"
            "- native store enterprise status\n"
            "- native store enterprise signing set type=<kms|hsm> name=<provider> key=<ref> hsm=<on|off>\n"
            "- native store enterprise vendor configure channel=<microsoft|apple|google_play|app_store_connect> identity=<id>\n"
            "- native store enterprise backend set replicas=<n> tls=<on|off> monitoring=<on|off> alerting=<on|off> storage=<on|off> dr=<strategy>\n"
            "- native store enterprise desktop set binary=<on|off> updater=<on|off> service=<on|off> registration=<on|off> crash=<on|off>\n"
            "- native store enterprise secrets set provider=<name> ca=<name> revocation=<on|off>\n"
            "- native store enterprise governance set oncall=<a,b> approvers=<a,b> freeze=<on|off>\n"
            "- native store enterprise deployed test target=<env> passed=<on|off>\n"
            "- native store scaffold vendor app=<name> version=<v>\n"
            "- native store scaffold services\n"
            "- native store scaffold backend\n"
            "- native store scaffold gui\n"
            "- native store backend init\n"
            "- native store backend status\n"
            "- native store backend deploy scaffold\n"
            "- native store backend backup [name=<name>]\n"
            "- native store backend restore path=<backup_path>\n"
            "- native store backend user create id=<id> email=<email> tier=<tier>\n"
            "- native store backend token issue id=<id> scope=<scope>\n"
            "- native store backend charge id=<charge_id> user=<user_id> amount=<n> currency=<code>\n"
            "- native store backend event kind=<name> json=<json>\n"
            "- native store desktop scaffold\n"
            "- native store desktop launch\n"
            "- native store build windows app=<name> version=<v>\n"
            "- native store build linux app=<name> version=<v>\n"
            "- native store build macos app=<name> version=<v> [signer=<identity>]\n"
            "- native store build mobile app=<name> version=<v>\n"
            "- native store pipeline run app=<name> os=<windows|linux|macos|android|ios> [format=<msix|msi|deb|rpm|pkg|app|apk|ipa>]\n"
            "- native store install app=<name> [os=<target_os>]\n"
            "- native store uninstall id=<install_id>\n"
            "- native store upgrade id=<install_id> version=<v>\n"
            "- native store service set os=<windows|linux|macos|android|ios> enabled=<on|off>\n"
            "- native store trust channel set name=<stable|beta> signed=<on|off> notarization=<on|off>\n"
            "- native store notarize app=<name> version=<v> signer=<id>\n"
            "- native store backend integrate component=<identity|payments|fraud|cdn|compliance|legal_ops> provider=<name> enabled=<on|off>\n"
            "- native store gui set [first_run=<on|off>] [deep=<on|off>]\n"
            "- native store desktop package app=<name> version=<v>\n"
            "- native store secret set name=<name> value=<value>\n"
            "- native store cert rotate name=<cert>\n"
            "- native store rollback checkpoint name=<checkpoint>\n"
            "- native store rollback restore name=<checkpoint>\n"
            "- native store incident open severity=<sev> summary=<text>\n"
            "- native store stress test traffic=<n> abuse=<n> failures=<n>\n"
            "- native store release prepare version=<v> [channel=<stable|beta|canary>]\n"
            "- native store artifact sign path=<artifact_path> signer=<name>\n"
            "- native store artifact verify path=<artifact_path>\n"
            "- native store e2e run app=<name> version=<v> traffic=<n> abuse=<n> failures=<n>\n"
            "- native store maximize\n"
            "- universal runtime install [version=<v>]\n"
            "- universal runtime status\n"
            "- universal adapters status\n"
            "- universal adapter set <windows|linux|macos|android|ios> <module>\n"
            "- universal execution flow <app_name> [os=<target_os>]\n"
            "- universal security status\n"
            "- universal infrastructure status\n"
            "- universal ecosystem coverage\n"
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
            "- zero ai security apply\n"
            "- zero ai security status\n"
            "- zero ai brain awareness build\n"
            "- zero ai brain awareness status\n"
            "- zero ai identity\n"
            "- zero ai consciousness status\n"
            "- zero ai conscious architecture\n"
            "- conscious machine architecture phase 2\n"
            "- conscious machine architecture phase 3\n"
            "- conscious machine architecture phase 4\n"
            "- conscious machine architecture phase 5\n"
            "- conscious machine architecture phase 6\n"
            "- conscious machine architecture phase 7\n"
            "- conscious machine architecture phase 8\n"
            "- conscious machine architecture phase 9\n"
            "- reflexive causality engine\n"
            "- self-generating ontology engine\n"
            "- temporal identity field\n"
            "- crystal lattice cognition\n"
            "- hybrid crystal cognition architecture\n"
            "- silicon awareness machine\n"
            "- strong persistent long-term memory\n"
            "- zero ai consciousness tick [prompt]\n"
            "- zero ai gap status\n"
            "- zero ai gap fix\n"
            "- zero ai runtime status\n"
            "- zero ai runtime run\n"
            "- runtime telemetry ingest [source=<name>]\n"
            "- runtime node publish <node> <json_payload>\n"
            "- runtime node consensus\n"
            "- runtime adversarial validate\n"
            "- runtime dashboard export\n"
            "- runtime slo check [min=<score>]\n"
            "- runtime validate independent\n"
            "- architecture run\n"
            "- architecture status\n"
            "- architecture verify\n"
            "- architecture measure\n"
            "- architecture explain\n"
            "- zero ai fix all\n"
            "- fix all now\n"
            "- security trust init\n"
            "- enterprise security status\n"
            "- enterprise security on [siem=<webhook_url>]\n"
            "- enterprise security off\n"
            "- enterprise role set <user> <admin|operator|viewer>\n"
            "- enterprise integration status\n"
            "- enterprise integration bootstrap local\n"
            "- enterprise integration set <edr|siem|iam|zerotrust> <on|off> [provider=<name>] [endpoint=<url_or_tenant>]\n"
            "- enterprise integration probe <edr|siem|iam|zerotrust>\n"
            "- enterprise rollout status\n"
            "- enterprise rollout set <dev|stage|prod>\n"
            "- enterprise policy lock apply\n"
            "- enterprise sign action user=<user> <action_text>\n"
            "- enterprise siem emit <low|medium|high|critical> <event>\n"
            "- enterprise rollback run <critical|ransomware|integrity_failure>\n"
            "- enterprise validate adversarial\n"
            "- enterprise key status\n"
            "- enterprise key rotate [key_name]\n"
            "- enterprise key revoke <key_name>\n"
            "- enterprise immutable audit export\n"
            "- enterprise runbooks sync\n"
            "- enterprise rollout apply <dev|stage|prod> [canary=<1-100>]\n"
            "- enterprise alert routing status\n"
            "- enterprise alert routing set webhook=<url> [critical=<low|medium|high|critical>]\n"
            "- enterprise alert routing emit <low|medium|high|critical> <event>\n"
            "- enterprise dr drill [rto=<seconds>]\n"
            "- enterprise max maturity apply\n"
            "- maturity status\n"
            "- maturity scaffold all\n"
            "- zero ai harmony\n"
            "- zero ai knowledge build\n"
            "- zero ai knowledge status\n"
            "- zero ai knowledge find <query> [limit=<n>]\n"
            "- zero ai know everything\n"
            "- zero ai backup status\n"
            "- zero ai backup create\n"
            "- zero ai recover [snapshot=<id|latest>]\n"
            "- false positive review list [limit=<n>]\n"
            "- false positive review decide index=<n> verdict=<confirmed|false_positive> [note=<text>]\n"
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

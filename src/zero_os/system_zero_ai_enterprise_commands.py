from __future__ import annotations

import json
import re

from zero_os.enterprise_security import (
    adversarial_validate,
    enterprise_enable,
    enterprise_status,
    integration_bootstrap_local,
    integration_configure,
    integration_probe,
    integration_status,
    policy_lock_apply,
    rollout_set,
    rollout_status,
    rollback_playbook_run,
    set_role as enterprise_set_role,
    siem_emit,
    sign_action as enterprise_sign_action,
)
from zero_os.harmony import zero_ai_harmony_status
from zero_os.maturity import maturity_scaffold_all, maturity_status
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
from zero_os.security_hardening import init_trust_root
from zero_os.types import Result, Task


def handle_zero_ai_enterprise_command(task: Task, raw: str, text: str) -> Result | None:
    normalized = text.strip()
    if normalized == "security trust init":
        return Result("system", json.dumps(init_trust_root(task.cwd), indent=2))
    if normalized == "enterprise security status":
        return Result("system", json.dumps(enterprise_status(task.cwd), indent=2))
    if normalized == "enterprise integration status":
        return Result("system", json.dumps(integration_status(task.cwd), indent=2))
    if normalized == "enterprise integration bootstrap local":
        return Result("system", json.dumps(integration_bootstrap_local(task.cwd), indent=2))
    if normalized == "enterprise rollout status":
        return Result("system", json.dumps(rollout_status(task.cwd), indent=2))

    rollout_set_match = re.match(r"^enterprise rollout set\s+(dev|stage|prod)$", normalized, flags=re.IGNORECASE)
    if rollout_set_match:
        return Result("system", json.dumps(rollout_set(task.cwd, rollout_set_match.group(1)), indent=2))

    if normalized == "enterprise policy lock apply":
        return Result("system", json.dumps(policy_lock_apply(task.cwd), indent=2))

    integration_config_match = re.match(
        r"^enterprise integration set\s+(edr|siem|iam|zerotrust)\s+(on|off)(?:\s+provider=(\S+))?(?:\s+endpoint=(\S+))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if integration_config_match:
        return Result(
            "system",
            json.dumps(
                integration_configure(
                    task.cwd,
                    integration_config_match.group(1).lower(),
                    integration_config_match.group(2).lower() == "on",
                    integration_config_match.group(3) or "",
                    integration_config_match.group(4) or "",
                ),
                indent=2,
            ),
        )

    integration_probe_match = re.match(
        r"^enterprise integration probe\s+(edr|siem|iam|zerotrust)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if integration_probe_match:
        return Result("system", json.dumps(integration_probe(task.cwd, integration_probe_match.group(1)), indent=2))

    enterprise_on_match = re.match(r"^enterprise security on(?:\s+siem=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
    if enterprise_on_match:
        siem = enterprise_on_match.group(1) if enterprise_on_match.group(1) else None
        return Result("system", json.dumps(enterprise_enable(task.cwd, True, siem), indent=2))

    if normalized == "enterprise security off":
        return Result("system", json.dumps(enterprise_enable(task.cwd, False), indent=2))

    role_match = re.match(
        r"^enterprise role set\s+([A-Za-z0-9._-]+)\s+(admin|operator|viewer)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if role_match:
        return Result("system", json.dumps(enterprise_set_role(task.cwd, role_match.group(1), role_match.group(2)), indent=2))

    sign_match = re.match(r"^enterprise sign action\s+user=([A-Za-z0-9._-]+)\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if sign_match:
        return Result("system", json.dumps(enterprise_sign_action(task.cwd, sign_match.group(1), sign_match.group(2).strip()), indent=2))

    siem_match = re.match(r"^enterprise siem emit\s+(low|medium|high|critical)\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if siem_match:
        return Result(
            "system",
            json.dumps(siem_emit(task.cwd, siem_match.group(2).strip(), siem_match.group(1).lower(), {"source": "system_command"}), indent=2),
        )

    rollback_match = re.match(r"^enterprise rollback run\s+([A-Za-z0-9._-]+)$", normalized, flags=re.IGNORECASE)
    if rollback_match:
        return Result("system", json.dumps(rollback_playbook_run(task.cwd, rollback_match.group(1)), indent=2))

    if normalized == "enterprise validate adversarial":
        return Result("system", json.dumps(adversarial_validate(task.cwd), indent=2))
    if normalized == "enterprise key status":
        return Result("system", json.dumps(key_status(task.cwd), indent=2))

    key_rotate_match = re.match(r"^enterprise key rotate(?:\s+([A-Za-z0-9._-]+))?$", normalized, flags=re.IGNORECASE)
    if key_rotate_match:
        return Result("system", json.dumps(key_rotate(task.cwd, key_rotate_match.group(1) or "operator_actions.key"), indent=2))

    key_revoke_match = re.match(r"^enterprise key revoke\s+([A-Za-z0-9._-]+)$", normalized, flags=re.IGNORECASE)
    if key_revoke_match:
        return Result("system", json.dumps(key_revoke(task.cwd, key_revoke_match.group(1)), indent=2))

    if normalized == "enterprise immutable audit export":
        return Result("system", json.dumps(immutable_audit_export(task.cwd), indent=2))
    if normalized == "enterprise runbooks sync":
        return Result("system", json.dumps(runbooks_sync(task.cwd), indent=2))

    rollout_apply_match = re.match(
        r"^enterprise rollout apply\s+(dev|stage|prod)(?:\s+canary=(\d+))?$",
        normalized,
        flags=re.IGNORECASE,
    )
    if rollout_apply_match:
        return Result(
            "system",
            json.dumps(rollout_apply(task.cwd, rollout_apply_match.group(1), int(rollout_apply_match.group(2) or "10")), indent=2),
        )

    if normalized == "enterprise alert routing status":
        return Result("system", json.dumps(alert_routing_status(task.cwd), indent=2))

    alert_route_match = re.match(
        r"^enterprise alert routing set\s+webhook=(\S+)(?:\s+critical=(low|medium|high|critical))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if alert_route_match:
        return Result("system", json.dumps(alert_routing_set(task.cwd, alert_route_match.group(1), alert_route_match.group(2) or "high"), indent=2))

    alert_emit_match = re.match(
        r"^enterprise alert routing emit\s+(low|medium|high|critical)\s+(.+)$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if alert_emit_match:
        return Result(
            "system",
            json.dumps(
                alert_routing_emit(task.cwd, alert_emit_match.group(2).strip(), alert_emit_match.group(1).lower(), {"source": "routing"}),
                indent=2,
            ),
        )

    dr_match = re.match(r"^enterprise dr drill(?:\s+rto=(\d+))?$", normalized, flags=re.IGNORECASE)
    if dr_match:
        return Result("system", json.dumps(dr_drill(task.cwd, int(dr_match.group(1) or "120")), indent=2))

    if normalized in {"enterprise max maturity apply", "max maturity apply", "max maturity all"}:
        return Result("system", json.dumps(enterprise_max_maturity_apply(task.cwd), indent=2))
    if normalized == "maturity status":
        return Result("system", json.dumps(maturity_status(task.cwd), indent=2))
    if normalized in {"maturity scaffold all", "maturity apply all", "go all"}:
        return Result("system", json.dumps(maturity_scaffold_all(task.cwd), indent=2))
    if normalized in {"zero ai harmony", "zero ai harmony status"}:
        return Result("system", json.dumps(zero_ai_harmony_status(task.cwd, autocorrect=True), indent=2))

    return None

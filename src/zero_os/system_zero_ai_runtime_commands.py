from __future__ import annotations

import json
import re

from zero_os.agent_permission_policy import policy_status as zero_ai_agent_policy_status, set_action_tier as zero_ai_set_action_tier
from zero_os.autonomous_fix_gate import autonomy_evaluate, autonomy_status
from zero_os.phase_runtime import zero_ai_runtime_run, zero_ai_runtime_status
from zero_os.recovery import (
    zero_ai_backup_create,
    zero_ai_backup_pin,
    zero_ai_backup_prune,
    zero_ai_backup_status,
    zero_ai_recover,
    zero_ai_recovery_inventory,
)
from zero_os.task_planner import planner_feedback_status, smart_planner_assess, smart_planner_status
from zero_os.types import Result, Task
from zero_os.zero_ai_pressure_harness import pressure_harness_refresh, pressure_harness_run, pressure_harness_status


def handle_zero_ai_runtime_command(task: Task, raw: str, text: str) -> Result | None:
    normalized = text.strip()
    if normalized == "zero ai autonomy status":
        return Result("system", json.dumps(autonomy_status(task.cwd), indent=2))
    if normalized in {"zero ai autonomy tiers", "zero ai autonomy tiers status", "zero ai autonomy policy", "zero ai autonomy policy status"}:
        return Result("system", json.dumps(zero_ai_agent_policy_status(task.cwd), indent=2))

    autonomy_tier_set = re.match(
        r"^zero ai autonomy tier set\s+([a-zA-Z0-9_]+)\s+(observe_only|safe_auto|guarded_auto|approval_required|forbidden)$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if autonomy_tier_set:
        return Result(
            "system",
            json.dumps(
                zero_ai_set_action_tier(task.cwd, autonomy_tier_set.group(1), autonomy_tier_set.group(2)),
                indent=2,
            ),
        )

    autonomy_eval = re.match(
        r"^zero ai autonomy evaluate\s+action=(.+?)\s+radius=(.+?)\s+reversible=(on|off)\s+evidence=(\d+)\s+contradictions=(\d+)\s+verifiers=(\d+)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if autonomy_eval:
        return Result(
            "system",
            json.dumps(
                autonomy_evaluate(
                    action=autonomy_eval.group(1).strip(),
                    radius=autonomy_eval.group(2).strip(),
                    reversible=autonomy_eval.group(3).strip().lower() == "on",
                    evidence_count=int(autonomy_eval.group(4)),
                    contradiction_count=int(autonomy_eval.group(5)),
                    verifier_count=int(autonomy_eval.group(6)),
                ),
                indent=2,
            ),
        )

    if normalized in {"zero ai runtime status", "phase runtime status"}:
        return Result("system", json.dumps(zero_ai_runtime_status(task.cwd), indent=2))
    if normalized in {"zero ai runtime run", "phase runtime run", "zero ai runtime all"}:
        return Result("system", json.dumps(zero_ai_runtime_run(task.cwd), indent=2))

    if normalized in {"pressure harness", "zero ai pressure status", "zero ai pressure harness status"}:
        return Result("system", json.dumps(pressure_harness_status(task.cwd), indent=2))
    if normalized in {"zero ai pressure run", "zero ai pressure harness run"}:
        return Result("system", json.dumps(pressure_harness_run(task.cwd), indent=2))
    if normalized in {"zero ai pressure refresh", "zero ai pressure harness refresh"}:
        return Result("system", json.dumps(pressure_harness_refresh(task.cwd), indent=2))
    if normalized in {"zero ai planner feedback", "zero ai planner feedback status", "planner feedback status"}:
        return Result("system", json.dumps(planner_feedback_status(task.cwd), indent=2))
    if normalized in {"zero ai smart planner", "zero ai smart planner status", "smart planner status"}:
        return Result("system", json.dumps(smart_planner_status(task.cwd), indent=2))

    smart_planner_assess_match = re.match(r"^zero ai smart planner assess\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if smart_planner_assess_match:
        return Result("system", json.dumps(smart_planner_assess(smart_planner_assess_match.group(1).strip(), task.cwd), indent=2))

    if normalized == "zero ai backup status":
        return Result("system", json.dumps(zero_ai_backup_status(task.cwd), indent=2))
    if normalized == "zero ai backup create":
        return Result("system", json.dumps(zero_ai_backup_create(task.cwd), indent=2))
    if normalized == "zero ai recovery inventory":
        return Result("system", json.dumps(zero_ai_recovery_inventory(task.cwd), indent=2))

    backup_pin = re.match(r"^zero ai backup pin\s+(\S+)(?:\s+known_good=(true|false))?$", raw.strip(), flags=re.IGNORECASE)
    if backup_pin:
        return Result(
            "system",
            json.dumps(
                zero_ai_backup_pin(
                    task.cwd,
                    backup_pin.group(1),
                    known_good=str(backup_pin.group(2) or "").lower() == "true",
                ),
                indent=2,
            ),
        )

    backup_prune = re.match(r"^zero ai backup prune(?:\s+keep_latest=(\d+))?$", raw.strip(), flags=re.IGNORECASE)
    if backup_prune:
        return Result(
            "system",
            json.dumps(zero_ai_backup_prune(task.cwd, keep_latest=int(backup_prune.group(1) or "2")), indent=2),
        )

    recover = re.match(r"^zero ai recover(?:\s+snapshot=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
    if recover:
        return Result("system", json.dumps(zero_ai_recover(task.cwd, snapshot_id=recover.group(1) or "latest"), indent=2))

    return None

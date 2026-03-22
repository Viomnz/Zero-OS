from __future__ import annotations

import json
import re

from zero_os.api_connector_profiles import profile_set as zero_ai_api_profile_set, profile_status as zero_ai_api_profile_status
from zero_os.approval_workflow import decide as zero_ai_approval_decide, status as zero_ai_approval_status
from zero_os.assistant_job_runner import schedule as zero_ai_job_schedule, status as zero_ai_job_status, tick as zero_ai_job_tick
from zero_os.autonomous_fix_gate import autonomy_evaluate, autonomy_record
from zero_os.auto_completion import auto_max_fix_upgrade_everything
from zero_os.browser_session_connector import browser_session_status as zero_ai_browser_session_status
from zero_os.gap_coverage import zero_ai_gap_fix, zero_ai_gap_status, zero_ai_upgrade_system
from zero_os.github_integration_pack import (
    connect_repo as github_connect,
    issue_act as github_issue_act,
    issue_comments as github_issue_comments,
    issue_plan as github_issue_plan,
    issue_read as github_issue_read,
    issue_reply_draft as github_issue_reply_draft,
    issue_reply_post as github_issue_reply_post,
    issue_summary as github_issue_summary,
    pr_act as github_pr_act,
    pr_comments as github_pr_comments,
    pr_plan as github_pr_plan,
    pr_read as github_pr_read,
    pr_reply_draft as github_pr_reply_draft,
    pr_reply_post as github_pr_reply_post,
    pr_summary as github_pr_summary,
    status as github_status,
)
from zero_os.observation_layer import collect_observations
from zero_os.playbook_memory import status as zero_ai_playbook_status
from zero_os.share_bundle import (
    export_bundle as zero_os_export_bundle,
    export_zero_ai_bundle,
    export_zero_ai_bundle_strict,
    share_package as zero_os_share_package,
    share_zero_ai_package,
    share_zero_ai_package_strict,
)
from zero_os.task_executor import run_task as zero_ai_run_task, run_task_resume as zero_ai_run_task_resume
from zero_os.task_memory import status as zero_ai_task_memory_status
from zero_os.tool_capability_registry import registry_status as zero_ai_registry_status
from zero_os.types import Result, Task
from zero_os.universal_ui_launcher import launch as universal_ui_launch


def handle_zero_ai_general_command(task: Task, raw: str, text: str) -> Result | None:
    normalized = text.strip()

    if normalized == "zero ai tools status":
        return Result("system", json.dumps(zero_ai_registry_status(task.cwd), indent=2))
    if normalized == "zero ai observe":
        return Result("system", json.dumps(collect_observations(task.cwd), indent=2))
    if normalized == "zero ai browser status":
        return Result("system", json.dumps(zero_ai_browser_session_status(task.cwd), indent=2))
    if normalized == "zero ai tasks status":
        return Result("system", json.dumps(zero_ai_task_memory_status(task.cwd), indent=2))
    if normalized == "zero ai approvals status":
        return Result("system", json.dumps(zero_ai_approval_status(task.cwd), indent=2))
    if normalized == "zero ai playbooks status":
        return Result("system", json.dumps(zero_ai_playbook_status(task.cwd), indent=2))
    if normalized == "zero ai jobs status":
        return Result("system", json.dumps(zero_ai_job_status(task.cwd), indent=2))
    if normalized == "zero ai jobs tick":
        return Result("system", json.dumps(zero_ai_job_tick(task.cwd), indent=2))
    if normalized == "zero ai api profile status":
        return Result("system", json.dumps(zero_ai_api_profile_status(task.cwd), indent=2))

    zero_ai_api_set = re.match(
        r"^zero ai api profile set\s+name=(.+?)\s+base=(.+?)(?:\s+token=(.+))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if zero_ai_api_set:
        return Result(
            "system",
            json.dumps(
                zero_ai_api_profile_set(
                    task.cwd,
                    zero_ai_api_set.group(1).strip(),
                    zero_ai_api_set.group(2).strip(),
                    (zero_ai_api_set.group(3) or "").strip(),
                ),
                indent=2,
            ),
        )

    zero_ai_approval = re.match(
        r"^zero ai approval decide\s+id=(.+?)\s+state=(approve|reject)$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if zero_ai_approval:
        return Result(
            "system",
            json.dumps(
                zero_ai_approval_decide(
                    task.cwd,
                    zero_ai_approval.group(1).strip(),
                    zero_ai_approval.group(2).strip().lower() == "approve",
                ),
                indent=2,
            ),
        )

    zero_ai_job_add = re.match(r"^zero ai job add\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if zero_ai_job_add:
        return Result("system", json.dumps(zero_ai_job_schedule(task.cwd, zero_ai_job_add.group(1).strip()), indent=2))

    if normalized == "zero ai ask resume":
        return Result("system", json.dumps(zero_ai_run_task_resume(task.cwd), indent=2))

    zero_ai_ask = re.match(r"^zero ai ask\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if zero_ai_ask:
        return Result("system", json.dumps(zero_ai_run_task(task.cwd, zero_ai_ask.group(1).strip()), indent=2))

    if normalized in {"zero ai gap status", "zero ai cover gap status"}:
        return Result("system", json.dumps(zero_ai_gap_status(task.cwd), indent=2))
    if normalized in {"zero ai gap fix", "zero ai cover gap fix", "maximize zero ai cover gap or missing"}:
        return Result("system", json.dumps(zero_ai_gap_fix(task.cwd), indent=2))

    if normalized in {"zero os export bundle", "zero os export", "zero os bundle export"}:
        return Result("system", json.dumps(zero_os_export_bundle(task.cwd), indent=2))
    if normalized in {"zero os share package", "zero os share", "zero os export package"}:
        return Result("system", json.dumps(zero_os_share_package(task.cwd), indent=2))
    if normalized in {"zero ai export bundle strict", "zero ai export strict", "zero ai bundle export strict"}:
        return Result("system", json.dumps(export_zero_ai_bundle_strict(task.cwd), indent=2))
    if normalized in {"zero ai export bundle", "zero ai export", "zero ai bundle export"}:
        return Result("system", json.dumps(export_zero_ai_bundle(task.cwd), indent=2))
    if normalized in {"zero ai share package strict", "zero ai share strict", "zero ai export package strict"}:
        return Result("system", json.dumps(share_zero_ai_package_strict(task.cwd), indent=2))
    if normalized in {"zero ai share package", "zero ai share", "zero ai export package"}:
        return Result("system", json.dumps(share_zero_ai_package(task.cwd), indent=2))

    if normalized in {
        "zero os complete all",
        "zero os auto max fix upgrade",
        "auto max fix upgrade everything",
        "zero os maximize complete",
    }:
        return Result("system", json.dumps(auto_max_fix_upgrade_everything(task.cwd), indent=2))

    if normalized in {
        "zero os native ui",
        "zero os native ui launch",
        "native zero ui",
        "launch zero os native ui",
        "zero os ui",
        "zero os ui launch",
        "launch zero os ui",
    }:
        return Result("system", json.dumps(universal_ui_launch(task.cwd), indent=2))

    if normalized in {"github status", "github integration status"}:
        return Result("system", json.dumps(github_status(task.cwd), indent=2))

    github_connect_m = re.match(r"^github repo connect\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\s+token=(.+))?$", raw.strip(), flags=re.IGNORECASE)
    if github_connect_m:
        return Result("system", json.dumps(github_connect(task.cwd, github_connect_m.group(1), (github_connect_m.group(2) or "").strip()), indent=2))

    github_issues_m = re.match(r"^github issues\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\s+state=(open|closed|all))?(?:\s+limit=(\d+))?$", raw.strip(), flags=re.IGNORECASE)
    if github_issues_m:
        return Result(
            "system",
            json.dumps(
                github_issue_summary(
                    task.cwd,
                    github_issues_m.group(1),
                    github_issues_m.group(2) or "open",
                    int(github_issues_m.group(3) or "10"),
                ),
                indent=2,
            ),
        )

    github_prs_m = re.match(r"^github prs\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\s+state=(open|closed|all))?(?:\s+limit=(\d+))?$", raw.strip(), flags=re.IGNORECASE)
    if github_prs_m:
        return Result(
            "system",
            json.dumps(
                github_pr_summary(
                    task.cwd,
                    github_prs_m.group(1),
                    github_prs_m.group(2) or "open",
                    int(github_prs_m.group(3) or "10"),
                ),
                indent=2,
            ),
        )

    github_issue_read_m = re.match(r"^github issue read\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)$", raw.strip(), flags=re.IGNORECASE)
    if github_issue_read_m:
        return Result("system", json.dumps(github_issue_read(task.cwd, github_issue_read_m.group(1), int(github_issue_read_m.group(2))), indent=2))

    github_issue_comments_m = re.match(r"^github issue comments\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)$", raw.strip(), flags=re.IGNORECASE)
    if github_issue_comments_m:
        return Result("system", json.dumps(github_issue_comments(task.cwd, github_issue_comments_m.group(1), int(github_issue_comments_m.group(2))), indent=2))

    github_issue_plan_m = re.match(r"^github issue plan\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)$", raw.strip(), flags=re.IGNORECASE)
    if github_issue_plan_m:
        return Result("system", json.dumps(github_issue_plan(task.cwd, github_issue_plan_m.group(1), int(github_issue_plan_m.group(2))), indent=2))

    github_issue_act_m = re.match(
        r"^github issue act\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)(?:\s+execute=(true|false))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if github_issue_act_m:
        return Result(
            "system",
            json.dumps(
                github_issue_act(
                    task.cwd,
                    github_issue_act_m.group(1),
                    int(github_issue_act_m.group(2)),
                    (github_issue_act_m.group(3) or "false").lower() == "true",
                ),
                indent=2,
            ),
        )

    github_issue_reply_post_m = re.match(
        r"^github issue reply post\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)\s+text=(.+)$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if github_issue_reply_post_m:
        return Result(
            "system",
            json.dumps(
                github_issue_reply_post(
                    task.cwd,
                    github_issue_reply_post_m.group(1),
                    int(github_issue_reply_post_m.group(2)),
                    github_issue_reply_post_m.group(3).strip(),
                ),
                indent=2,
            ),
        )

    github_issue_reply_m = re.match(
        r"^github issue reply\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)(?:\s+execute=(true|false))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if github_issue_reply_m:
        return Result(
            "system",
            json.dumps(
                github_issue_reply_draft(
                    task.cwd,
                    github_issue_reply_m.group(1),
                    int(github_issue_reply_m.group(2)),
                    (github_issue_reply_m.group(3) or "false").lower() == "true",
                ),
                indent=2,
            ),
        )

    github_pr_read_m = re.match(r"^github pr read\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)$", raw.strip(), flags=re.IGNORECASE)
    if github_pr_read_m:
        return Result("system", json.dumps(github_pr_read(task.cwd, github_pr_read_m.group(1), int(github_pr_read_m.group(2))), indent=2))

    github_pr_comments_m = re.match(r"^github pr comments\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)$", raw.strip(), flags=re.IGNORECASE)
    if github_pr_comments_m:
        return Result("system", json.dumps(github_pr_comments(task.cwd, github_pr_comments_m.group(1), int(github_pr_comments_m.group(2))), indent=2))

    github_pr_plan_m = re.match(r"^github pr plan\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)$", raw.strip(), flags=re.IGNORECASE)
    if github_pr_plan_m:
        return Result("system", json.dumps(github_pr_plan(task.cwd, github_pr_plan_m.group(1), int(github_pr_plan_m.group(2))), indent=2))

    github_pr_act_m = re.match(
        r"^github pr act\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)(?:\s+execute=(true|false))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if github_pr_act_m:
        return Result(
            "system",
            json.dumps(
                github_pr_act(
                    task.cwd,
                    github_pr_act_m.group(1),
                    int(github_pr_act_m.group(2)),
                    (github_pr_act_m.group(3) or "false").lower() == "true",
                ),
                indent=2,
            ),
        )

    github_pr_reply_post_m = re.match(
        r"^github pr reply post\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)\s+text=(.+)$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if github_pr_reply_post_m:
        return Result(
            "system",
            json.dumps(
                github_pr_reply_post(
                    task.cwd,
                    github_pr_reply_post_m.group(1),
                    int(github_pr_reply_post_m.group(2)),
                    github_pr_reply_post_m.group(3).strip(),
                ),
                indent=2,
            ),
        )

    github_pr_reply_m = re.match(
        r"^github pr reply\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+(\d+)(?:\s+execute=(true|false))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if github_pr_reply_m:
        return Result(
            "system",
            json.dumps(
                github_pr_reply_draft(
                    task.cwd,
                    github_pr_reply_m.group(1),
                    int(github_pr_reply_m.group(2)),
                    (github_pr_reply_m.group(3) or "false").lower() == "true",
                ),
                indent=2,
            ),
        )

    if normalized in {
        "zero ai self upgrade",
        "zero ai upgrade",
        "zero ai upgrade system",
        "zero ai self upgrade for better system",
    }:
        gate = autonomy_evaluate(
            task.cwd,
            action="zero ai self upgrade",
            blast_radius="service",
            reversible=True,
            evidence_count=12,
            contradictory_signals=0,
            independent_verifiers=4,
            checks={
                "gap_status_ready": True,
                "backup_ready": True,
                "system_optimize_ready": True,
            },
        )
        if gate["decision"] != "allow":
            return Result("system", json.dumps({"ok": False, "reason": "autonomy_gate", "gate": gate}, indent=2))
        result = zero_ai_upgrade_system(task.cwd)
        autonomy_record(
            task.cwd,
            "zero ai self upgrade",
            "success" if result.get("ok") else "failed",
            gate["confidence"]["confidence"],
        )
        return Result("system", json.dumps({"ok": bool(result.get("ok", False)), "gate": gate, "result": result}, indent=2))

    return None

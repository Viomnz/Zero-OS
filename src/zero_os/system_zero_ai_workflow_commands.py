from __future__ import annotations

import json
import re

from zero_os.types import Result, Task
from zero_os.zero_ai_control_workflows import (
    zero_ai_control_workflow_browser_act,
    zero_ai_control_workflow_browser_open,
    zero_ai_control_workflow_install,
    zero_ai_control_workflow_recover,
    zero_ai_control_workflow_self_repair,
    zero_ai_control_workflows_refresh,
    zero_ai_control_workflows_status,
)


def handle_zero_ai_workflow_command(task: Task, raw: str, text: str) -> Result | None:
    normalized = text.strip()
    if normalized in {"zero ai control workflows status", "zero ai workflow status"}:
        return Result("system", json.dumps(zero_ai_control_workflows_status(task.cwd), indent=2))
    if normalized in {"zero ai control workflows refresh", "zero ai workflow refresh"}:
        return Result("system", json.dumps(zero_ai_control_workflows_refresh(task.cwd), indent=2))

    workflow_browser_open = re.match(r"^zero ai workflow browser open\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if workflow_browser_open:
        return Result(
            "system",
            json.dumps(
                zero_ai_control_workflow_browser_open(task.cwd, workflow_browser_open.group(1).strip().strip("\"'")),
                indent=2,
            ),
        )

    workflow_browser_act = re.match(
        r"^zero ai workflow browser act\s+url=(\S+)\s+action=([A-Za-z0-9_-]+)(?:\s+selector=(\S+))?(?:\s+value=(.+))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if workflow_browser_act:
        return Result(
            "system",
            json.dumps(
                zero_ai_control_workflow_browser_act(
                    task.cwd,
                    workflow_browser_act.group(1),
                    workflow_browser_act.group(2),
                    workflow_browser_act.group(3) or "",
                    workflow_browser_act.group(4) or "",
                ),
                indent=2,
            ),
        )

    workflow_install = re.match(
        r"^zero ai workflow install\s+([A-Za-z0-9._-]+)(?:\s+user=(\S+))?(?:\s+email=(\S+))?(?:\s+os=(\S+))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if workflow_install:
        return Result(
            "system",
            json.dumps(
                zero_ai_control_workflow_install(
                    task.cwd,
                    workflow_install.group(1),
                    user_id=workflow_install.group(2) or "local-user",
                    email=workflow_install.group(3) or "",
                    target_os=workflow_install.group(4) or "",
                ),
                indent=2,
            ),
        )

    workflow_recover = re.match(r"^zero ai workflow recover(?:\s+snapshot=(\S+))?$", raw.strip(), flags=re.IGNORECASE)
    if workflow_recover:
        return Result(
            "system",
            json.dumps(zero_ai_control_workflow_recover(task.cwd, workflow_recover.group(1) or "latest"), indent=2),
        )

    if normalized == "zero ai workflow self repair":
        return Result("system", json.dumps(zero_ai_control_workflow_self_repair(task.cwd), indent=2))

    return None

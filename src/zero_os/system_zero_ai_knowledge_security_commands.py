from __future__ import annotations

import json
import re

from zero_os.antivirus import (
    monitor_set as antivirus_monitor_set,
    monitor_status as antivirus_monitor_status,
    monitor_tick as antivirus_monitor_tick,
    policy_set as antivirus_policy_set,
    policy_status as antivirus_policy_status,
    quarantine_file as antivirus_quarantine_file,
    quarantine_list as antivirus_quarantine_list,
    quarantine_restore as antivirus_quarantine_restore,
    scan_target as antivirus_scan_target,
    suppression_add as antivirus_suppression_add,
    suppression_list as antivirus_suppression_list,
    suppression_remove as antivirus_suppression_remove,
    threat_feed_export_signed as antivirus_threat_feed_export_signed,
    threat_feed_import_signed as antivirus_threat_feed_import_signed,
    threat_feed_status as antivirus_threat_feed_status,
    threat_feed_update as antivirus_threat_feed_update,
)
from zero_os.antivirus_agent import antivirus_agent_status, run_antivirus_agent
from zero_os.knowledge_map import build_knowledge_index, knowledge_find, knowledge_status
from zero_os.smart_logic_governance import decide_false_positive, list_false_positive_reviews
from zero_os.types import Result, Task


def handle_zero_ai_knowledge_security_command(task: Task, raw: str, text: str) -> Result | None:
    normalized = text.strip()
    if normalized in {"zero ai knowledge build", "zero ai know everything"}:
        build_result = build_knowledge_index(task.cwd)
        return Result("system", json.dumps({"build": build_result, "status": knowledge_status(task.cwd)}, indent=2))

    if normalized == "zero ai knowledge status":
        return Result("system", json.dumps(knowledge_status(task.cwd), indent=2))

    knowledge_find_match = re.match(r"^zero ai knowledge find\s+(.+?)(?:\s+limit=(\d+))?$", raw.strip(), flags=re.IGNORECASE)
    if knowledge_find_match:
        return Result(
            "system",
            json.dumps(
                knowledge_find(
                    task.cwd,
                    knowledge_find_match.group(1).strip().strip("\"'"),
                    limit=int(knowledge_find_match.group(2) or "20"),
                ),
                indent=2,
            ),
        )

    false_positive_list_match = re.match(r"^false positive review list(?:\s+limit=(\d+))?$", normalized, flags=re.IGNORECASE)
    if false_positive_list_match:
        return Result("system", json.dumps(list_false_positive_reviews(task.cwd, limit=int(false_positive_list_match.group(1) or "100")), indent=2))

    false_positive_decide_match = re.match(
        r"^false positive review decide\s+index=(\d+)\s+verdict=(confirmed|false_positive)(?:\s+note=(.+))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if false_positive_decide_match:
        return Result(
            "system",
            json.dumps(
                decide_false_positive(
                    task.cwd,
                    int(false_positive_decide_match.group(1)),
                    false_positive_decide_match.group(2),
                    (false_positive_decide_match.group(3) or "").strip(),
                ),
                indent=2,
            ),
        )

    agent_run_match = re.match(
        r"^antivirus agent run(?:\s+(.+?))?(?:\s+auto_quarantine=(true|false|1|0|yes|no|on|off))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if agent_run_match:
        target = agent_run_match.group(1).strip().strip("\"'") if agent_run_match.group(1) else "."
        auto_quarantine = (agent_run_match.group(2) or "false").strip().lower() in {"1", "true", "yes", "on"}
        return Result("system", json.dumps(run_antivirus_agent(task.cwd, target=target, auto_quarantine=auto_quarantine), indent=2))

    if normalized == "antivirus agent status":
        return Result("system", json.dumps(antivirus_agent_status(task.cwd), indent=2))
    if normalized == "antivirus feed status":
        return Result("system", json.dumps(antivirus_threat_feed_status(task.cwd), indent=2))
    if normalized == "antivirus feed update":
        return Result("system", json.dumps(antivirus_threat_feed_update(task.cwd), indent=2))

    feed_export_match = re.match(r"^antivirus feed export signed\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if feed_export_match:
        return Result("system", json.dumps(antivirus_threat_feed_export_signed(task.cwd, feed_export_match.group(1).strip().strip("\"'")), indent=2))

    feed_import_match = re.match(r"^antivirus feed import signed\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if feed_import_match:
        return Result("system", json.dumps(antivirus_threat_feed_import_signed(task.cwd, feed_import_match.group(1).strip().strip("\"'")), indent=2))

    scan_match = re.match(r"^antivirus scan(?:\s+(.+))?$", raw.strip(), flags=re.IGNORECASE)
    if scan_match:
        return Result(
            "system",
            json.dumps(
                antivirus_scan_target(task.cwd, scan_match.group(1).strip().strip("\"'") if scan_match.group(1) else "."),
                indent=2,
            ),
        )

    if normalized == "antivirus quarantine list":
        return Result("system", json.dumps(antivirus_quarantine_list(task.cwd), indent=2))

    quarantine_match = re.match(r"^antivirus quarantine\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if quarantine_match:
        return Result(
            "system",
            json.dumps(antivirus_quarantine_file(task.cwd, quarantine_match.group(1).strip().strip("\"'"), reason="manual"), indent=2),
        )

    restore_match = re.match(r"^antivirus restore\s+([a-z0-9]+)$", normalized, flags=re.IGNORECASE)
    if restore_match:
        return Result("system", json.dumps(antivirus_quarantine_restore(task.cwd, restore_match.group(1)), indent=2))

    policy_match = re.match(r"^antivirus policy set\s+([a-z_]+)\s+(.+)$", raw.strip(), flags=re.IGNORECASE)
    if policy_match:
        try:
            updated = antivirus_policy_set(task.cwd, policy_match.group(1).strip(), policy_match.group(2).strip())
        except ValueError:
            return Result(
                "system",
                "supported policy keys: heuristic_threshold, auto_quarantine, max_files_per_scan, max_file_mb, archive_max_depth, archive_max_entries, restore_overwrite, response_mode",
            )
        return Result("system", json.dumps(updated, indent=2))

    if normalized == "antivirus policy show":
        return Result("system", json.dumps(antivirus_policy_status(task.cwd), indent=2))

    suppression_add_match = re.match(
        r"^antivirus suppression add\s+([A-Za-z0-9._-]+)(?:\s+path=(\S+))?(?:\s+hours=(\d+))?$",
        raw.strip(),
        flags=re.IGNORECASE,
    )
    if suppression_add_match:
        return Result(
            "system",
            json.dumps(
                antivirus_suppression_add(
                    task.cwd,
                    suppression_add_match.group(1),
                    suppression_add_match.group(2) or "",
                    int(suppression_add_match.group(3) or "24"),
                ),
                indent=2,
            ),
        )

    if normalized == "antivirus suppression list":
        return Result("system", json.dumps(antivirus_suppression_list(task.cwd), indent=2))

    suppression_remove_match = re.match(r"^antivirus suppression remove\s+([a-z0-9]+)$", normalized, flags=re.IGNORECASE)
    if suppression_remove_match:
        return Result("system", json.dumps(antivirus_suppression_remove(task.cwd, suppression_remove_match.group(1)), indent=2))

    monitor_on_match = re.match(r"^antivirus monitor on(?:\s+interval=(\d+))?$", normalized, flags=re.IGNORECASE)
    if monitor_on_match:
        return Result(
            "system",
            json.dumps(antivirus_monitor_set(task.cwd, True, int(monitor_on_match.group(1)) if monitor_on_match.group(1) else None), indent=2),
        )

    if normalized == "antivirus monitor off":
        return Result("system", json.dumps(antivirus_monitor_set(task.cwd, False), indent=2))
    if normalized == "antivirus monitor status":
        return Result("system", json.dumps(antivirus_monitor_status(task.cwd), indent=2))

    monitor_tick_match = re.match(r"^antivirus monitor tick(?:\s+(.+))?$", raw.strip(), flags=re.IGNORECASE)
    if monitor_tick_match:
        return Result(
            "system",
            json.dumps(
                antivirus_monitor_tick(
                    task.cwd,
                    monitor_tick_match.group(1).strip().strip("\"'") if monitor_tick_match.group(1) else ".",
                ),
                indent=2,
            ),
        )

    return None

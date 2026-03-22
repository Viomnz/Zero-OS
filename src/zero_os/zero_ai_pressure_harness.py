from __future__ import annotations

import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from zero_os.approval_workflow import decide as approval_decide, status as approval_status
from zero_os.task_planner import planner_feedback_status
from zero_os.task_executor import run_task, run_task_resume
from zero_os.unified_action_engine import execute_step


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "pressure_harness"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _latest_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "latest.json"


def _history_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "history.jsonl"


def _summary_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "latest.md"


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_history(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Zero AI Pressure Harness",
        "",
        f"- Generated UTC: {payload.get('generated_utc', '')}",
        f"- Status: {payload.get('status', 'unknown')}",
        f"- Overall score: {payload.get('overall_score', 0.0)}",
        f"- Grade: {payload.get('grade', 'F')}",
        f"- Passed: {payload.get('passed_count', 0)}/{payload.get('scenario_count', 0)}",
        f"- Failed: {payload.get('failed_count', 0)}",
        f"- Recommended action: {payload.get('recommended_action', '')}",
        "",
        "## Category Scores",
    ]
    for name, category in sorted(dict(payload.get("category_scores") or {}).items()):
        lines.append(
            f"- {name}: score={category.get('score', 0.0)} "
            f"passed={category.get('passed_count', 0)}/{category.get('scenario_count', 0)}"
        )
    lines.extend(["", "## Failure Taxonomy"])
    taxonomy = dict(payload.get("failure_taxonomy") or {})
    if taxonomy:
        for name, count in sorted(taxonomy.items()):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Scenarios"])
    for scenario in list(payload.get("scenarios") or []):
        status = "pass" if scenario.get("ok", False) else "fail"
        lines.append(f"- {scenario.get('name', 'scenario')}: {status} - {scenario.get('summary', '')}")
    planner = dict(payload.get("planner_feedback") or {})
    planner_summary = dict(planner.get("summary") or {})
    if planner_summary:
        lines.extend(["", "## Planner Feedback"])
        lines.append(f"- history_count: {planner_summary.get('history_count', 0)}")
        for route_name, route_metrics in sorted(dict(planner_summary.get("routes") or {}).items()):
            lines.append(
                f"- {route_name}: success={route_metrics.get('successful_completion_rate', 0.0)} "
                f"holds={route_metrics.get('contradiction_hold_rate', 0.0)} "
                f"target_drop={route_metrics.get('target_drop_rate', 0.0)}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _planner_feedback_block(cwd: str) -> dict[str, Any]:
    feedback = planner_feedback_status(cwd)
    summary = dict(feedback.get("summary") or {})
    routes = dict(summary.get("routes") or {})
    worst_route = ""
    worst_hold = -1.0
    worst_target_drop = -1.0
    for route_name, metrics in routes.items():
        contradiction_hold_rate = float(metrics.get("contradiction_hold_rate", 0.0) or 0.0)
        target_drop_rate = float(metrics.get("target_drop_rate", 0.0) or 0.0)
        combined = contradiction_hold_rate + target_drop_rate
        if combined > worst_hold + worst_target_drop:
            worst_hold = contradiction_hold_rate
            worst_target_drop = target_drop_rate
            worst_route = route_name
    highest_value_steps: list[str] = []
    if worst_route and (worst_hold > 0.0 or worst_target_drop > 0.0):
        highest_value_steps.append(
            f"Reduce planner drift on route `{worst_route}` by lowering contradiction holds and unbound-target drops before widening autonomy further."
        )
    elif int(summary.get("history_count", 0) or 0) == 0:
        highest_value_steps.append("Run more real planner-driven tasks so Zero AI has route-quality evidence, not only pressure scenarios.")
    return {
        "history_count": int(summary.get("history_count", 0) or 0),
        "routes": routes,
        "worst_route": worst_route,
        "worst_contradiction_hold_rate": round(max(0.0, worst_hold), 3),
        "worst_target_drop_rate": round(max(0.0, worst_target_drop), 3),
        "highest_value_steps": highest_value_steps,
        "path": str(feedback.get("path", "")),
        "summary": summary,
    }


def _seed_workspace(base: Path) -> None:
    (base / ".zero_os").mkdir(parents=True, exist_ok=True)
    (base / ".zero_os" / "state.json").write_text("{}\n", encoding="utf-8")
    (base / "README.md").write_text("# Zero AI Pressure Sandbox\n", encoding="utf-8")
    (base / "src").mkdir(parents=True, exist_ok=True)
    (base / "src" / "sandbox.py").write_text("VALUE = 1\n", encoding="utf-8")


def _scenario(name: str, category: str, ok: bool, summary: str, *, failure_code: str = "", details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "ok": bool(ok),
        "summary": summary,
        "failure_code": failure_code,
        "details": dict(details or {}),
    }


def _extract_approval_item(payload: dict[str, Any]) -> dict[str, Any]:
    approval = dict(payload.get("approval") or {})
    nested = dict(approval.get("approval") or {})
    return nested or approval


def _browser_action_single_use() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zero_pressure_browser_") as tempdir:
        base = Path(tempdir)
        _seed_workspace(base)
        run_id = str(uuid4())
        step = {"kind": "browser_action", "target": {"url": "https://example.com", "action": "click", "selector": "body"}}

        first = execute_step(str(base), step, run_id=run_id)
        if first.get("ok", False) or str(first.get("reason", "")) != "approval_required":
            return _scenario(
                "browser_action_single_use",
                "approval_flow",
                False,
                "Browser action did not request approval on the first attempt.",
                failure_code="approval_not_requested",
                details={"first": first},
            )

        approval = _extract_approval_item(first)
        decision = approval_decide(str(base), str(approval.get("id", "")), True)
        if not decision.get("ok", False):
            return _scenario(
                "browser_action_single_use",
                "approval_flow",
                False,
                "Approved browser action could not be recorded.",
                failure_code="approval_handoff_failed",
                details={"decision": decision},
            )

        second = execute_step(str(base), step, run_id=run_id)
        action = dict(second.get("result", {}).get("action") or {})
        if not second.get("ok", False):
            return _scenario(
                "browser_action_single_use",
                "approval_flow",
                False,
                "Approved browser action did not execute.",
                failure_code="approval_handoff_failed",
                details={"second": second},
            )
        if str(action.get("url", "")) != "https://example.com":
            return _scenario(
                "browser_action_single_use",
                "approval_flow",
                False,
                "Approved browser action lost its page target.",
                failure_code="wrong_action_target",
                details={"second": second},
            )

        third = execute_step(str(base), step, run_id=run_id)
        approvals = approval_status(str(base))
        if third.get("ok", False):
            return _scenario(
                "browser_action_single_use",
                "approval_flow",
                False,
                "A consumed browser approval was reused.",
                failure_code="approval_reuse_allowed",
                details={"third": third, "approvals": approvals},
            )
        if str(third.get("reason", "")) != "approval_required":
            return _scenario(
                "browser_action_single_use",
                "approval_flow",
                False,
                "Browser action did not fall back to approval after the first execution.",
                failure_code="approval_reuse_allowed",
                details={"third": third, "approvals": approvals},
            )

        return _scenario(
            "browser_action_single_use",
            "approval_flow",
            True,
            "Browser actions require exact approval once, execute correctly, and request fresh approval after use.",
            details={"approval_count": approvals.get("count", 0)},
        )


def _browser_action_target_scope() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zero_pressure_scope_") as tempdir:
        base = Path(tempdir)
        _seed_workspace(base)
        run_id = str(uuid4())
        first_step = {"kind": "browser_action", "target": {"url": "https://example.com", "action": "click", "selector": "body"}}
        second_step = {"kind": "browser_action", "target": {"url": "https://example.org", "action": "click", "selector": "body"}}

        first = execute_step(str(base), first_step, run_id=run_id)
        approval = _extract_approval_item(first)
        approval_decide(str(base), str(approval.get("id", "")), True)
        second = execute_step(str(base), second_step, run_id=run_id)
        second_approval = _extract_approval_item(second)

        if second.get("ok", False):
            return _scenario(
                "browser_action_target_scope",
                "approval_flow",
                False,
                "An approval for one browser target leaked into a different target.",
                failure_code="approval_scope_leak",
                details={"second": second},
            )
        if str(second.get("reason", "")) != "approval_required":
            return _scenario(
                "browser_action_target_scope",
                "approval_flow",
                False,
                "Target-scoped browser approval did not force a fresh approval request.",
                failure_code="approval_scope_leak",
                details={"second": second},
            )
        if str(((second_approval.get("payload") or {}).get("target") or {}).get("url", "")) != "https://example.org":
            return _scenario(
                "browser_action_target_scope",
                "approval_flow",
                False,
                "The new approval request lost the requested browser target.",
                failure_code="wrong_action_target",
                details={"second": second},
            )

        return _scenario(
            "browser_action_target_scope",
            "approval_flow",
            True,
            "Browser approvals stay bound to the exact requested target.",
        )


def _self_repair_approval_handoff() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zero_pressure_self_repair_") as tempdir:
        base = Path(tempdir)
        _seed_workspace(base)

        first = run_task(str(base), "self repair runtime")
        approvals_before = approval_status(str(base))
        if first.get("ok", False):
            return _scenario(
                "self_repair_approval_handoff",
                "approval_flow",
                False,
                "Self repair executed without the expected approval gate.",
                failure_code="approval_not_requested",
                details={"first": first},
            )
        approval = approvals_before.get("items", [])[-1] if approvals_before.get("items") else {}
        if str(approval.get("action", "")) != "self_repair":
            return _scenario(
                "self_repair_approval_handoff",
                "approval_flow",
                False,
                "Self repair did not create a matching approval record.",
                failure_code="approval_not_requested",
                details={"first": first, "approvals": approvals_before},
            )

        approval_decide(str(base), str(approval.get("id", "")), True)
        resumed = run_task_resume(str(base))
        approvals_after = approval_status(str(base))
        self_repair_results = [item for item in resumed.get("results", []) if str(item.get("kind", "")) == "self_repair"]

        if not self_repair_results:
            return _scenario(
                "self_repair_approval_handoff",
                "approval_flow",
                False,
                "Self repair did not re-enter execution after approval.",
                failure_code="approval_handoff_failed",
                details={"resumed": resumed},
            )
        if any(str(item.get("reason", "")) == "approval_required" for item in self_repair_results):
            return _scenario(
                "self_repair_approval_handoff",
                "approval_flow",
                False,
                "Self repair stayed trapped in an approval loop after approval.",
                failure_code="approval_loop_persists",
                details={"resumed": resumed},
            )
        if approvals_after.get("count", 0) != approvals_before.get("count", 0):
            return _scenario(
                "self_repair_approval_handoff",
                "approval_flow",
                False,
                "Self repair created duplicate approval requests after approval.",
                failure_code="duplicate_approval_request",
                details={"before": approvals_before, "after": approvals_after, "resumed": resumed},
            )

        return _scenario(
            "self_repair_approval_handoff",
            "approval_flow",
            True,
            "Approved self repair moves into execution or autonomy review instead of requesting approval again.",
            details={"run_ok": resumed.get("ok", False), "final_reason": resumed.get("results", [])[-1].get("reason", "") if resumed.get("results") else ""},
        )


def _contradiction_hold_when_self_conflict() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zero_pressure_contradiction_") as tempdir:
        base = Path(tempdir)
        _seed_workspace(base)
        runtime_dir = base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "zero_ai_self_continuity.json").write_text(
            json.dumps(
                {
                    "continuity": {"same_system": True, "continuity_score": 82.0},
                    "contradiction_detection": {
                        "has_contradiction": True,
                        "issues": ["self_model_missing_no_contradiction_constraint"],
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        out = run_task(str(base), "check system status")
        gate = dict(out.get("contradiction_gate") or {})
        if out.get("ok", False) or str(gate.get("decision", "")) != "hold":
            return _scenario(
                "contradiction_hold_when_self_conflict",
                "contradiction_handling",
                False,
                "Contradiction gate did not hold output when the self model was contradictory.",
                failure_code="contradiction_gate_missed",
                details={"out": out},
            )
        return _scenario(
            "contradiction_hold_when_self_conflict",
            "contradiction_handling",
            True,
            "Contradiction gate holds output when self continuity becomes contradictory.",
        )


def _smart_workspace_routing() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zero_pressure_workspace_") as tempdir:
        base = Path(tempdir)
        _seed_workspace(base)
        out = run_task(str(base), "smart workspace")
        step_kinds = [str(step.get("kind", "")) for step in list(out.get("plan", {}).get("steps", []))]
        if "smart_workspace" not in step_kinds:
            return _scenario(
                "smart_workspace_routing",
                "routing",
                False,
                "Smart workspace requests were routed to the wrong lane.",
                failure_code="route_misclassified",
                details={"plan": out.get("plan", {})},
            )
        if not out.get("ok", False):
            return _scenario(
                "smart_workspace_routing",
                "routing",
                False,
                "Smart workspace route failed to complete.",
                failure_code="task_failed",
                details={"out": out},
            )
        return _scenario(
            "smart_workspace_routing",
            "routing",
            True,
            "Smart workspace requests route into the workspace lane cleanly.",
        )


def _flow_monitor_routing() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zero_pressure_flow_") as tempdir:
        base = Path(tempdir)
        _seed_workspace(base)
        out = run_task(str(base), "find contradiction bugs errors virus anything")
        step_kinds = [str(step.get("kind", "")) for step in list(out.get("plan", {}).get("steps", []))]
        if "flow_monitor" not in step_kinds:
            return _scenario(
                "flow_monitor_routing",
                "routing",
                False,
                "Flow-monitor requests were routed to the wrong lane.",
                failure_code="route_misclassified",
                details={"plan": out.get("plan", {})},
            )
        if not out.get("ok", False):
            return _scenario(
                "flow_monitor_routing",
                "routing",
                False,
                "Flow-monitor route failed to complete.",
                failure_code="task_failed",
                details={"out": out},
            )
        return _scenario(
            "flow_monitor_routing",
            "routing",
            True,
            "Flow-monitor requests route into the unified integrity lane cleanly.",
        )


def _status_task_completion() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zero_pressure_status_") as tempdir:
        base = Path(tempdir)
        _seed_workspace(base)
        out = run_task(str(base), "check system status")
        step_kinds = [str(step.get("kind", "")) for step in list(out.get("plan", {}).get("steps", []))]
        if "system_status" not in step_kinds:
            return _scenario(
                "status_task_completion",
                "task_completion",
                False,
                "System-status requests lost their typed status step.",
                failure_code="route_misclassified",
                details={"plan": out.get("plan", {})},
            )
        if not out.get("ok", False):
            return _scenario(
                "status_task_completion",
                "task_completion",
                False,
                "System-status request failed under pressure.",
                failure_code="task_failed",
                details={"out": out},
            )
        return _scenario(
            "status_task_completion",
            "task_completion",
            True,
            "Basic system-status tasks complete successfully under pressure.",
        )


_SCENARIOS = (
    _browser_action_single_use,
    _browser_action_target_scope,
    _self_repair_approval_handoff,
    _contradiction_hold_when_self_conflict,
    _smart_workspace_routing,
    _flow_monitor_routing,
    _status_task_completion,
)


def _grade(score: float) -> str:
    if score >= 95.0:
        return "A"
    if score >= 85.0:
        return "B"
    if score >= 75.0:
        return "C"
    if score >= 65.0:
        return "D"
    return "F"


def _top_failure(failure_taxonomy: dict[str, int]) -> str:
    if not failure_taxonomy:
        return ""
    return sorted(failure_taxonomy.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _recommended_action(failure_taxonomy: dict[str, int]) -> str:
    top = _top_failure(failure_taxonomy)
    if top == "approval_not_requested":
        return "Restore explicit approval requirements before any broader autonomy expansion."
    if top in {"approval_handoff_failed", "approval_loop_persists", "duplicate_approval_request"}:
        return "Tighten approval-to-execution handoff so approved actions execute once and never loop."
    if top in {"approval_reuse_allowed", "approval_scope_leak", "wrong_action_target"}:
        return "Keep approvals bound to exact targets and one-shot execution."
    if top == "contradiction_gate_missed":
        return "Fix contradiction gating before trusting broader reasoning or autonomy."
    if top == "route_misclassified":
        return "Repair planner routing so requests enter the correct typed lane under pressure."
    if top == "task_failed":
        return "Stabilize the failing task contract before expanding feature surface."
    return "Run the pressure harness regularly and feed real incidents back into it."


def _category_scores(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for scenario in scenarios:
        buckets.setdefault(str(scenario.get("category", "general")), []).append(scenario)
    scores: dict[str, Any] = {}
    for name, items in buckets.items():
        passed = sum(1 for item in items if item.get("ok", False))
        total = len(items)
        scores[name] = {
            "scenario_count": total,
            "passed_count": passed,
            "failed_count": total - passed,
            "score": round((passed / max(1, total)) * 100.0, 2),
        }
    return scores


def pressure_harness_status(cwd: str) -> dict[str, Any]:
    planner_feedback = _planner_feedback_block(cwd)
    latest = _latest_path(cwd)
    if not latest.exists():
        return {
            "ok": True,
            "missing": True,
            "active": False,
            "ready": True,
            "status": "missing",
            "scenario_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "overall_score": 0.0,
            "grade": "F",
            "category_scores": {},
            "failure_taxonomy": {},
            "top_failure_code": "",
            "recommended_action": "Run `zero ai pressure run` to create a real survivability baseline.",
            "highest_value_steps": [
                "Run `zero ai pressure run` to create a real survivability baseline.",
            ],
            "planner_feedback": planner_feedback,
            "path": str(latest),
            "history_path": str(_history_path(cwd)),
            "summary_path": str(_summary_path(cwd)),
        }
    payload = _load_json(latest, {"ok": True})
    payload.setdefault("ok", True)
    payload.setdefault("missing", False)
    payload.setdefault("active", True)
    payload.setdefault("ready", True)
    payload.setdefault("path", str(latest))
    payload.setdefault("history_path", str(_history_path(cwd)))
    payload.setdefault("summary_path", str(_summary_path(cwd)))
    payload.setdefault(
        "highest_value_steps",
        [str(payload.get("recommended_action", "Run the pressure harness regularly and feed real incidents back into it."))],
    )
    payload["planner_feedback"] = planner_feedback
    if list(planner_feedback.get("highest_value_steps", [])):
        payload["highest_value_steps"] = list(payload.get("highest_value_steps", [])) + list(planner_feedback.get("highest_value_steps", []))
    return payload


def pressure_harness_run(cwd: str) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    for scenario in _SCENARIOS:
        try:
            scenarios.append(scenario())
        except Exception as exc:
            scenarios.append(
                _scenario(
                    scenario.__name__.lstrip("_"),
                    "general",
                    False,
                    "Scenario raised an unexpected exception.",
                    failure_code="scenario_exception",
                    details={"error": str(exc)},
                )
            )

    scenario_count = len(scenarios)
    passed_count = sum(1 for item in scenarios if item.get("ok", False))
    failed_count = scenario_count - passed_count
    overall_score = round((passed_count / max(1, scenario_count)) * 100.0, 2)
    failure_taxonomy = dict(sorted(Counter(item["failure_code"] for item in scenarios if item.get("failure_code")).items()))
    top_failure_code = _top_failure(failure_taxonomy)
    recommended_action = _recommended_action(failure_taxonomy)
    status = "pass" if failed_count == 0 else "attention"
    category_scores = _category_scores(scenarios)
    planner_feedback = _planner_feedback_block(cwd)

    payload = {
        "ok": True,
        "missing": False,
        "active": True,
        "ready": True,
        "status": status,
        "generated_utc": _utc_now(),
        "scenario_count": scenario_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "overall_score": overall_score,
        "grade": _grade(overall_score),
        "category_scores": category_scores,
        "failure_taxonomy": failure_taxonomy,
        "top_failure_code": top_failure_code,
        "recommended_action": recommended_action,
        "highest_value_steps": [recommended_action] + list(planner_feedback.get("highest_value_steps", [])),
        "planner_feedback": planner_feedback,
        "scenarios": scenarios,
        "summary": {
            "scenario_count": scenario_count,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "overall_score": overall_score,
            "grade": _grade(overall_score),
            "top_failure_code": top_failure_code,
        },
        "path": str(_latest_path(cwd)),
        "history_path": str(_history_path(cwd)),
        "summary_path": str(_summary_path(cwd)),
    }
    _save_json(_latest_path(cwd), payload)
    _append_history(
        _history_path(cwd),
        {
            "generated_utc": payload["generated_utc"],
            "status": payload["status"],
            "overall_score": payload["overall_score"],
            "passed_count": passed_count,
            "failed_count": failed_count,
            "top_failure_code": top_failure_code,
        },
    )
    _write_summary(_summary_path(cwd), payload)
    return payload


def pressure_harness_refresh(cwd: str) -> dict[str, Any]:
    return pressure_harness_run(cwd)

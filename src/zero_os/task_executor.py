from __future__ import annotations

from uuid import uuid4

from zero_os.contradiction_engine import review_run, select_stable_branch
from zero_os.playbook_memory import remember
from zero_os.result_synthesizer import synthesize_result
from zero_os.task_memory import latest_resumable, save_task_run, status as task_memory_status
from zero_os.task_planner import build_candidate_plans, build_plan, record_planner_outcome
from zero_os.unified_action_engine import execute_step


def _default_branch_selection(plan: dict) -> dict:
    branch = dict(plan.get("branch") or {"id": "primary", "source": "direct_plan"})
    return {
        "selected_plan": plan,
        "selected_branch": {
            "plan": plan,
            "branch": branch,
            "evidence": dict(plan.get("evidence") or {}),
            "memory_context": dict(plan.get("memory_context") or {}),
        },
        "candidate_count": 1 + int(plan.get("discarded_count", 0) or 0),
        "discarded_count": int(plan.get("discarded_count", 0) or 0),
        "discarded_branches": list(plan.get("discarded_branches", [])),
        "blocked_branch": None,
    }


def _execute_plan(
    cwd: str,
    request: str,
    plan: dict,
    *,
    run_id: str,
    branch_selection: dict | None = None,
    start_index: int = 0,
    existing_results: list[dict] | None = None,
) -> dict:
    results = list(existing_results or [])
    plan_context = {
        "planner_confidence": float(plan.get("planner_confidence", 0.0) or 0.0),
        "risk_level": str(plan.get("risk_level", "low") or "low"),
        "ambiguity_flags": list(plan.get("ambiguity_flags", [])),
    }
    for step in plan.get("steps", [])[start_index:]:
        result = execute_step(cwd, step, run_id=run_id, plan_context=plan_context)
        results.append(result)
        if not result.get("ok", False):
            break
        if step.get("kind") == "autonomy_gate" and result.get("result", {}).get("decision") == "hold_for_review":
            break

    contradiction_gate = review_run(cwd, request, plan, results, run_ok=all(item.get("ok", False) for item in results))
    autonomy_hold = any(
        item.get("kind") == "autonomy_gate" and str((item.get("result") or {}).get("decision", "")) == "hold_for_review"
        for item in results
    )
    overall_ok = all(item.get("ok", False) for item in results) and not autonomy_hold and contradiction_gate.get("decision") == "allow"
    out = {
        "ok": overall_ok,
        "run_id": run_id,
        "request": request,
        "plan": plan,
        "results": results,
        "contradiction_gate": contradiction_gate,
        "branch_selection": branch_selection or _default_branch_selection(plan),
    }
    out["response"] = synthesize_result(out)
    remember(cwd, str(plan.get("intent", {}).get("intent", "observe")), plan)
    save_task_run(cwd, request, out)
    out["planner_feedback"] = record_planner_outcome(cwd, request, branch_selection or _default_branch_selection(plan), out)
    out["task_memory"] = task_memory_status(cwd)
    return out


def run_task(cwd: str, request: str) -> dict:
    candidate_bundle = build_candidate_plans(request, cwd)
    selection = select_stable_branch(cwd, request, list(candidate_bundle.get("candidates", [])))
    plan = dict(selection.get("selected_plan") or {})
    if not plan:
        contradiction_gate = dict((selection.get("blocked_branch") or {}))
        if not contradiction_gate:
            contradiction_gate = review_run(cwd, request, build_plan(request, cwd), [], run_ok=False)
        out = {
            "ok": False,
            "run_id": str(uuid4()),
            "request": request,
            "plan": {},
            "results": [],
            "contradiction_gate": contradiction_gate,
            "branch_selection": selection,
        }
        out["response"] = synthesize_result(out)
        save_task_run(cwd, request, out)
        out["planner_feedback"] = record_planner_outcome(cwd, request, selection, out)
        out["task_memory"] = task_memory_status(cwd)
        return out
    return _execute_plan(cwd, request, plan, run_id=str(uuid4()), branch_selection=selection)


def run_task_resume(cwd: str) -> dict:
    resumable = latest_resumable(cwd)
    if not resumable.get("ok", False):
        return {"ok": False, "reason": "no resumable task"}
    task = resumable["task"]
    completed_steps = int(task.get("completed_steps", 0))
    return _execute_plan(
        cwd,
        str(task.get("request", "")),
        dict(task.get("plan", {})),
        run_id=str(task.get("run_id", "")),
        branch_selection=dict(task.get("branch_selection", {}) or _default_branch_selection(dict(task.get("plan", {})))),
        start_index=int(task.get("resume_from", 0)),
        existing_results=list(task.get("results", []))[:completed_steps],
    )

from __future__ import annotations

from zero_os.contradiction_engine import select_stable_branch
from zero_os.playbook_memory import remember
from zero_os.result_synthesizer import synthesize_result
from zero_os.task_memory import latest_resumable, save_task_run, status as task_memory_status
from zero_os.task_planner import build_candidate_plans, build_plan
from zero_os.unified_action_engine import execute_step


def _execute_plan(cwd: str, request: str, plan: dict, start_index: int = 0, existing_results: list[dict] | None = None) -> dict:
    candidate_bundle = build_candidate_plans(request, cwd, base_plan=plan)
    branch_selection = select_stable_branch(cwd, request, list(candidate_bundle.get("candidates", [])))
    selected_plan = dict(branch_selection.get("selected_plan") or {})
    active_plan = selected_plan or dict(plan)
    if not selected_plan:
        gate = dict((branch_selection.get("blocked_branch") or {}).copy())
        response = {
            "summary": gate.get("boundary_summary", "contradiction gate: hold"),
            "ok": False,
            "contradiction_gate": gate,
        }
        out = {
            "ok": False,
            "request": request,
            "plan": active_plan,
            "results": list(existing_results or []),
            "response": response,
            "contradiction_gate": gate,
            "branch_selection": branch_selection,
        }
        remember(cwd, str(active_plan.get("intent", {}).get("intent", "observe")), active_plan)
        save_task_run(cwd, request, out)
        out["task_memory"] = task_memory_status(cwd)
        return out

    results = list(existing_results or [])
    for step in active_plan.get("steps", [])[start_index:]:
        result = execute_step(cwd, step)
        results.append(result)
        if not result.get("ok", False):
            break
        if step.get("kind") == "autonomy_gate" and result.get("result", {}).get("decision") == "hold_for_review":
            break
    run_ok = all(item.get("ok", False) for item in results)
    response = synthesize_result(
        {
            "cwd": cwd,
            "ok": run_ok,
            "request": request,
            "plan": active_plan,
            "results": results,
            "branch_selection": branch_selection,
        }
    )
    out = {
        "ok": bool(response.get("ok", False)),
        "request": request,
        "plan": active_plan,
        "results": results,
        "response": response,
        "contradiction_gate": dict(response.get("contradiction_gate") or {}),
        "branch_selection": branch_selection,
    }
    remember(cwd, str(active_plan.get("intent", {}).get("intent", "observe")), active_plan)
    save_task_run(cwd, request, out)
    out["task_memory"] = task_memory_status(cwd)
    return out


def run_task(cwd: str, request: str) -> dict:
    plan = build_plan(request, cwd)
    return _execute_plan(cwd, request, plan, start_index=0, existing_results=[])


def run_task_resume(cwd: str) -> dict:
    resumable = latest_resumable(cwd)
    if not resumable.get("ok", False):
        return {"ok": False, "reason": "no resumable task"}
    task = resumable["task"]
    return _execute_plan(
        cwd,
        str(task.get("request", "")),
        dict(task.get("plan", {})),
        start_index=int(task.get("resume_from", 0)),
        existing_results=list(task.get("results", [])),
    )

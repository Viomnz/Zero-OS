from __future__ import annotations

from zero_os.playbook_memory import remember
from zero_os.result_synthesizer import synthesize_result
from zero_os.task_memory import latest_resumable, save_task_run, status as task_memory_status
from zero_os.task_planner import build_plan
from zero_os.unified_action_engine import execute_step


def _execute_plan(cwd: str, request: str, plan: dict, start_index: int = 0, existing_results: list[dict] | None = None) -> dict:
    results = list(existing_results or [])
    for step in plan.get("steps", [])[start_index:]:
        result = execute_step(cwd, step)
        results.append(result)
        if not result.get("ok", False):
            break
        if step.get("kind") == "autonomy_gate" and result.get("result", {}).get("decision") == "hold_for_review":
            break
    out = {
        "ok": all(item.get("ok", False) for item in results),
        "request": request,
        "plan": plan,
        "results": results,
        "response": synthesize_result({"ok": all(item.get("ok", False) for item in results), "results": results}),
    }
    remember(cwd, str(plan.get("intent", {}).get("intent", "observe")), plan)
    save_task_run(cwd, request, out)
    out["task_memory"] = task_memory_status(cwd)
    return out


def run_task(cwd: str, request: str) -> dict:
    plan = build_plan(request)
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

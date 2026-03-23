from __future__ import annotations

from uuid import uuid4

from zero_os.contradiction_engine import review_run, select_stable_branch
from zero_os.playbook_memory import remember
from zero_os.result_synthesizer import synthesize_result
from zero_os.self_derivation_engine import record_strategy_outcome, survivor_history_score
from zero_os.task_memory import latest_resumable, save_task_run, status as task_memory_status
from zero_os.task_planner import build_candidate_plans, build_plan, record_planner_outcome
from zero_os.unified_action_engine import execute_step


def _result_allows_progress(result: dict) -> bool:
    return bool(
        result.get("ok", False)
        or result.get("handled_by_fallback", False)
        or result.get("skipped", False)
    )


def _step_failure_aliases(step: dict) -> set[str]:
    kind = str(step.get("kind", "")).strip().lower()
    aliases = {kind}
    browser_target = dict(step.get("target") or {}) if isinstance(step.get("target"), dict) else {}
    kind_map = {
        "browser_open": {"open", "browser", "browser_open"},
        "browser_action": {str(browser_target.get("action", "")).strip().lower() or "click", "browser_action"},
        "cloud_deploy": {"deploy", "cloud_deploy"},
        "cloud_target_set": {"configure", "cloud_target_set"},
        "github_issue_act": {"issue", "act", "github_issue_act"},
        "github_pr_act": {"pr", "act", "github_pr_act"},
        "recover": {"recover", "recovery"},
        "self_repair": {"repair", "self_repair", "fix"},
        "store_install": {"install", "store_install"},
        "highway_dispatch": {"show", "read", "inspect", "command"},
    }
    aliases.update({item for item in kind_map.get(kind, set()) if item})
    return {item for item in aliases if item}


def _matching_conditional_indexes(steps: list[dict], failed_index: int) -> list[int]:
    failed_step = dict(steps[failed_index] or {})
    failed_subgoal = str(failed_step.get("decomposition_subgoal_id", "") or failed_step.get("subgoal_id", ""))
    failed_aliases = _step_failure_aliases(failed_step)
    matches: list[int] = []
    for index in range(failed_index + 1, len(steps)):
        candidate = dict(steps[index] or {})
        if str(candidate.get("conditional_execution_mode", "always")) != "on_failure":
            continue
        depends_on = [str(item) for item in list(candidate.get("decomposition_depends_on", [])) if str(item)]
        if failed_subgoal and failed_subgoal in depends_on:
            matches.append(index)
            continue
        trigger_text = str(candidate.get("condition_trigger_text", "")).strip().lower()
        if trigger_text and any(alias in trigger_text for alias in failed_aliases):
            matches.append(index)
            continue
        trigger_hints = {str(item).strip().lower() for item in list(candidate.get("condition_trigger_hints", [])) if str(item).strip()}
        if trigger_hints & failed_aliases:
            matches.append(index)
    return matches


def _result_verification_succeeded(result: dict) -> bool:
    if not bool(result.get("ok", False)):
        return False
    kind = str(result.get("kind", "")).strip()
    payload = dict(result.get("result") or {})
    if kind == "web_verify":
        return bool(payload.get("verified", False))
    return True


def _matching_outcome_indexes(steps: list[dict], source_index: int, result: dict, *, outcome_mode: str) -> list[int]:
    source_step = dict(steps[source_index] or {})
    source_subgoal = str(source_step.get("decomposition_subgoal_id", "") or source_step.get("subgoal_id", ""))
    source_aliases = _step_failure_aliases(source_step)
    matches: list[int] = []
    for index in range(source_index + 1, len(steps)):
        candidate = dict(steps[index] or {})
        if str(candidate.get("conditional_execution_mode", "always")) != outcome_mode:
            continue
        depends_on = [str(item) for item in list(candidate.get("decomposition_depends_on", [])) if str(item)]
        if source_subgoal and source_subgoal in depends_on:
            matches.append(index)
            continue
        trigger_text = str(candidate.get("condition_trigger_text", "")).strip().lower()
        if trigger_text and any(alias in trigger_text for alias in source_aliases):
            matches.append(index)
            continue
        trigger_hints = {str(item).strip().lower() for item in list(candidate.get("condition_trigger_hints", [])) if str(item).strip()}
        if trigger_hints & source_aliases:
            matches.append(index)
    return matches


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
    steps = list(plan.get("steps", []))
    executed_conditional_indexes: set[int] = set()
    plan_context = {
        "planner_confidence": float(plan.get("planner_confidence", 0.0) or 0.0),
        "risk_level": str(plan.get("risk_level", "low") or "low"),
        "ambiguity_flags": list(plan.get("ambiguity_flags", [])),
        "execution_mode": str(plan.get("execution_mode", "normal") or "normal"),
        "smart_strategy": str((plan.get("smart_planner") or {}).get("strategy", "") or ""),
        "planner_precheck": dict(plan.get("planner_precheck") or {}),
    }
    for step_index in range(start_index, len(steps)):
        if step_index in executed_conditional_indexes:
            continue
        step = dict(steps[step_index] or {})
        conditional_mode = str(step.get("conditional_execution_mode", "always"))
        if conditional_mode in {"on_failure", "on_success", "on_verified"}:
            results.append(
                {
                    "ok": True,
                    "kind": str(step.get("kind", "step")),
                    "skipped": True,
                    "reason": "conditional_not_triggered",
                    "condition_type": conditional_mode,
                }
            )
            continue
        result = execute_step(cwd, step, run_id=run_id, plan_context=plan_context)
        results.append(result)
        if not result.get("ok", False):
            fallback_indexes = _matching_conditional_indexes(steps, step_index)
            if fallback_indexes:
                result["handled_by_fallback"] = True
                result["fallback_branch_triggered"] = True
                result["fallback_step_count"] = len(fallback_indexes)
                fallback_failed = False
                for fallback_index in fallback_indexes:
                    executed_conditional_indexes.add(fallback_index)
                    fallback_step = dict(steps[fallback_index] or {})
                    fallback_result = execute_step(cwd, fallback_step, run_id=run_id, plan_context=plan_context)
                    fallback_result["conditional_triggered_by"] = str(step.get("kind", ""))
                    fallback_result["conditional_source_subgoal"] = str(step.get("decomposition_subgoal_id", "") or step.get("subgoal_id", ""))
                    results.append(fallback_result)
                    if not _result_allows_progress(fallback_result):
                        fallback_failed = True
                        break
                if not fallback_failed:
                    continue
            break
        success_indexes = _matching_outcome_indexes(steps, step_index, result, outcome_mode="on_success")
        verified_indexes = _matching_outcome_indexes(steps, step_index, result, outcome_mode="on_verified")
        triggered_outcome_indexes = list(success_indexes)
        if verified_indexes and _result_verification_succeeded(result):
            triggered_outcome_indexes.extend(verified_indexes)
        if triggered_outcome_indexes:
            for conditional_index in triggered_outcome_indexes:
                if conditional_index in executed_conditional_indexes:
                    continue
                executed_conditional_indexes.add(conditional_index)
                conditional_step = dict(steps[conditional_index] or {})
                conditional_result = execute_step(cwd, conditional_step, run_id=run_id, plan_context=plan_context)
                conditional_result["conditional_triggered_by"] = str(step.get("kind", ""))
                conditional_result["conditional_source_subgoal"] = str(step.get("decomposition_subgoal_id", "") or step.get("subgoal_id", ""))
                conditional_result["condition_type"] = str(conditional_step.get("conditional_execution_mode", "always"))
                results.append(conditional_result)
                if not _result_allows_progress(conditional_result):
                    break
        if step.get("kind") == "autonomy_gate" and result.get("result", {}).get("decision") == "hold_for_review":
            break

    contradiction_gate = review_run(cwd, request, plan, results, run_ok=all(_result_allows_progress(item) for item in results))
    autonomy_hold = any(
        item.get("kind") == "autonomy_gate" and str((item.get("result") or {}).get("decision", "")) == "hold_for_review"
        for item in results
    )
    overall_ok = all(_result_allows_progress(item) for item in results) and not autonomy_hold and contradiction_gate.get("decision") == "allow"
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


def _count_completed_steps(results: list[dict]) -> int:
    completed = 0
    for item in results:
        if not _result_allows_progress(item):
            break
        completed += 1
    return completed


def _replan_trigger(out: dict) -> str:
    contradiction_gate = dict(out.get("contradiction_gate") or {})
    if str(contradiction_gate.get("decision", "")) == "hold":
        return "contradiction_hold"
    results = list(out.get("results", []))
    if not results:
        return "empty_results"
    last = dict(results[-1] or {})
    reason = str(last.get("reason", "")).strip()
    if reason == "approval_required":
        return ""
    if last.get("kind") == "autonomy_gate" and str((last.get("result") or {}).get("decision", "")) == "hold_for_review":
        return ""
    if reason in {"autonomy_gate", "policy_denied", "policy_observe_only"}:
        return ""
    if not bool(last.get("ok", False)):
        return reason or "step_failure"
    return ""


def _candidate_replan_sort_key(review: dict) -> tuple:
    plan = dict(review.get("plan") or {})
    branch = dict(plan.get("branch") or {})
    branch_id = str(branch.get("id", ""))
    preferred_branch_ids = {"conservative_execution", "minimal_safe", "observation_only", "verification_first", "evidence_first"}
    steps = list(plan.get("steps", []))
    mutating_count = sum(1 for step in steps if bool(step.get("mutation_requested_explicitly", False)))
    survivor_history = dict(review.get("survivor_history") or {})
    return (
        1 if branch_id in preferred_branch_ids else 0,
        1 if str(plan.get("execution_mode", "")) == "safe" else 0 if str(plan.get("execution_mode", "")) == "deliberate" else -1,
        float(plan.get("derivation_survival_score", 0.0) or 0.0),
        float(survivor_history.get("score", 0.0) or 0.0),
        -mutating_count,
        float(plan.get("planner_confidence", 0.0) or 0.0),
        float(dict(plan.get("target_coverage") or {}).get("coverage_ratio", 0.0) or 0.0),
    )


def _alternate_branch_selection(selection: dict, review: dict) -> dict:
    discarded = [item for item in list(selection.get("reviews", [])) if item is not review]
    return {
        "ok": True,
        "candidate_count": int(selection.get("candidate_count", len(list(selection.get("reviews", [])))) or 0),
        "selected_branch": review,
        "selected_plan": dict(review.get("plan") or {}),
        "discarded_branches": discarded,
        "discarded_count": len(discarded),
        "blocked_branch": None,
        "reviews": list(selection.get("reviews", [])),
    }


def _should_prefer_replan(original_out: dict, replanned_out: dict) -> bool:
    if replanned_out.get("ok", False) and not original_out.get("ok", False):
        return True
    original_completed = _count_completed_steps(list(original_out.get("results", [])))
    replanned_completed = _count_completed_steps(list(replanned_out.get("results", [])))
    if replanned_completed > original_completed:
        return True
    original_contradictions = int(dict(original_out.get("contradiction_gate") or {}).get("contradiction_count", 0) or 0)
    replanned_contradictions = int(dict(replanned_out.get("contradiction_gate") or {}).get("contradiction_count", 0) or 0)
    if replanned_contradictions < original_contradictions:
        return True
    original_plan = dict(original_out.get("plan") or {})
    replanned_plan = dict(replanned_out.get("plan") or {})
    if float(replanned_plan.get("derivation_survival_score", 0.0) or 0.0) > float(original_plan.get("derivation_survival_score", 0.0) or 0.0):
        return True
    original_history = float(dict((original_out.get("branch_selection") or {}).get("selected_branch") or {}).get("survivor_history", {}).get("score", 0.0) or 0.0)
    replanned_history = float(dict((replanned_out.get("branch_selection") or {}).get("selected_branch") or {}).get("survivor_history", {}).get("score", 0.0) or 0.0)
    return replanned_history > original_history


def _execute_with_replan(cwd: str, request: str, plan: dict, selection: dict) -> dict:
    initial_out = _execute_plan(cwd, request, plan, run_id=str(uuid4()), branch_selection=selection)
    trigger = _replan_trigger(initial_out)
    if not trigger:
        initial_out["replan"] = {"attempted": False, "trigger": "", "applied": False}
        return initial_out

    alternates = [
        review
        for review in list(selection.get("discarded_branches", []))
        if str(review.get("decision", "")) == "allow"
    ]
    for review in alternates:
        review.setdefault("survivor_history", survivor_history_score(cwd, dict(review.get("plan") or {}), trigger=trigger))
    alternates.sort(key=_candidate_replan_sort_key, reverse=True)
    if not alternates:
        initial_out["replan"] = {"attempted": False, "trigger": trigger, "applied": False}
        return initial_out

    alternate = alternates[0]
    alternate_plan = dict(alternate.get("plan") or {})
    replanned_out = _execute_plan(
        cwd,
        request,
        alternate_plan,
        run_id=str(uuid4()),
        branch_selection=_alternate_branch_selection(selection, alternate),
    )
    replan_meta = {
        "attempted": True,
        "trigger": trigger,
        "initial_branch_id": str(((plan.get("branch") or {}).get("id", "primary"))),
        "candidate_branch_id": str((((alternate.get("plan") or {}).get("branch") or {}).get("id", "alternate"))),
        "applied": _should_prefer_replan(initial_out, replanned_out),
    }
    if replan_meta["applied"]:
        replanned_out["replan"] = replan_meta
        replanned_out["initial_run"] = {
            "ok": bool(initial_out.get("ok", False)),
            "branch_id": str(((plan.get("branch") or {}).get("id", "primary"))),
            "completed_steps": _count_completed_steps(list(initial_out.get("results", []))),
            "contradiction_count": int(dict(initial_out.get("contradiction_gate") or {}).get("contradiction_count", 0) or 0),
        }
        return replanned_out
    initial_out["replan"] = replan_meta
    return initial_out


def _attach_strategy_feedback(cwd: str, out: dict) -> dict:
    plan = dict(out.get("plan") or {})
    if not plan:
        return out
    feedback = record_strategy_outcome(cwd, plan, out)
    if feedback.get("ok", False):
        out["strategy_feedback"] = feedback
        save_task_run(cwd, str(out.get("request", "")), out)
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
    return _attach_strategy_feedback(cwd, _execute_with_replan(cwd, request, plan, selection))


def run_task_resume(cwd: str) -> dict:
    resumable = latest_resumable(cwd)
    if not resumable.get("ok", False):
        return {"ok": False, "reason": "no resumable task"}
    task = resumable["task"]
    completed_steps = int(task.get("completed_steps", 0))
    out = _execute_plan(
        cwd,
        str(task.get("request", "")),
        dict(task.get("plan", {})),
        run_id=str(task.get("run_id", "")),
        branch_selection=dict(task.get("branch_selection", {}) or _default_branch_selection(dict(task.get("plan", {})))),
        start_index=int(task.get("resume_from", 0)),
        existing_results=list(task.get("results", []))[:completed_steps],
    )
    trigger = _replan_trigger(out)
    if trigger and dict(task.get("branch_selection", {})).get("discarded_branches"):
        selection = dict(task.get("branch_selection", {}))
        alternates = [
            review
            for review in list(selection.get("discarded_branches", []))
            if str(review.get("decision", "")) == "allow"
        ]
        for review in alternates:
            review.setdefault("survivor_history", survivor_history_score(cwd, dict(review.get("plan") or {}), trigger=trigger))
        alternates.sort(key=_candidate_replan_sort_key, reverse=True)
        if alternates:
            alternate = alternates[0]
            replanned = _execute_plan(
                cwd,
                str(task.get("request", "")),
                dict(alternate.get("plan") or {}),
                run_id=str(uuid4()),
                branch_selection=_alternate_branch_selection(selection, alternate),
            )
            if _should_prefer_replan(out, replanned):
                replanned["replan"] = {
                    "attempted": True,
                    "trigger": trigger,
                    "initial_branch_id": str((((task.get("plan") or {}).get("branch") or {}).get("id", "primary"))),
                    "candidate_branch_id": str((((alternate.get("plan") or {}).get("branch") or {}).get("id", "alternate"))),
                    "applied": True,
                }
                return _attach_strategy_feedback(cwd, replanned)
        out["replan"] = {"attempted": True, "trigger": trigger, "applied": False}
    return _attach_strategy_feedback(cwd, out)

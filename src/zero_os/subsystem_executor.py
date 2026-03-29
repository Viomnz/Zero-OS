from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def execute_subsystem_adapters(
    cwd: str,
    adapters: list[Any] | tuple[Any, ...],
    *,
    context: dict[str, Any] | None = None,
    force: bool = False,
    subsystem_state: dict[str, Any] | None = None,
    scan_snapshot: dict[str, Any] | None = None,
    decide_all: Callable[[str, dict[str, Any], dict[str, Any] | None], dict[str, Any]] | None = None,
    due_predicate: Callable[[str, int, bool], bool] | None = None,
    mutation_action_predicate: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    adapter_list = list(adapters or [])
    if not adapter_list:
        return {
            "ok": True,
            "mode": "empty",
            "adapter_count": 0,
            "adapter_names": [],
        }

    sample = adapter_list[0]
    if callable(getattr(sample, "run", None)):
        return _execute_runtime_plane(cwd, adapter_list, context=context)
    return _execute_decision_plane(
        cwd,
        adapter_list,
        context=context,
        force=force,
        subsystem_state=subsystem_state,
        scan_snapshot=scan_snapshot,
        decide_all=decide_all,
        due_predicate=due_predicate,
        mutation_action_predicate=mutation_action_predicate,
    )


def _execute_runtime_plane(
    cwd: str,
    adapters: list[Any],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shared_context = dict(context or {})
    updates: dict[str, Any] = {}
    runtime_checks: dict[str, Any] = {}
    adapter_results: dict[str, Any] = {}
    for adapter in adapters:
        result = dict(adapter.run(cwd, shared_context) or {})
        adapter_results[str(adapter.name)] = result
        updates.update(dict(result.get("updates") or {}))
        runtime_checks.update(dict(result.get("runtime_checks") or {}))
        shared_context.update(dict(result.get("context") or {}))
    return {
        "ok": True,
        "mode": "runtime",
        "adapter_count": len(adapters),
        "adapter_names": [str(adapter.name) for adapter in adapters],
        "updates": updates,
        "runtime_checks": runtime_checks,
        "context": shared_context,
        "adapter_results": adapter_results,
    }


def _execute_decision_plane(
    cwd: str,
    adapters: list[Any],
    *,
    context: dict[str, Any] | None = None,
    force: bool = False,
    subsystem_state: dict[str, Any] | None = None,
    scan_snapshot: dict[str, Any] | None = None,
    decide_all: Callable[[str, dict[str, Any], dict[str, Any] | None], dict[str, Any]] | None = None,
    due_predicate: Callable[[str, int, bool], bool] | None = None,
    mutation_action_predicate: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    if decide_all is None:
        raise ValueError("decide_all is required for decision-plane execution")
    if due_predicate is None:
        raise ValueError("due_predicate is required for decision-plane execution")
    if mutation_action_predicate is None:
        raise ValueError("mutation_action_predicate is required for decision-plane execution")

    current_state = dict(subsystem_state or {})
    runtime_context = dict(context or {})
    facts: dict[str, Any] = {}
    scan_errors: dict[str, Any] = {}
    scan_started = perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, len(adapters))) as executor:
        futures = {
            executor.submit(adapter.scan, cwd, scan_snapshot): str(adapter.name)
            for adapter in adapters
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                subsystem_facts = dict(future.result() or {})
            except Exception as exc:
                subsystem_facts = {
                    "missing": True,
                    "scan_error": str(exc),
                    "report": {"ok": False, "reason": str(exc)},
                }
                scan_errors[name] = {"reason": str(exc)}
            subsystem_facts["scan_snapshot"] = scan_snapshot
            facts[name] = subsystem_facts
    scan_duration_ms = round((perf_counter() - scan_started) * 1000.0, 3)

    decision_block = dict(decide_all(cwd, facts, runtime_context) or {})
    decisions = dict(decision_block.get("decisions") or {})
    subsystem_reports: dict[str, Any] = {}
    updated_state: dict[str, Any] = {}
    ran_count = 0
    executed_mutation_count = 0
    deferred_mutation_count = 0
    now_utc = _utc_now()
    due_mutating_candidates: list[tuple[str, dict[str, Any]]] = []

    for adapter in adapters:
        name = str(adapter.name)
        adapter_state = dict(current_state.get(name) or {})
        interval_seconds = int(adapter_state.get("interval_seconds", getattr(adapter, "interval_seconds", 60)) or getattr(adapter, "interval_seconds", 60))
        action = str(dict(decisions.get(name) or {}).get("action", "observe"))
        if due_predicate(str(adapter_state.get("last_run_utc", "")), interval_seconds, force) and mutation_action_predicate(action):
            due_mutating_candidates.append((name, dict(decisions.get(name) or {})))

    mutation_winner_name = ""
    if due_mutating_candidates:
        mutation_winner_name = str(
            max(
                due_mutating_candidates,
                key=lambda item: (
                    {"backup": 2, "failover_apply": 3, "revalidate": 1, "verify": 1}.get(str(item[1].get("action", "observe")), 0),
                    float(item[1].get("confidence", 0.0) or 0.0),
                    str(item[0]),
                ),
            )[0]
        )

    for adapter in adapters:
        name = str(adapter.name)
        adapter_state = dict(current_state.get(name) or {})
        decision = dict(decisions.get(name) or {})
        interval_seconds = int(adapter_state.get("interval_seconds", getattr(adapter, "interval_seconds", 60)) or getattr(adapter, "interval_seconds", 60))
        adapter_state["interval_seconds"] = interval_seconds
        fact_report = dict(facts.get(name) or {})
        if "scan_snapshot" in fact_report and isinstance(scan_snapshot, dict):
            fact_report["scan_snapshot"] = scan_snapshot
        if not due_predicate(str(adapter_state.get("last_run_utc", "")), interval_seconds, force):
            subsystem_reports[name] = {
                "ok": True,
                "ran": False,
                "reason": "subsystem not due",
                "decision": decision,
                "facts": fact_report,
            }
            updated_state[name] = adapter_state
            continue
        action = str(decision.get("action", "observe") or "observe")
        if mutation_action_predicate(action) and mutation_winner_name and name != mutation_winner_name:
            subsystem_reports[name] = {
                "ok": True,
                "ran": False,
                "reason": f"mutation budget reserved for {mutation_winner_name}",
                "decision": decision,
                "facts": fact_report,
                "deferred_by_mutation_budget": True,
            }
            updated_state[name] = adapter_state
            deferred_mutation_count += 1
            continue
        result = dict(adapter.enforce(cwd, decision, dict(facts.get(name) or {})) or {})
        adapter_state["last_run_utc"] = now_utc
        adapter_state["last_decision"] = decision
        adapter_state["last_result"] = result
        adapter_state["last_reason"] = str(decision.get("reason", ""))
        updated_state[name] = adapter_state
        subsystem_reports[name] = {
            "ok": bool(result.get("ok", False)),
            "ran": True,
            "decision": decision,
            "facts": fact_report,
            "result": result,
        }
        ran_count += 1
        if mutation_action_predicate(action):
            executed_mutation_count += 1

    return {
        "ok": True,
        "mode": "decision",
        "generated_utc": now_utc,
        "adapter_count": len(adapters),
        "adapter_names": [str(adapter.name) for adapter in adapters],
        "facts": facts,
        "scan_errors": scan_errors,
        "scan_duration_ms": scan_duration_ms,
        "decisions": decisions,
        "decision_block": decision_block,
        "subsystem_reports": subsystem_reports,
        "updated_subsystems": updated_state,
        "ran_count": ran_count,
        "mutation_winner_subsystem": mutation_winner_name,
        "executed_mutation_count": executed_mutation_count,
        "deferred_mutation_count": deferred_mutation_count,
        "due_mutating_candidate_count": len(due_mutating_candidates),
    }

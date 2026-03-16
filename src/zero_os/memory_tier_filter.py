from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from zero_os.playbook_memory import lookup
from zero_os.self_continuity import zero_ai_self_continuity_status
from zero_os.task_memory import load_memory


_INTENT_STEP_HINTS = {
    "planning": {"controller_registry"},
    "reasoning": {"contradiction_engine"},
    "recover": {"recover", "autonomy_gate"},
    "self_repair": {"self_repair", "autonomy_gate"},
    "status": {"observe", "system_status"},
    "store_install": {"store_install"},
    "store_status": {"store_status"},
    "tools": {"tool_registry"},
    "web": {"browser_action", "browser_dom_inspect", "browser_open", "browser_status", "web_fetch", "web_verify"},
}
_TIER_WEIGHTS = {
    "tier1_current": 1.0,
    "tier2_working": 0.75,
    "tier3_playbook": 0.9,
    "tier4_core": 1.0,
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9._/-]+", (text or "").lower()) if len(token) >= 3}


def _relevance(request_tokens: set[str], *texts: str) -> float:
    if not request_tokens:
        return 0.0
    memory_tokens: set[str] = set()
    for text in texts:
        memory_tokens.update(_tokenize(text))
    if not memory_tokens:
        return 0.0
    overlap = len(request_tokens & memory_tokens)
    return round(overlap / max(len(request_tokens), 1), 2)


def _task_intent(task: dict[str, Any]) -> str:
    return str(((task.get("plan") or {}).get("intent") or {}).get("intent", "observe"))


def _task_step_kinds(task: dict[str, Any]) -> list[str]:
    return [str(step.get("kind", "")).strip() for step in list((task.get("plan") or {}).get("steps", [])) if str(step.get("kind", "")).strip()]


def _task_gate_decision(task: dict[str, Any]) -> str:
    gate = dict(task.get("contradiction_gate") or {})
    if not gate:
        gate = dict((task.get("response") or {}).get("contradiction_gate") or {})
    return str(gate.get("decision", "allow"))


def _stable_task(task: dict[str, Any]) -> bool:
    if not bool(task.get("ok", False)):
        return False
    return _task_gate_decision(task) in {"", "allow"}


def _load_policy_memory_payload(cwd: str) -> dict[str, Any]:
    status = zero_ai_self_continuity_status(cwd)
    policy_path = Path(str((status.get("policy_memory") or {}).get("policy_memory_path", "")))
    if not policy_path.exists():
        return {}
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def build_memory_context(cwd: str, request: str, intent: dict[str, Any] | None) -> dict[str, Any]:
    intent_data = dict(intent or {})
    intent_name = str(intent_data.get("intent", "observe"))
    request_text = request.strip()
    request_tokens = _tokenize(request_text)
    expected_step_kinds = sorted(_INTENT_STEP_HINTS.get(intent_name, set()))
    items: list[dict[str, Any]] = [
        {
            "tier": "tier1_current",
            "source": "request",
            "key": "current_request",
            "relevance": 1.0,
            "evidence_weight": 1.0,
            "stable": True,
            "support_step_kinds": expected_step_kinds,
            "summary": request_text,
        }
    ]

    filtered_out = {"task_memory": 0, "playbook": 0}
    tasks = list(load_memory(cwd).get("tasks", []))
    for task in reversed(tasks[-12:]):
        task_intent = _task_intent(task)
        task_steps = _task_step_kinds(task)
        relevance = _relevance(request_tokens, str(task.get("request", "")), " ".join(task_steps), task_intent)
        if task_intent != intent_name and relevance < 0.25:
            filtered_out["task_memory"] += 1
            continue
        if not _stable_task(task):
            filtered_out["task_memory"] += 1
            continue
        items.append(
            {
                "tier": "tier2_working",
                "source": "task_memory",
                "key": str(task.get("request", "")),
                "relevance": relevance if relevance > 0 else 0.25,
                "evidence_weight": min(1.0, 0.35 + max(relevance, 0.25) * 0.65),
                "stable": True,
                "support_step_kinds": task_steps,
                "summary": str(task.get("request", "")),
            }
        )
        if len([item for item in items if item["tier"] == "tier2_working"]) >= 4:
            break

    remembered = lookup(cwd, intent_name)
    if remembered.get("ok", False):
        playbook = dict(remembered.get("plan") or {})
        playbook_steps = [str(step.get("kind", "")).strip() for step in list(playbook.get("steps", [])) if str(step.get("kind", "")).strip()]
        relevance = _relevance(request_tokens, request_text, " ".join(playbook_steps), intent_name)
        if relevance >= 0.2 or playbook_steps:
            items.append(
                {
                    "tier": "tier3_playbook",
                    "source": "playbook_memory",
                    "key": intent_name,
                    "relevance": relevance if relevance > 0 else 0.2,
                    "evidence_weight": min(1.0, 0.4 + max(relevance, 0.2) * 0.6),
                    "stable": True,
                    "support_step_kinds": playbook_steps,
                    "summary": f"playbook:{intent_name}",
                }
            )
        else:
            filtered_out["playbook"] += 1

    continuity = zero_ai_self_continuity_status(cwd)
    policy_memory = _load_policy_memory_payload(cwd)
    identity_policy = dict(policy_memory.get("identity_policy") or {})
    contradiction_free = not bool((continuity.get("contradiction_detection") or {}).get("has_contradiction", False))
    same_system = bool((continuity.get("continuity") or {}).get("same_system", False))
    core_constraints = list(identity_policy.get("required_self_model_constraints", []) or [])
    core_goals = list(identity_policy.get("required_self_model_goals", []) or [])
    core_weight = 1.0 if contradiction_free and same_system else 0.4
    items.append(
        {
            "tier": "tier4_core",
            "source": "policy_memory",
            "key": "core_law",
            "relevance": 1.0,
            "evidence_weight": core_weight,
            "stable": contradiction_free and same_system,
            "support_step_kinds": expected_step_kinds,
            "summary": "core law",
            "constraints": core_constraints,
            "goals": core_goals,
        }
    )

    support_by_kind: dict[str, float] = {}
    for item in items:
        tier_weight = _TIER_WEIGHTS.get(str(item.get("tier", "")), 0.5)
        contribution = float(item.get("evidence_weight", 0.0)) * tier_weight
        for kind in list(item.get("support_step_kinds", [])):
            if not kind:
                continue
            support_by_kind[kind] = round(support_by_kind.get(kind, 0.0) + contribution, 3)

    stable_items = [item for item in items if bool(item.get("stable", False))]
    memory_confidence = 0.0
    if stable_items:
        memory_confidence = round(sum(float(item.get("evidence_weight", 0.0)) for item in stable_items) / len(stable_items), 3)

    return {
        "ok": True,
        "request": request_text,
        "intent": intent_name,
        "items": items,
        "filtered_out": filtered_out,
        "support_by_kind": support_by_kind,
        "memory_confidence": memory_confidence,
        "core_constraints": core_constraints,
        "core_goals": core_goals,
        "same_system": same_system,
        "contradiction_free": contradiction_free,
    }


def score_branch_support(plan: dict[str, Any], memory_context: dict[str, Any]) -> dict[str, Any]:
    steps = list(plan.get("steps", []))
    step_kinds = [str(step.get("kind", "")).strip() for step in steps if str(step.get("kind", "")).strip()]
    support_by_kind = dict(memory_context.get("support_by_kind") or {})
    step_supports = [float(support_by_kind.get(kind, 0.0)) for kind in step_kinds]
    memory_weight = round(min(1.0, sum(step_supports) / max(len(step_supports), 1)), 3) if step_supports else 0.0
    direct_request_weight = 1.0 if step_kinds else 0.25
    core_law_weight = 1.0 if bool(memory_context.get("same_system", False)) and bool(memory_context.get("contradiction_free", False)) else 0.4
    total_weight = round(min(1.0, (direct_request_weight * 0.5) + (memory_weight * 0.35) + (core_law_weight * 0.15)), 3)

    supporting_items: list[dict[str, Any]] = []
    for item in list(memory_context.get("items", [])):
        support_kinds = set(item.get("support_step_kinds", []))
        if support_kinds & set(step_kinds) or str(item.get("tier", "")) == "tier4_core":
            supporting_items.append(
                {
                    "tier": item.get("tier", ""),
                    "source": item.get("source", ""),
                    "key": item.get("key", ""),
                    "evidence_weight": item.get("evidence_weight", 0.0),
                }
            )

    return {
        "direct_request_weight": direct_request_weight,
        "memory_weight": memory_weight,
        "core_law_weight": core_law_weight,
        "total_weight": total_weight,
        "supported_step_kinds": step_kinds,
        "supporting_items": supporting_items,
        "memory_confidence": float(memory_context.get("memory_confidence", 0.0)),
    }

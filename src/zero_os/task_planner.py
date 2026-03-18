from __future__ import annotations

import json
import re
from zero_os.memory_tier_filter import build_memory_context, score_branch_support
from zero_os.playbook_memory import lookup
from zero_os.structured_intent import extract_intent


_MUTATING_STEP_KINDS = {
    "browser_action",
    "browser_open",
    "cloud_deploy",
    "recover",
    "self_repair",
    "store_install",
}
_READ_ONLY_INTENTS = {"planning", "reasoning", "status", "tools"}
_HIGH_RISK_REMEDIATION_KINDS = {"recover", "self_repair"}


def _step_signature(step: dict) -> str:
    return json.dumps(
        {"kind": step.get("kind", ""), "target": step.get("target", "")},
        sort_keys=True,
        default=str,
    )


def _dedupe_steps(steps: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for step in steps:
        signature = _step_signature(step)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(dict(step))
    return deduped


def _clone_plan(plan: dict, steps: list[dict], *, branch_id: str, source: str, note: str, preferred: bool = False) -> dict:
    cloned = dict(plan)
    cloned["steps"] = [dict(step) for step in steps]
    cloned["branch"] = {
        "id": branch_id,
        "source": source,
        "note": note,
        "preferred": bool(preferred),
    }
    return cloned


def _candidate_signature(plan: dict) -> str:
    return json.dumps(
        {
            "steps": [
                {"kind": step.get("kind", ""), "target": step.get("target", "")}
                for step in list(plan.get("steps", []))
            ]
        },
        sort_keys=True,
        default=str,
    )


def _add_candidate(candidates: list[dict], seen: set[str], plan: dict) -> None:
    signature = _candidate_signature(plan)
    if signature in seen:
        return
    seen.add(signature)
    candidates.append(plan)


def _memory_context_summary(memory_context: dict) -> dict:
    return {
        "intent": memory_context.get("intent", "observe"),
        "memory_confidence": memory_context.get("memory_confidence", 0.0),
        "same_system": memory_context.get("same_system", False),
        "contradiction_free": memory_context.get("contradiction_free", False),
        "support_by_kind": dict(memory_context.get("support_by_kind", {})),
        "core_constraints": list(memory_context.get("core_constraints", [])),
        "core_goals": list(memory_context.get("core_goals", [])),
        "items": list(memory_context.get("items", [])),
        "filtered_out": dict(memory_context.get("filtered_out", {})),
    }


def _attach_branch_support(plan: dict, memory_context: dict) -> dict:
    enriched = dict(plan)
    enriched["memory_context"] = _memory_context_summary(memory_context)
    enriched["evidence"] = score_branch_support(enriched, memory_context)
    return enriched


def build_candidate_plans(request: str, cwd: str = ".", base_plan: dict | None = None) -> dict:
    primary = dict(base_plan or build_plan(request, cwd))
    steps = _dedupe_steps(list(primary.get("steps", [])))
    intent_name = str((primary.get("intent") or {}).get("intent", "observe"))
    memory_context = build_memory_context(cwd, request, dict(primary.get("intent", {})))
    candidates: list[dict] = []
    seen: set[str] = set()

    _add_candidate(
        candidates,
        seen,
        _attach_branch_support(
            _clone_plan(
                primary,
                steps,
                branch_id="primary",
                source="direct_plan",
                note="Primary planning branch generated from the request.",
                preferred=True,
            ),
            memory_context,
        ),
    )

    if intent_name in _READ_ONLY_INTENTS and any(str(step.get("kind", "")) in _MUTATING_STEP_KINDS for step in steps):
        safe_steps = [dict(step) for step in steps if str(step.get("kind", "")) not in _MUTATING_STEP_KINDS]
        if not safe_steps:
            safe_steps = [{"kind": "observe", "target": request.strip()}]
        _add_candidate(
            candidates,
            seen,
            _attach_branch_support(
                _clone_plan(
                    primary,
                    safe_steps,
                    branch_id="read_only_fallback",
                    source="regenerated_read_only",
                    note="Read-only fallback branch regenerated after mutating steps conflicted with a read-only request.",
                ),
                memory_context,
            ),
        )

    remediation_order: list[str] = []
    for step in steps:
        kind = str(step.get("kind", ""))
        if kind in _HIGH_RISK_REMEDIATION_KINDS and kind not in remediation_order:
            remediation_order.append(kind)
    if len(remediation_order) > 1:
        support_by_kind = dict(memory_context.get("support_by_kind", {}))
        preferred = max(
            remediation_order,
            key=lambda kind: (
                1 if kind == intent_name else 0,
                float(support_by_kind.get(kind, 0.0)),
                -remediation_order.index(kind),
            ),
        )
        ordered = [preferred] + [kind for kind in remediation_order if kind != preferred]
        for kind in ordered:
            branch_steps = [dict(step) for step in steps if str(step.get("kind", "")) not in _HIGH_RISK_REMEDIATION_KINDS or str(step.get("kind", "")) == kind]
            _add_candidate(
                candidates,
                seen,
                _attach_branch_support(
                    _clone_plan(
                        primary,
                        branch_steps,
                        branch_id=f"single_{kind}",
                        source="regenerated_single_remediation",
                        note=f"Single remediation branch regenerated to avoid mixing {', '.join(remediation_order)} in one run.",
                        preferred=(kind == preferred),
                    ),
                    memory_context,
                ),
            )

    return {
        "ok": True,
        "request": request.strip(),
        "intent": dict(primary.get("intent", {})),
        "memory_context": _memory_context_summary(memory_context),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def build_plan(request: str, cwd: str = ".") -> dict:
    text = request.strip()
    lowered = text.lower()
    intent = extract_intent(request)
    steps: list[dict] = []
    should_resume = str(intent.get("constraints", {}).get("resume", "")).lower() == "true"
    remembered = lookup(cwd, intent["intent"]) if should_resume else {"ok": False}
    if remembered.get("ok", False):
        steps.extend(list(remembered["plan"].get("steps", [])))
    if intent["intent"] == "tools" or any(token in lowered for token in ("tools", "capabilities", "what can you do")):
        steps.append({"kind": "tool_registry", "target": "registry"})
    if intent["intent"] == "planning" or any(token in lowered for token in ("highest value", "highest-value", "next step", "next steps", "what should improve", "recommend")):
        steps.append({"kind": "controller_registry", "target": "next_steps"})
    if intent["intent"] == "reasoning" or any(token in lowered for token in ("contradiction engine", "contradiction gate", "reasoning gate", "contradiction status")):
        steps.append({"kind": "contradiction_engine", "target": "status"})
    if intent["intent"] == "pressure" or any(
        token in lowered for token in ("pressure harness", "stress harness", "pressure mode", "stress test", "pressure test")
    ):
        steps.append({"kind": "pressure_harness", "target": "status" if "status" in lowered else "run"})
    if any(
        token in lowered
        for token in (
            "smart workspace",
            "workspace status",
            "workspace map",
            "workspace overview",
            "understand workspace",
            "repo overview",
        )
    ):
        steps.append({"kind": "smart_workspace", "target": "main"})
    if any(
        token in lowered
        for token in (
            "find contradiction",
            "find bug",
            "find bugs",
            "find error",
            "find errors",
            "find virus",
            "find viruses",
            "find malware",
            "scan for bug",
            "scan for bugs",
            "scan for error",
            "scan for virus",
            "scan workspace",
            "scan system",
            "virus",
            "malware",
        )
    ):
        steps.append({"kind": "flow_monitor", "target": "."})
    if intent["intent"] == "web" or "http://" in lowered or "https://" in lowered:
        urls = list(dict.fromkeys(re.findall(r"https?://\S+", text)))
        for url in urls:
            steps.append({"kind": "web_verify", "target": url})
            if any(token in lowered for token in ("fetch", "open", "read", "load")):
                steps.append({"kind": "web_fetch", "target": url})
                if "open" in lowered:
                    steps.append({"kind": "browser_open", "target": url})
                if any(token in lowered for token in ("click", "submit", "type")):
                    steps.append({"kind": "browser_action", "target": {"url": url, "action": "click", "selector": "body"}})
    if intent["intent"] == "status" or any(token in lowered for token in ("system status", "diagnostic", "health check", "system health")):
        steps.append({"kind": "system_status", "target": "health"})
    if any(token in lowered for token in ("browser status", "tabs", "session")):
        steps.append({"kind": "browser_status", "target": "browser"})
    if any(token in lowered for token in ("inspect page", "dom inspect")) and ("http://" in lowered or "https://" in lowered):
        for url in list(dict.fromkeys(re.findall(r"https?://\S+", text))):
            steps.append({"kind": "browser_dom_inspect", "target": url})
    if intent["intent"] == "store_status" or "native store status" in lowered or "store status" in lowered:
        steps.append({"kind": "store_status", "target": "native_store"})
    install_match = re.search(r"install\s+app\s+([a-z0-9._-]+)", lowered)
    if install_match:
        steps.append({"kind": "store_install", "target": install_match.group(1)})
    if intent["intent"] == "self_repair" or any(token in lowered for token in ("repair", "self repair")):
        steps.append({"kind": "self_repair", "target": "runtime"})
    if intent["intent"] == "recover" or any(token in lowered for token in ("recover", "recovery")):
        steps.append({"kind": "recover", "target": "runtime"})
    api_match = re.search(r"api\s+profile\s+([a-z0-9._-]+)\s+fetch\s+(\S+)", lowered)
    if api_match:
        steps.append({"kind": "api_request", "target": {"profile": api_match.group(1), "path": api_match.group(2)}})
    api_flow_match = re.search(r"api\s+workflow\s+([a-z0-9._-]+)\s+paths\s+(.+)$", lowered)
    if api_flow_match:
        parts = [p.strip() for p in api_flow_match.group(2).split(",") if p.strip()]
        steps.append({"kind": "api_workflow", "target": {"profile": api_flow_match.group(1), "paths": parts}})
    gh_match = re.search(r"github\s+repo\s+connect\s+([a-z0-9._/-]+)", lowered)
    if gh_match:
        steps.append({"kind": "github_connect", "target": gh_match.group(1)})
    gh_issues = re.search(r"github\s+issues\s+([a-z0-9._/-]+)", lowered)
    if gh_issues:
        steps.append({"kind": "github_issues", "target": gh_issues.group(1)})
    gh_prs = re.search(r"github\s+prs\s+([a-z0-9._/-]+)", lowered)
    if gh_prs:
        steps.append({"kind": "github_prs", "target": gh_prs.group(1)})
    gh_issue_read = re.search(r"github\s+issue\s+read\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_issue_read:
        steps.append({"kind": "github_issue_read", "target": {"repo": gh_issue_read.group(1), "issue": int(gh_issue_read.group(2))}})
    gh_issue_comments = re.search(r"github\s+issue\s+comments\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_issue_comments:
        steps.append({"kind": "github_issue_comments", "target": {"repo": gh_issue_comments.group(1), "issue": int(gh_issue_comments.group(2))}})
    gh_issue_plan = re.search(r"github\s+issue\s+plan\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_issue_plan:
        steps.append({"kind": "github_issue_plan", "target": {"repo": gh_issue_plan.group(1), "issue": int(gh_issue_plan.group(2))}})
    gh_issue_act = re.search(r"github\s+issue\s+act\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_issue_act:
        steps.append({"kind": "github_issue_act", "target": {"repo": gh_issue_act.group(1), "issue": int(gh_issue_act.group(2)), "execute": False}})
    gh_issue_reply_post = re.search(r"github\s+issue\s+reply\s+post\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_issue_reply_post:
        text_match = re.search(r'text=(.+)$', text, flags=re.IGNORECASE)
        steps.append({"kind": "github_issue_reply_post", "target": {"repo": gh_issue_reply_post.group(1), "issue": int(gh_issue_reply_post.group(2)), "text": (text_match.group(1).strip() if text_match else "")}})
    gh_issue_reply = re.search(r"github\s+issue\s+reply\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_issue_reply and not gh_issue_reply_post:
        execute = " execute=true" in lowered
        steps.append({"kind": "github_issue_reply_draft", "target": {"repo": gh_issue_reply.group(1), "issue": int(gh_issue_reply.group(2)), "execute": execute}})
    gh_pr_read = re.search(r"github\s+pr\s+read\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_pr_read:
        steps.append({"kind": "github_pr_read", "target": {"repo": gh_pr_read.group(1), "pr": int(gh_pr_read.group(2))}})
    gh_pr_comments = re.search(r"github\s+pr\s+comments\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_pr_comments:
        steps.append({"kind": "github_pr_comments", "target": {"repo": gh_pr_comments.group(1), "pr": int(gh_pr_comments.group(2))}})
    gh_pr_plan = re.search(r"github\s+pr\s+plan\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_pr_plan:
        steps.append({"kind": "github_pr_plan", "target": {"repo": gh_pr_plan.group(1), "pr": int(gh_pr_plan.group(2))}})
    gh_pr_act = re.search(r"github\s+pr\s+act\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_pr_act:
        steps.append({"kind": "github_pr_act", "target": {"repo": gh_pr_act.group(1), "pr": int(gh_pr_act.group(2)), "execute": False}})
    gh_pr_reply_post = re.search(r"github\s+pr\s+reply\s+post\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_pr_reply_post:
        text_match = re.search(r'text=(.+)$', text, flags=re.IGNORECASE)
        steps.append({"kind": "github_pr_reply_post", "target": {"repo": gh_pr_reply_post.group(1), "pr": int(gh_pr_reply_post.group(2)), "text": (text_match.group(1).strip() if text_match else "")}})
    gh_pr_reply = re.search(r"github\s+pr\s+reply\s+([a-z0-9._/-]+)\s+(\d+)", lowered)
    if gh_pr_reply and not gh_pr_reply_post:
        execute = " execute=true" in lowered
        steps.append({"kind": "github_pr_reply_draft", "target": {"repo": gh_pr_reply.group(1), "pr": int(gh_pr_reply.group(2)), "execute": execute}})
    cloud_cfg = re.search(r"cloud\s+target\s+set\s+([a-z0-9._-]+)\s+provider\s+([a-z0-9._-]+)", lowered)
    if cloud_cfg:
        steps.append({"kind": "cloud_target_set", "target": {"name": cloud_cfg.group(1), "provider": cloud_cfg.group(2)}})
    cloud_dep = re.search(r"deploy\s+artifact\s+([a-z0-9._/-]+)\s+to\s+([a-z0-9._-]+)", lowered)
    if cloud_dep:
        steps.append({"kind": "cloud_deploy", "target": {"artifact": cloud_dep.group(1), "target": cloud_dep.group(2)}})
    if any(token in lowered for token in ("read file", "show ", "whoami", "date", "time")):
        steps.append({"kind": "highway_dispatch", "target": text})
    if any(token in lowered for token in ("fix", "repair", "recover")):
        steps.append({"kind": "autonomy_gate", "target": text})
    if not steps:
        steps.append({"kind": "observe", "target": text})
    return {"ok": True, "request": text, "intent": intent, "steps": steps}

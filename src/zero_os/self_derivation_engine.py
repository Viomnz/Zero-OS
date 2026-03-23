from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.semantic_reasoner import semantic_abstraction_profile
from zero_os.smart_planner import simulate_plan, simulate_plan_conflicts
from zero_os.state_cache import flush_state_writes, load_json_state, queue_json_state
from zero_os.state_registry import put_state_store
from zero_os.task_planner_composer import step_allows_mutation

_VERIFICATION_KINDS = {
    "observe",
    "system_status",
    "browser_status",
    "browser_dom_inspect",
    "web_verify",
    "web_fetch",
    "store_status",
    "github_issue_read",
    "github_issue_comments",
    "github_issue_plan",
    "github_pr_read",
    "github_pr_comments",
    "github_pr_plan",
    "flow_monitor",
}
_PREPARE_KINDS = {
    "browser_open",
    "cloud_target_set",
    "github_connect",
}
_SELF_DERIVATION_CODE_VERSION = "2026.03.22.strategy_memory"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _strategy_record_freshness(record: dict[str, Any], *, condition_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    current_planner_version = _current_planner_version()
    current_code_version = _current_strategy_code_version()
    condition_profile = dict(condition_profile or {})
    matched_condition: dict[str, Any] = {}
    matched_condition_signature = ""
    condition_profiles = dict(record.get("condition_profiles") or {})
    requested_condition_signature = str(condition_profile.get("signature", "")).strip()
    if requested_condition_signature:
        matched_condition = dict(condition_profiles.get(requested_condition_signature) or {})
        matched_condition_signature = requested_condition_signature if matched_condition else ""
    if not matched_condition and condition_profile:
        best_overlap = 0.0
        for signature, raw_condition in condition_profiles.items():
            candidate = dict(raw_condition or {})
            candidate_profile = dict(candidate.get("condition_profile") or {})
            overlap = 0.0
            if str(candidate_profile.get("subsystem_surface", "")) == str(condition_profile.get("subsystem_surface", "")):
                overlap += 0.5
            if str(candidate_profile.get("structure_family", "")) == str(condition_profile.get("structure_family", "")):
                overlap += 0.2
            if str(candidate_profile.get("semantic_goal", "")) == str(condition_profile.get("semantic_goal", "")):
                overlap += 0.15
            if str(candidate_profile.get("risk_level", "")) == str(condition_profile.get("risk_level", "")):
                overlap += 0.05
            target_family_overlap = set(str(item) for item in list(candidate_profile.get("target_families", []))) & set(
                str(item) for item in list(condition_profile.get("target_families", []))
            )
            overlap += min(0.15, len(target_family_overlap) * 0.05)
            if overlap <= best_overlap:
                continue
            best_overlap = overlap
            matched_condition = candidate
            matched_condition_signature = str(signature)
    condition_last_run = _parse_utc(str(matched_condition.get("last_seen_utc", "") or ""))
    last_run = condition_last_run or _parse_utc(str(record.get("last_run_utc", "") or record.get("updated_utc", "") or ""))
    record_planner_version = str(matched_condition.get("planner_version", "") or record.get("planner_version", "") or "").strip()
    record_code_version = str(matched_condition.get("code_version", "") or record.get("code_version", "") or "").strip()
    planner_version_match = not record_planner_version or record_planner_version == current_planner_version
    code_version_match = not record_code_version or record_code_version == current_code_version
    version_alignment_score = 1.0
    if record_planner_version and not planner_version_match:
        version_alignment_score *= 0.55
    if record_code_version and not code_version_match:
        version_alignment_score *= 0.45
    if last_run is None:
        # Legacy records may not have timestamps yet; treat them as neutral-fresh
        # so they can still guide planning until explicit age data exists.
        freshness_score = round(max(0.08, min(1.0, 0.8 * version_alignment_score)), 3)
        return {
            "freshness_score": freshness_score,
            "days_since_last_run": None,
            "current_planner_version": current_planner_version,
            "record_planner_version": record_planner_version,
            "planner_version_match": planner_version_match,
            "current_code_version": current_code_version,
            "record_code_version": record_code_version,
            "code_version_match": code_version_match,
            "version_alignment_score": round(version_alignment_score, 3),
            "condition_match_score": round(1.0 if matched_condition_signature == requested_condition_signature and matched_condition_signature else 0.0, 3),
            "condition_match_exact": bool(matched_condition_signature and matched_condition_signature == requested_condition_signature),
            "condition_signature": matched_condition_signature,
            "subsystem_surface": str(dict(matched_condition.get("condition_profile") or {}).get("subsystem_surface", "") or str(condition_profile.get("subsystem_surface", ""))),
        }
    age_days = max(0.0, (datetime.now(timezone.utc) - last_run).total_seconds() / 86400.0)
    freshness_score = max(0.08, min(1.0, 1.0 - min(age_days, 180.0) / 180.0))
    freshness_score = round(max(0.08, min(1.0, freshness_score * version_alignment_score)), 3)
    return {
        "freshness_score": freshness_score,
        "days_since_last_run": round(age_days, 2),
        "current_planner_version": current_planner_version,
        "record_planner_version": record_planner_version,
        "planner_version_match": planner_version_match,
        "current_code_version": current_code_version,
        "record_code_version": record_code_version,
        "code_version_match": code_version_match,
        "version_alignment_score": round(version_alignment_score, 3),
        "condition_match_score": round(1.0 if matched_condition_signature == requested_condition_signature and matched_condition_signature else (0.6 if matched_condition_signature else 0.0), 3),
        "condition_match_exact": bool(matched_condition_signature and matched_condition_signature == requested_condition_signature),
        "condition_signature": matched_condition_signature,
        "subsystem_surface": str(dict(matched_condition.get("condition_profile") or {}).get("subsystem_surface", "") or str(condition_profile.get("subsystem_surface", ""))),
    }


def _accumulate_surface_freshness(
    profiles: dict[str, dict[str, Any]],
    *,
    surface: str,
    freshness: dict[str, Any],
    recovery_profile: str,
    quarantined: bool,
) -> None:
    normalized_surface = str(surface or "general_surface").strip() or "general_surface"
    profile = dict(
        profiles.get(normalized_surface)
        or {
            "surface": normalized_surface,
            "count": 0,
            "active_count": 0,
            "quarantined_count": 0,
            "fresh_count": 0,
            "stale_count": 0,
            "version_mismatch_count": 0,
            "freshness_total": 0.0,
            "freshness_score": 0.0,
            "recovery_profiles": {},
            "top_recovery_profile": "neutral",
        }
    )
    freshness_score = float(freshness.get("freshness_score", 0.0) or 0.0)
    profile["count"] = int(profile.get("count", 0) or 0) + 1
    if quarantined:
        profile["quarantined_count"] = int(profile.get("quarantined_count", 0) or 0) + 1
    else:
        profile["active_count"] = int(profile.get("active_count", 0) or 0) + 1
    profile["freshness_total"] = float(profile.get("freshness_total", 0.0) or 0.0) + freshness_score
    if freshness_score >= 0.75:
        profile["fresh_count"] = int(profile.get("fresh_count", 0) or 0) + 1
    if freshness_score < 0.4:
        profile["stale_count"] = int(profile.get("stale_count", 0) or 0) + 1
    if not bool(freshness.get("planner_version_match", True)) or not bool(freshness.get("code_version_match", True)):
        profile["version_mismatch_count"] = int(profile.get("version_mismatch_count", 0) or 0) + 1
    recovery_profiles = dict(profile.get("recovery_profiles") or {})
    recovery_profiles[recovery_profile] = int(recovery_profiles.get(recovery_profile, 0) or 0) + 1
    profile["recovery_profiles"] = recovery_profiles
    profile["freshness_score"] = round(float(profile["freshness_total"]) / max(1, int(profile["count"])), 3)
    profile["top_recovery_profile"] = (
        max(recovery_profiles.items(), key=lambda item: (int(item[1] or 0), str(item[0])))[0]
        if recovery_profiles
        else "neutral"
    )
    profiles[normalized_surface] = profile


def _current_planner_version() -> str:
    try:
        from zero_os.task_planner import PLANNER_VERSION

        return str(PLANNER_VERSION).strip() or "unknown"
    except Exception:
        return "unknown"


def _current_strategy_code_version() -> str:
    return f"planner:{_current_planner_version()}|self_derivation:{_SELF_DERIVATION_CODE_VERSION}"


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "self_derivation"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _latest_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "latest.json"


def _memory_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "memory.json"


def _load_json(path: Path, default: Any) -> Any:
    return load_json_state(path, default)


def _save_json(path: Path, payload: Any) -> None:
    queue_json_state(path, payload)


def _target_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(part for part in (_target_text(item) for item in value.values()) if part)
    if isinstance(value, (list, tuple, set)):
        return " ".join(part for part in (_target_text(item) for item in value) if part)
    return str(value or "").strip()


def _step_signature(step: dict[str, Any]) -> str:
    return json.dumps({"kind": step.get("kind", ""), "target": step.get("target", "")}, sort_keys=True, default=str)


def _plan_signature(plan: dict[str, Any]) -> str:
    return json.dumps(
        [{"kind": step.get("kind", ""), "target": step.get("target", "")} for step in list(plan.get("steps", []))],
        sort_keys=True,
        default=str,
    )


def _step_role(step: dict[str, Any]) -> str:
    kind = str(step.get("kind", ""))
    if kind in _VERIFICATION_KINDS:
        return "verify"
    if kind in _PREPARE_KINDS:
        return "prepare"
    if step_allows_mutation(kind):
        return "mutate"
    if "status" in kind or "read" in kind or "inspect" in kind:
        return "observe"
    return "dispatch"


def _abstract_pattern(steps: list[dict[str, Any]]) -> str:
    roles = [_step_role(step) for step in steps]
    compact: list[str] = []
    for role in roles:
        if not compact or compact[-1] != role:
            compact.append(role)
    return " -> ".join(compact) if compact else "observe"


def _branch_shape_profile(plan: dict[str, Any]) -> dict[str, Any]:
    request_targets = dict(plan.get("request_targets", {}))
    decomposition = list(plan.get("request_decomposition", []))
    abstraction = semantic_abstraction_profile(
        str(plan.get("request", "")),
        request_targets,
        decomposition,
    )
    target_items = list(request_targets.get("items", []))
    dependency_count = sum(len(list(item.get("depends_on", []))) for item in decomposition)
    conditional_count = sum(1 for item in decomposition if bool(item.get("conditional", False)))
    mutating_count = sum(1 for step in list(plan.get("steps", [])) if step_allows_mutation(str(step.get("kind", ""))))
    target_families = sorted({str(item) for item in list(abstraction.get("target_families", [])) if str(item)})
    profile = {
        "pattern_signature": _abstract_pattern(list(plan.get("steps", []))),
        "structure_family": str(abstraction.get("structure_family", "")),
        "semantic_goal": str(abstraction.get("semantic_goal", "")),
        "target_families": target_families,
        "target_types": _target_types(plan),
        "dependency_depth": "deep" if dependency_count >= 3 else "light" if dependency_count > 0 else "none",
        "conditional_flow": bool(conditional_count),
        "multi_target": bool(len(target_items) > 1 or len(target_families) > 1),
        "mutating": bool(mutating_count),
        "risk_level": str(plan.get("risk_level", "low") or "low").strip().lower(),
    }
    return {
        **profile,
        "signature": json.dumps(profile, sort_keys=True),
    }


def _strategy_condition_profile(plan: dict[str, Any]) -> dict[str, Any]:
    request_targets = dict(plan.get("request_targets", {}))
    decomposition = list(plan.get("request_decomposition", []))
    abstraction = semantic_abstraction_profile(
        str(plan.get("request", "")),
        request_targets,
        decomposition,
    )
    target_families = sorted({str(item) for item in list(abstraction.get("target_families", [])) if str(item)})
    target_types = _target_types(plan)
    steps = list(plan.get("steps", []))
    step_kinds = {str(step.get("kind", "")).strip() for step in steps if str(step.get("kind", "")).strip()}
    browser_action_modes = {
        str(dict(step.get("target") or {}).get("action", "") or "").strip().lower()
        for step in steps
        if str(step.get("kind", "")).strip() == "browser_action"
    }
    browser_action_modes = {mode for mode in browser_action_modes if mode}
    github_issue_reply_draft_kinds = {"github_issue_reply_draft"}
    github_pr_reply_draft_kinds = {"github_pr_reply_draft"}
    github_issue_reply_post_kinds = {"github_issue_reply_post"}
    github_pr_reply_post_kinds = {"github_pr_reply_post"}
    github_issue_comment_kinds = {"github_issue_comments"}
    github_pr_comment_kinds = {"github_pr_comments"}
    github_issue_plan_kinds = {"github_issue_plan"}
    github_pr_plan_kinds = {"github_pr_plan"}
    github_issue_read_only_kinds = {"github_issue_read"}
    github_pr_read_only_kinds = {"github_pr_read"}
    github_reply_draft_kinds = github_issue_reply_draft_kinds | github_pr_reply_draft_kinds
    github_reply_post_kinds = github_issue_reply_post_kinds | github_pr_reply_post_kinds
    github_issue_reply_kinds = github_issue_reply_draft_kinds | github_issue_reply_post_kinds | {"github_issue_act"}
    github_pr_reply_kinds = github_pr_reply_draft_kinds | github_pr_reply_post_kinds | {"github_pr_act"}
    github_reply_kinds = github_issue_reply_kinds | github_pr_reply_kinds
    github_read_kinds = {
        "github_connect",
        "github_issue_read",
        "github_issue_comments",
        "github_issue_plan",
        "github_pr_read",
        "github_pr_comments",
        "github_pr_plan",
    }
    browser_mutation = "browser_action" in step_kinds
    deploy_mutation = "cloud_deploy" in step_kinds
    generic_mutation = any(step_allows_mutation(kind) for kind in step_kinds if kind not in {"browser_open", "browser_action", "cloud_deploy"})
    subsystem_surface = "general_surface"
    if step_kinds & github_pr_reply_post_kinds:
        subsystem_surface = "github_pr_reply_post_surface"
    elif step_kinds & github_pr_reply_draft_kinds:
        subsystem_surface = "github_pr_reply_draft_surface"
    elif step_kinds & github_issue_reply_post_kinds:
        subsystem_surface = "github_issue_reply_post_surface"
    elif step_kinds & github_issue_reply_draft_kinds:
        subsystem_surface = "github_issue_reply_draft_surface"
    elif step_kinds & github_pr_reply_kinds:
        subsystem_surface = "github_pr_reply_surface"
    elif step_kinds & github_issue_reply_kinds:
        subsystem_surface = "github_issue_reply_surface"
    elif step_kinds & github_pr_comment_kinds:
        subsystem_surface = "github_pr_comment_surface"
    elif step_kinds & github_issue_comment_kinds:
        subsystem_surface = "github_issue_comment_surface"
    elif step_kinds & github_pr_plan_kinds:
        subsystem_surface = "github_pr_plan_surface"
    elif step_kinds & github_issue_plan_kinds:
        subsystem_surface = "github_issue_plan_surface"
    elif step_kinds & github_pr_read_only_kinds:
        subsystem_surface = "github_pr_read_surface"
    elif step_kinds & github_issue_read_only_kinds:
        subsystem_surface = "github_issue_read_surface"
    elif step_kinds & github_read_kinds or any(item in {"github_issues", "github_prs"} for item in target_types):
        subsystem_surface = "github_read_surface"
    elif "delivery_surface" in target_families or step_kinds & {"cloud_target_set", "cloud_deploy"}:
        subsystem_surface = "deploy_mutate_surface" if deploy_mutation else "deploy_verify_surface"
    elif ("interaction_surface" in target_families and "remote_source" in target_families) or step_kinds & {"browser_status", "browser_dom_inspect", "web_verify", "web_fetch", "browser_open", "browser_action"}:
        if browser_mutation:
            if "submit" in browser_action_modes:
                subsystem_surface = "browser_submit_surface"
            elif browser_action_modes & {"input", "type", "fill", "enter_text"}:
                subsystem_surface = "browser_input_surface"
            elif "click" in browser_action_modes:
                subsystem_surface = "browser_click_surface"
            else:
                subsystem_surface = "browser_mutate_surface"
        else:
            subsystem_surface = "browser_read_surface"
    elif any(item in {"api_requests", "api_workflows"} for item in target_types):
        subsystem_surface = "api_mutate_surface" if generic_mutation else "api_read_surface"
    elif "workspace_source" in target_families:
        subsystem_surface = "workspace_mutate_surface" if generic_mutation else "workspace_read_surface"
    elif "collaboration_source" in target_families:
        subsystem_surface = "collaboration_mutate_surface" if generic_mutation else "collaboration_read_surface"
    elif "remote_source" in target_families:
        subsystem_surface = "remote_mutate_surface" if generic_mutation else "remote_read_surface"
    profile = {
        "subsystem_surface": subsystem_surface,
        "structure_family": str(abstraction.get("structure_family", "")),
        "semantic_goal": str(abstraction.get("semantic_goal", "")),
        "target_families": target_families,
        "target_types": target_types,
        "risk_level": str(plan.get("risk_level", "low") or "low").strip().lower(),
        "execution_mode": str(plan.get("execution_mode", "") or "").strip().lower(),
        "strategy_mode": str(dict(plan.get("smart_planner") or {}).get("strategy_mode", "") or "").strip().lower(),
    }
    return {
        **profile,
        "signature": json.dumps(profile, sort_keys=True),
    }


def _surface_target_items(condition_profile: dict[str, Any]) -> list[dict[str, Any]]:
    surface = str(condition_profile.get("subsystem_surface", "")).strip().lower()
    if surface.startswith("browser_") or surface.startswith("remote_"):
        return [{"id": "canary_url", "type": "urls", "value": "https://example.com", "label": "https://example.com"}]
    if surface.startswith("github_pr_"):
        return [{"id": "canary_pr", "type": "github_prs", "value": {"repo": "octocat/Hello-World", "pr": 1}, "label": "octocat/Hello-World#PR1"}]
    if surface.startswith("github_issue_"):
        return [{"id": "canary_issue", "type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}, "label": "octocat/Hello-World#1"}]
    if surface.startswith("github_") or surface.startswith("collaboration_"):
        return [{"id": "canary_issue", "type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}, "label": "octocat/Hello-World#1"}]
    if surface.startswith("deploy_"):
        return [
            {"id": "canary_target", "type": "cloud_targets", "value": {"target": "staging"}, "label": "staging"},
            {"id": "canary_deploy", "type": "deployments", "value": {"target": "staging", "artifact": "build/canary.zip"}, "label": "build/canary.zip -> staging"},
        ]
    if surface.startswith("workspace_"):
        return [{"id": "canary_file", "type": "files", "value": "README.md", "label": "README.md"}]
    if surface.startswith("api_"):
        return [{"id": "canary_api", "type": "api_requests", "value": {"service": "sample_api", "operation": "status"}, "label": "sample_api.status"}]
    return []


def _make_canary_step(kind: str, target: Any, *, risk_level: str | None = None) -> dict[str, Any]:
    kind = str(kind).strip()
    effective_risk = risk_level or ("medium" if step_allows_mutation(kind) else "low")
    return {
        "kind": kind,
        "target": target,
        "risk_level": effective_risk,
        "requires_approval_possible": kind in {"browser_action", "recover", "self_repair", "store_install"},
        "verification_mode": "observe" if not step_allows_mutation(kind) else "mutation",
        "source_of_route": "self_derivation_canary",
        "route_confidence": 0.72,
        "requires": [],
        "decomposition_depends_on": [],
        "failure_impact": {"blocks": [], "degrades": []},
        "dependency_strength": "soft",
    }


def _strategy_canary_steps(record: dict[str, Any]) -> list[dict[str, Any]]:
    condition_profile = dict(record.get("last_condition_profile") or {})
    surface = str(condition_profile.get("subsystem_surface", "")).strip().lower()
    if not surface:
        condition_profiles = dict(record.get("condition_profiles") or {})
        if condition_profiles:
            best_condition = max(
                (dict(item or {}) for item in condition_profiles.values()),
                key=lambda item: int(item.get("run_count", 0) or 0),
            )
            condition_profile = dict(best_condition.get("condition_profile") or {})
            surface = str(condition_profile.get("subsystem_surface", "")).strip().lower()

    steps: list[dict[str, Any]]
    if surface in {"browser_click_surface"}:
        steps = [
            _make_canary_step("browser_open", {"url": "https://example.com"}, risk_level="low"),
            _make_canary_step("browser_action", {"url": "https://example.com", "action": "click", "selector": "body"}, risk_level="medium"),
        ]
    elif surface in {"browser_input_surface"}:
        steps = [
            _make_canary_step("browser_open", {"url": "https://example.com"}, risk_level="low"),
            _make_canary_step(
                "browser_action",
                {"url": "https://example.com", "action": "input", "selector": "body", "value": "canary"},
                risk_level="medium",
            ),
        ]
    elif surface in {"browser_submit_surface"}:
        steps = [
            _make_canary_step("browser_open", {"url": "https://example.com"}, risk_level="low"),
            _make_canary_step("browser_action", {"url": "https://example.com", "action": "submit", "selector": "body"}, risk_level="medium"),
        ]
    elif surface in {"browser_mutate_surface"}:
        steps = [
            _make_canary_step("browser_open", {"url": "https://example.com"}, risk_level="low"),
            _make_canary_step("browser_action", {"url": "https://example.com", "action": "submit", "selector": "body"}, risk_level="medium"),
        ]
    elif surface in {"browser_read_surface", "remote_read_surface", "remote_mutate_surface"}:
        steps = [
            _make_canary_step("browser_status", {}),
            _make_canary_step("browser_dom_inspect", {"url": "https://example.com"}),
        ]
    elif surface == "github_pr_reply_post_surface":
        steps = [
            _make_canary_step("github_pr_read", {"repo": "octocat/Hello-World", "pr": 1}),
            _make_canary_step("github_pr_reply_post", {"repo": "octocat/Hello-World", "pr": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface == "github_pr_reply_draft_surface":
        steps = [
            _make_canary_step("github_pr_read", {"repo": "octocat/Hello-World", "pr": 1}),
            _make_canary_step("github_pr_reply_draft", {"repo": "octocat/Hello-World", "pr": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface == "github_pr_reply_surface":
        steps = [
            _make_canary_step("github_pr_read", {"repo": "octocat/Hello-World", "pr": 1}),
            _make_canary_step("github_pr_reply_post", {"repo": "octocat/Hello-World", "pr": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface == "github_pr_comment_surface":
        steps = [
            _make_canary_step("github_pr_read", {"repo": "octocat/Hello-World", "pr": 1}),
            _make_canary_step("github_pr_comments", {"repo": "octocat/Hello-World", "pr": 1}),
        ]
    elif surface == "github_pr_plan_surface":
        steps = [
            _make_canary_step("github_pr_read", {"repo": "octocat/Hello-World", "pr": 1}),
            _make_canary_step("github_pr_plan", {"repo": "octocat/Hello-World", "pr": 1}),
        ]
    elif surface == "github_pr_read_surface":
        steps = [_make_canary_step("github_pr_read", {"repo": "octocat/Hello-World", "pr": 1})]
    elif surface == "github_issue_reply_post_surface":
        steps = [
            _make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1}),
            _make_canary_step("github_issue_reply_post", {"repo": "octocat/Hello-World", "issue": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface == "github_issue_reply_draft_surface":
        steps = [
            _make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1}),
            _make_canary_step("github_issue_reply_draft", {"repo": "octocat/Hello-World", "issue": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface == "github_issue_reply_surface":
        steps = [
            _make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1}),
            _make_canary_step("github_issue_reply_post", {"repo": "octocat/Hello-World", "issue": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface == "github_issue_comment_surface":
        steps = [
            _make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1}),
            _make_canary_step("github_issue_comments", {"repo": "octocat/Hello-World", "issue": 1}),
        ]
    elif surface == "github_issue_plan_surface":
        steps = [
            _make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1}),
            _make_canary_step("github_issue_plan", {"repo": "octocat/Hello-World", "issue": 1}),
        ]
    elif surface == "github_issue_read_surface":
        steps = [_make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1})]
    elif surface == "github_reply_post_surface":
        steps = [
            _make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1}),
            _make_canary_step("github_issue_reply_post", {"repo": "octocat/Hello-World", "issue": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface == "github_reply_draft_surface":
        steps = [
            _make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1}),
            _make_canary_step("github_issue_reply_draft", {"repo": "octocat/Hello-World", "issue": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface == "github_reply_surface":
        steps = [
            _make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1}),
            _make_canary_step("github_issue_reply_post", {"repo": "octocat/Hello-World", "issue": 1, "body": "canary revalidation"}, risk_level="medium"),
        ]
    elif surface in {"github_read_surface", "collaboration_read_surface", "collaboration_mutate_surface"}:
        steps = [_make_canary_step("github_issue_read", {"repo": "octocat/Hello-World", "issue": 1})]
    elif surface == "deploy_mutate_surface":
        steps = [
            _make_canary_step("cloud_target_set", {"target": "staging"}),
            _make_canary_step("cloud_deploy", {"target": "staging", "artifact": "build/canary.zip"}, risk_level="medium"),
        ]
    elif surface == "deploy_verify_surface":
        steps = [_make_canary_step("cloud_target_set", {"target": "staging"})]
    elif surface == "workspace_mutate_surface":
        steps = [_make_canary_step("self_repair", {"scope": "workspace_canary"}, risk_level="medium")]
    elif surface == "workspace_read_surface":
        steps = [_make_canary_step("flow_monitor", {})]
    elif surface == "api_mutate_surface":
        steps = [_make_canary_step("store_install", {"app": "canary-app"}, risk_level="medium")]
    elif surface == "api_read_surface":
        steps = [_make_canary_step("system_status", {})]
    else:
        steps = [_make_canary_step("observe", {})]

    pattern_signature = str(dict(record.get("last_branch_shape") or {}).get("pattern_signature", "")).strip()
    return pattern_guided_steps(steps, pattern_signature) if pattern_signature else steps


def _strategy_canary_plan(strategy_name: str, record: dict[str, Any]) -> dict[str, Any]:
    last_condition_profile = dict(record.get("last_condition_profile") or {})
    steps = _strategy_canary_steps(record)
    if not last_condition_profile:
        last_condition_profile = _strategy_condition_profile({"request": f"canary revalidation for {strategy_name}", "steps": steps, "request_targets": {"items": []}, "request_decomposition": []})
    request_targets = {"items": _surface_target_items(last_condition_profile)}
    risk_level = str(last_condition_profile.get("risk_level", "") or ("medium" if any(step_allows_mutation(str(step.get("kind", ""))) for step in steps) else "low")).strip().lower()
    planner_confidence = round(
        max(
            0.42,
            min(
                0.95,
                (float(record.get("success_rate", 0.0) or 0.0) * 0.45)
                + (float(record.get("resilience_score", 0.0) or 0.0) * 0.35)
                + (float(record.get("average_outcome_quality", 0.0) or 0.0) * 0.2),
            ),
        ),
        3,
    )
    plan = {
        "request": f"canary revalidation for {strategy_name}",
        "planner_version": _current_planner_version(),
        "request_targets": request_targets,
        "request_decomposition": [],
        "steps": steps,
        "risk_level": risk_level or "low",
        "ambiguity_flags": [],
        "execution_mode": "safe",
        "smart_planner": {
            "strategy": strategy_name,
            "strategy_mode": "safe",
            "strategy_source": "self_derivation_canary",
            "reasons": ["quarantined_strategy_canary_revalidation"],
        },
        "planner_confidence": planner_confidence,
        "branch": {"id": f"canary_{strategy_name}", "reason": "quarantined_strategy_revalidation"},
    }
    current_condition = _strategy_condition_profile(plan)
    plan["survivor_strategy_guidance"] = {
        "preferred_strategy": strategy_name,
        "recovery_profile": _strategy_outcome_profile(record),
        "current_condition_signature": str(current_condition.get("signature", "")),
        "reasons": ["explicit_canary_revalidation"],
    }
    return plan


def _shape_match_summary(record: dict[str, Any], current_shape: dict[str, Any]) -> dict[str, Any]:
    current_signature = str(current_shape.get("signature", "")).strip()
    shape_profiles = dict(record.get("shape_profiles") or {})
    exact_profile = dict(shape_profiles.get(current_signature) or {})
    if exact_profile:
        run_count = int(exact_profile.get("run_count", 0) or 0)
        success_rate = float(exact_profile.get("success_rate", 0.0) or 0.0)
        recovery_rate = float(exact_profile.get("recovery_rate", 0.0) or 0.0)
        match_score = round(min(1.0, 0.55 + min(0.25, run_count * 0.05) + (success_rate * 0.15) + (recovery_rate * 0.05)), 3)
        return {
            "match_score": match_score,
            "exact_match": True,
            "matched_signature": current_signature,
            "matched_shape": dict(exact_profile.get("branch_shape") or {}),
            "run_count": run_count,
            "success_rate": round(success_rate, 3),
            "recovery_rate": round(recovery_rate, 3),
        }

    best_partial: dict[str, Any] = {}
    best_partial_score = 0.0
    for signature, raw_profile in shape_profiles.items():
        profile = dict(raw_profile or {})
        branch_shape = dict(profile.get("branch_shape") or {})
        overlap = 0.0
        if str(branch_shape.get("structure_family", "")) == str(current_shape.get("structure_family", "")):
            overlap += 0.35
        if str(branch_shape.get("pattern_signature", "")) == str(current_shape.get("pattern_signature", "")):
            overlap += 0.25
        if bool(branch_shape.get("conditional_flow", False)) == bool(current_shape.get("conditional_flow", False)):
            overlap += 0.1
        if bool(branch_shape.get("multi_target", False)) == bool(current_shape.get("multi_target", False)):
            overlap += 0.1
        if bool(branch_shape.get("mutating", False)) == bool(current_shape.get("mutating", False)):
            overlap += 0.1
        if str(branch_shape.get("dependency_depth", "")) == str(current_shape.get("dependency_depth", "")):
            overlap += 0.1
        target_family_overlap = set(str(item) for item in list(branch_shape.get("target_families", []))) & set(
            str(item) for item in list(current_shape.get("target_families", []))
        )
        overlap += min(0.15, len(target_family_overlap) * 0.05)
        if overlap <= best_partial_score:
            continue
        best_partial_score = overlap
        best_partial = {
            "matched_signature": str(signature),
            "matched_shape": branch_shape,
            "run_count": int(profile.get("run_count", 0) or 0),
            "success_rate": round(float(profile.get("success_rate", 0.0) or 0.0), 3),
            "recovery_rate": round(float(profile.get("recovery_rate", 0.0) or 0.0), 3),
        }
    return {
        "match_score": round(min(0.85, best_partial_score), 3),
        "exact_match": False,
        **best_partial,
    }


def _target_types(plan: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("type", ""))
            for item in list(dict(plan.get("request_targets", {})).get("items", []))
            if str(item.get("type", ""))
        }
    )


def _context_signature(plan: dict[str, Any]) -> str:
    reasoning = dict(plan.get("reasoning_trace", {}))
    return json.dumps(
        {
            "shape": str(reasoning.get("request_shape", "")),
            "goal": str(reasoning.get("abstract_goal", "")),
            "targets": _target_types(plan),
        },
        sort_keys=True,
    )


def _abstract_context_signature(plan: dict[str, Any]) -> str:
    abstraction = semantic_abstraction_profile(
        str(plan.get("request", "")),
        dict(plan.get("request_targets", {})),
        list(plan.get("request_decomposition", [])),
    )
    return json.dumps(
        {
            "structure_family": str(abstraction.get("structure_family", "")),
            "target_families": list(abstraction.get("target_families", [])),
            "semantic_goal": str(abstraction.get("semantic_goal", "")),
        },
        sort_keys=True,
    )


def _clone_interpretation(
    plan: dict[str, Any],
    steps: list[dict[str, Any]],
    *,
    interpretation_id: str,
    source_branch_id: str,
    mutation_operator: str,
    mutation_intensity: str,
    interpretation_kind: str,
) -> dict[str, Any]:
    cloned = deepcopy(plan)
    cloned["steps"] = [dict(step) for step in steps]
    cloned["self_derivation_interpretation"] = {
        "id": interpretation_id,
        "source_branch_id": source_branch_id,
        "mutation_operator": mutation_operator,
        "mutation_intensity": mutation_intensity,
        "kind": interpretation_kind,
    }
    return cloned


def _verification_first_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(step) for step in steps],
        key=lambda step: (
            0 if _step_role(step) == "verify" else 1,
            0 if str(step.get("risk_level", "low")) == "low" else 1 if str(step.get("risk_level", "low")) == "medium" else 2,
            -float(step.get("route_confidence", 0.0) or 0.0),
        ),
    )


def _delay_mutation_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(step) for step in steps],
        key=lambda step: (
            1 if step_allows_mutation(str(step.get("kind", ""))) else 0,
            0 if _step_role(step) == "verify" else 1,
            -float(step.get("route_confidence", 0.0) or 0.0),
        ),
    )


def _drop_high_risk_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        enumerate(steps),
        key=lambda item: (
            0 if str(item[1].get("risk_level", "low")) == "high" else 1 if str(item[1].get("risk_level", "low")) == "medium" else 2,
            0 if step_allows_mutation(str(item[1].get("kind", ""))) else 1,
            float(item[1].get("route_confidence", 0.0) or 0.0),
        ),
    )
    if not ranked:
        return [dict(step) for step in steps]
    drop_index = ranked[0][0]
    reduced = [dict(step) for idx, step in enumerate(steps) if idx != drop_index]
    return reduced or [dict(steps[0])]


def _single_target_steps(steps: list[dict[str, Any]], target_id: str) -> list[dict[str, Any]]:
    filtered = [
        dict(step)
        for step in steps
        if target_id in list(step.get("attached_targets", []))
        or not list(step.get("attached_targets", []))
        or str(step.get("kind", "")) in {"autonomy_gate", "observe"}
    ]
    return filtered or [dict(step) for step in steps[:1]]


def _strip_targets_from_last_step(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped = [dict(step) for step in steps]
    for step in reversed(stripped):
        if step.get("target"):
            step["target"] = {}
            step["precondition_state"] = "degraded"
            step["stress_injected_missing_target"] = True
            break
    return stripped


def _observe_only_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed = [dict(step) for step in steps if _step_role(step) in {"verify", "observe"}]
    return observed or [dict(step) for step in steps[:1]]


def _execute_only_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    execute = [dict(step) for step in steps if _step_role(step) in {"prepare", "mutate"}]
    return execute or [dict(step) for step in steps[-1:]]


def _reverse_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(step) for step in reversed(steps)]


def _swap_last_two(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    swapped = [dict(step) for step in steps]
    if len(swapped) >= 2:
        swapped[-2], swapped[-1] = swapped[-1], swapped[-2]
    return swapped


def _drop_first_verification(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dropped = False
    filtered: list[dict[str, Any]] = []
    for step in steps:
        if not dropped and _step_role(step) == "verify":
            dropped = True
            continue
        filtered.append(dict(step))
    return filtered or [dict(step) for step in steps[:1]]


def _prefix_only_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(steps) <= 1:
        return [dict(step) for step in steps]
    cutoff = max(1, len(steps) // 2)
    return [dict(step) for step in steps[:cutoff]]


def _suffix_only_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(steps) <= 1:
        return [dict(step) for step in steps]
    cutoff = max(1, len(steps) // 2)
    return [dict(step) for step in steps[-cutoff:]]


def _verification_then_present_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        [dict(step) for step in steps],
        key=lambda step: (
            0 if _step_role(step) == "verify" else 1 if _step_role(step) == "dispatch" else 2 if _step_role(step) == "prepare" else 3,
            0 if str(step.get("risk_level", "low")) == "low" else 1 if str(step.get("risk_level", "low")) == "medium" else 2,
            -float(step.get("route_confidence", 0.0) or 0.0),
        ),
    )
    return ranked


def _hybrid_combine_steps(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prefix = [dict(step) for step in first if _step_role(step) in {"verify", "prepare"}]
    suffix = [dict(step) for step in second if _step_role(step) not in {"verify", "prepare"}]
    combined = prefix + suffix
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in combined:
        signature = _step_signature(step)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(step)
    return deduped or [dict(step) for step in first]


def _generate_interpretations(
    primary: dict[str, Any],
    candidates: list[dict[str, Any]],
    desired_count: int = 16,
    *,
    strategy_guidance: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    interpretations: list[dict[str, Any]] = []
    seen: set[str] = set()
    strategy_guidance = dict(strategy_guidance or primary.get("survivor_strategy_guidance") or {})

    def add(plan: dict[str, Any]) -> None:
        signature = _plan_signature(plan)
        if signature in seen:
            return
        seen.add(signature)
        interpretations.append(plan)

    base_candidates = [deepcopy(primary)] + [deepcopy(candidate) for candidate in candidates]
    for index, candidate in enumerate(base_candidates):
        branch_id = str((candidate.get("branch") or {}).get("id", f"candidate_{index}"))
        add(
            _clone_interpretation(
                candidate,
                list(candidate.get("steps", [])),
                interpretation_id=f"candidate_{index}",
                source_branch_id=branch_id,
                mutation_operator="baseline_candidate",
                mutation_intensity="none",
                interpretation_kind="candidate",
            )
        )

    for index, candidate in enumerate(base_candidates):
        steps = list(candidate.get("steps", []))
        branch_id = str((candidate.get("branch") or {}).get("id", f"candidate_{index}"))
        branch_guidance = dict(candidate.get("survivor_strategy_guidance") or strategy_guidance)
        derived_interpretations: list[dict[str, Any]] = []

        def queue(plan: dict[str, Any]) -> None:
            derived_interpretations.append(plan)

        queue(
            _clone_interpretation(
                candidate,
                _verification_first_steps(steps),
                interpretation_id=f"{branch_id}_verify_first",
                source_branch_id=branch_id,
                mutation_operator="reorder_verification_first",
                mutation_intensity="low",
                interpretation_kind="mutation",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _delay_mutation_steps(steps),
                interpretation_id=f"{branch_id}_delay_mutation",
                source_branch_id=branch_id,
                mutation_operator="delay_mutation",
                mutation_intensity="medium",
                interpretation_kind="mutation",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _drop_high_risk_steps(steps),
                interpretation_id=f"{branch_id}_drop_high_risk",
                source_branch_id=branch_id,
                mutation_operator="partial_removal",
                mutation_intensity="medium",
                interpretation_kind="mutation",
            )
        )
        target_items = list(dict(candidate.get("request_targets", {})).get("items", []))
        single_target = next((str(item.get("id", "")) for item in target_items if str(item.get("type", "")) not in {"actions"} and str(item.get("id", ""))), "")
        if single_target:
            queue(
                _clone_interpretation(
                    candidate,
                    _single_target_steps(steps, single_target),
                    interpretation_id=f"{branch_id}_single_target",
                    source_branch_id=branch_id,
                    mutation_operator="target_isolation",
                    mutation_intensity="medium",
                    interpretation_kind="mutation",
                )
            )
        queue(
            _clone_interpretation(
                candidate,
                _strip_targets_from_last_step(steps),
                interpretation_id=f"{branch_id}_missing_data",
                source_branch_id=branch_id,
                mutation_operator="inject_missing_data",
                mutation_intensity="high",
                interpretation_kind="stress_variant",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _observe_only_steps(steps),
                interpretation_id=f"{branch_id}_observe_only",
                source_branch_id=branch_id,
                mutation_operator="observation_only",
                mutation_intensity="medium",
                interpretation_kind="mutation",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _execute_only_steps(steps),
                interpretation_id=f"{branch_id}_execute_only",
                source_branch_id=branch_id,
                mutation_operator="execute_only",
                mutation_intensity="high",
                interpretation_kind="mutation",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _reverse_steps(steps),
                interpretation_id=f"{branch_id}_reverse",
                source_branch_id=branch_id,
                mutation_operator="reorder_reverse",
                mutation_intensity="extreme",
                interpretation_kind="mutation",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _swap_last_two(steps),
                interpretation_id=f"{branch_id}_swap_last_two",
                source_branch_id=branch_id,
                mutation_operator="swap_last_two",
                mutation_intensity="medium",
                interpretation_kind="mutation",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _drop_first_verification(steps),
                interpretation_id=f"{branch_id}_drop_first_verify",
                source_branch_id=branch_id,
                mutation_operator="drop_first_verification",
                mutation_intensity="high",
                interpretation_kind="stress_variant",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _prefix_only_steps(steps),
                interpretation_id=f"{branch_id}_prefix_only",
                source_branch_id=branch_id,
                mutation_operator="prefix_only",
                mutation_intensity="medium",
                interpretation_kind="partial",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _suffix_only_steps(steps),
                interpretation_id=f"{branch_id}_suffix_only",
                source_branch_id=branch_id,
                mutation_operator="suffix_only",
                mutation_intensity="medium",
                interpretation_kind="partial",
            )
        )
        queue(
            _clone_interpretation(
                candidate,
                _verification_then_present_steps(steps),
                interpretation_id=f"{branch_id}_verify_then_present",
                source_branch_id=branch_id,
                mutation_operator="reorder_verify_then_present",
                mutation_intensity="medium",
                interpretation_kind="alternative_logic",
            )
        )
        derived_interpretations.sort(key=lambda item: _strategy_guided_generation_priority(item, branch_guidance), reverse=True)
        for interpretation in derived_interpretations:
            if _strategy_blocks_interpretation(interpretation, branch_guidance):
                continue
            add(interpretation)

    if len(base_candidates) >= 2:
        first = list(base_candidates[0].get("steps", []))
        second = list(base_candidates[1].get("steps", []))
        hybrid_0_1 = _clone_interpretation(
            base_candidates[0],
            _hybrid_combine_steps(first, second),
            interpretation_id="hybrid_0_1",
            source_branch_id=str((base_candidates[0].get("branch") or {}).get("id", "primary")),
            mutation_operator="hybrid_combine",
            mutation_intensity="high",
            interpretation_kind="hybrid",
        )
        hybrid_1_0 = _clone_interpretation(
            base_candidates[1],
            _hybrid_combine_steps(second, first),
            interpretation_id="hybrid_1_0",
            source_branch_id=str((base_candidates[1].get("branch") or {}).get("id", "secondary")),
            mutation_operator="hybrid_combine_reverse",
            mutation_intensity="high",
            interpretation_kind="hybrid",
        )
        for interpretation in sorted(
            [hybrid_0_1, hybrid_1_0],
            key=lambda item: _strategy_guided_generation_priority(item, strategy_guidance),
            reverse=True,
        ):
            if _strategy_blocks_interpretation(interpretation, strategy_guidance):
                continue
            add(interpretation)

    return interpretations[: max(12, desired_count)]


def _reuse_success(pattern_memory: dict[str, Any], signature: str) -> float:
    patterns = dict(pattern_memory.get("patterns") or {})
    pattern = dict(patterns.get(signature) or {})
    average_score = float(pattern.get("average_score", 0.0) or 0.0)
    survival_count = int(pattern.get("survival_count", 0) or 0)
    if survival_count <= 0:
        return 0.0
    return round(min(1.0, (average_score / 100.0) * min(1.0, survival_count / 5.0)), 3)


def _pressure_report(interpretation: dict[str, Any], pattern_memory: dict[str, Any]) -> dict[str, Any]:
    steps = list(interpretation.get("steps", []))
    decomposition = list(interpretation.get("request_decomposition", []))
    targets = dict(interpretation.get("request_targets", {}))
    ambiguity_flags = list(interpretation.get("ambiguity_flags", []))
    precheck = simulate_plan_conflicts(
        steps,
        decomposition,
        targets,
        read_only_request=bool(interpretation.get("read_only_request", False)),
    )
    simulation = simulate_plan(
        steps,
        decomposition,
        targets,
        planner_confidence=float(interpretation.get("planner_confidence", 0.0) or 0.0),
        risk_level=str(interpretation.get("risk_level", "low")),
        ambiguity_flags=ambiguity_flags,
        route_history_bias=dict(interpretation.get("route_history_bias", {})),
        precheck=precheck,
        memory_strength=str(dict(interpretation.get("memory_context", {})).get("memory_strength", "none")),
    )
    rerun = simulate_plan(
        steps,
        decomposition,
        targets,
        planner_confidence=float(interpretation.get("planner_confidence", 0.0) or 0.0),
        risk_level=str(interpretation.get("risk_level", "low")),
        ambiguity_flags=ambiguity_flags,
        route_history_bias=dict(interpretation.get("route_history_bias", {})),
        precheck=precheck,
        memory_strength=str(dict(interpretation.get("memory_context", {})).get("memory_strength", "none")),
    )
    recursion_stability = 1.0 if simulation == rerun else 0.7
    target_coverage = dict(interpretation.get("target_coverage", {}))
    coverage_ratio = float(target_coverage.get("coverage_ratio", 0.0) or 0.0)
    contradiction_penalty = min(30.0, float(precheck.get("conflict_count", 0) or 0.0) * 8.0)
    failure_rate_penalty = round((1.0 - float(simulation.get("expected_success", 0.0) or 0.0)) * 28.0, 3)
    incomplete_information_penalty = 0.0
    incomplete_information_penalty += max(0.0, 1.0 - coverage_ratio) * 16.0
    incomplete_information_penalty += sum(
        4.0
        for step in steps
        if bool(step.get("stress_injected_missing_target", False)) or str(step.get("precondition_state", "")) == "degraded"
    )
    conflicting_goal_penalty = 6.0 if "read_only_mutation_overlap" in ambiguity_flags else 0.0
    conflicting_goal_penalty += 4.0 if "mixed_intents" in ambiguity_flags else 0.0
    delay_async_penalty = 4.0 if any(str(step.get("conditional_execution_mode", "")) == "on_failure" for step in steps) and not any(_step_role(step) == "verify" for step in steps) else 0.0
    resource_penalty = max(0.0, (len(steps) - 4) * 1.5) + max(0.0, (len(list(targets.get("items", []))) - 3) * 1.0)

    pattern_signature = _abstract_pattern(steps)
    reuse_success = _reuse_success(pattern_memory, pattern_signature)
    survival_score = round(
        max(
            0.0,
            min(
                100.0,
                (float(simulation.get("expected_success", 0.0) or 0.0) * 48.0)
                + (recursion_stability * 18.0)
                + (coverage_ratio * 16.0)
                + (reuse_success * 10.0)
                - contradiction_penalty
                - failure_rate_penalty
                - incomplete_information_penalty
                - conflicting_goal_penalty
                - delay_async_penalty
                - resource_penalty,
            ),
        ),
        2,
    )
    return {
        "precheck": precheck,
        "simulation": simulation,
        "recursion_stability": recursion_stability,
        "pressure": {
            "contradiction_penalty": round(contradiction_penalty, 3),
            "failure_rate_penalty": round(failure_rate_penalty, 3),
            "incomplete_information_penalty": round(incomplete_information_penalty, 3),
            "conflicting_goal_penalty": round(conflicting_goal_penalty, 3),
            "delay_async_penalty": round(delay_async_penalty, 3),
            "resource_penalty": round(resource_penalty, 3),
            "reuse_success": reuse_success,
        },
        "survival_score": survival_score,
        "pattern_signature": pattern_signature,
        "context_signature": _context_signature(interpretation),
        "abstract_context_signature": _abstract_context_signature(interpretation),
    }


def _memory_default() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "patterns": {},
        "knowledge": [],
        "strategy_outcomes": {},
        "quarantined_strategy_outcomes": {},
        "meta_rules": [],
        "updated_utc": _utc_now(),
    }


def _reconcile_strategy_memory(memory: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    reconciled = dict(memory or {})
    strategy_outcomes = dict(reconciled.get("strategy_outcomes") or {})
    quarantined = dict(reconciled.get("quarantined_strategy_outcomes") or {})
    current_planner_version = _current_planner_version()
    current_code_version = _current_strategy_code_version()
    changed = False
    for strategy_name, raw_record in list(strategy_outcomes.items()):
        record = dict(raw_record or {})
        planner_history = list(dict.fromkeys([str(item).strip() for item in ([record.get("planner_version", "")] + list(record.get("planner_version_history", []))) if str(item).strip()]))
        code_history = list(dict.fromkeys([str(item).strip() for item in ([record.get("code_version", "")] + list(record.get("code_version_history", []))) if str(item).strip()]))
        freshness = _strategy_record_freshness(record)
        planner_generations_missed = int(current_planner_version not in planner_history and len(planner_history) >= 2)
        code_generations_missed = int(current_code_version not in code_history and len(code_history) >= 2)
        if (planner_generations_missed or code_generations_missed) and float(freshness.get("freshness_score", 0.0) or 0.0) < 0.55:
            quarantined[strategy_name] = {
                **record,
                "quarantine_reason": "version_mismatch_across_generations",
                "quarantined_utc": _utc_now(),
                "planner_generations_missed": planner_generations_missed,
                "code_generations_missed": code_generations_missed,
            }
            strategy_outcomes.pop(strategy_name, None)
            changed = True
    for strategy_name, raw_record in list(quarantined.items()):
        record = dict(raw_record or {})
        freshness = _strategy_record_freshness(record)
        days_since = freshness.get("days_since_last_run")
        if days_since is not None and float(days_since or 0.0) > 365.0 and float(freshness.get("freshness_score", 0.0) or 0.0) <= 0.12:
            quarantined.pop(strategy_name, None)
            changed = True
    reconciled["schema_version"] = max(2, int(reconciled.get("schema_version", 1) or 1))
    reconciled["strategy_outcomes"] = strategy_outcomes
    reconciled["quarantined_strategy_outcomes"] = quarantined
    return reconciled, changed


def _load_memory(cwd: str) -> dict[str, Any]:
    path = _memory_path(cwd)
    memory = _load_json(path, _memory_default())
    reconciled, changed = _reconcile_strategy_memory(memory)
    if changed:
        reconciled["updated_utc"] = _utc_now()
        _save_json(path, reconciled)
    return reconciled


def _derive_meta_rules(patterns: dict[str, Any], strategy_outcomes: dict[str, Any]) -> list[dict[str, Any]]:
    meta_rules: list[dict[str, Any]] = []
    verification_scores = [float(record.get("average_score", 0.0) or 0.0) for record in patterns.values() if str(record.get("structure", "")).startswith("verify")]
    mutate_first_scores = [float(record.get("average_score", 0.0) or 0.0) for record in patterns.values() if str(record.get("structure", "")).startswith("mutate")]
    if verification_scores and mutate_first_scores and (sum(verification_scores) / len(verification_scores)) > (sum(mutate_first_scores) / len(mutate_first_scores)):
        meta_rules.append(
            {
                "rule": "verification_first_survives_better",
                "confidence": round(min(0.99, (sum(verification_scores) / len(verification_scores)) / 100.0), 3),
                "evidence": {
                    "verification_first_average": round(sum(verification_scores) / len(verification_scores), 2),
                    "mutate_first_average": round(sum(mutate_first_scores) / len(mutate_first_scores), 2),
                },
            }
        )

    for strategy_name, raw_record in strategy_outcomes.items():
        record = dict(raw_record or {})
        run_count = int(record.get("run_count", 0) or 0)
        if run_count < 2:
            continue
        freshness = _strategy_record_freshness(record)
        freshness_score = float(freshness.get("freshness_score", 0.45) or 0.45)
        success_rate = float(record.get("success_rate", 0.0) or 0.0)
        failure_rate = float(record.get("failure_rate", 0.0) or 0.0)
        recovery_rate = float(record.get("recovery_rate", 0.0) or 0.0)
        contradiction_hold_rate = float(record.get("contradiction_hold_rate", 0.0) or 0.0)
        average_quality = float(record.get("average_outcome_quality", 0.0) or 0.0)
        strategy_name = str(strategy_name).strip()
        if not strategy_name:
            continue
        if success_rate >= 0.72 and contradiction_hold_rate <= 0.18:
            meta_rules.append(
                {
                    "rule": f"strategy_{strategy_name}_execution_proven",
                    "confidence": round(min(0.99, ((success_rate * 0.65) + (average_quality * 0.35)) * freshness_score), 3),
                    "strategy": strategy_name,
                    "evidence": {
                        "run_count": run_count,
                        "success_rate": round(success_rate, 3),
                        "average_outcome_quality": round(average_quality, 3),
                        "recovery_rate": round(recovery_rate, 3),
                        "freshness_score": round(freshness_score, 3),
                    },
                }
            )
        if recovery_rate >= 0.35 and failure_rate <= 0.45:
            meta_rules.append(
                {
                    "rule": f"strategy_{strategy_name}_recovery_supported",
                    "confidence": round(min(0.95, ((recovery_rate * 0.7) + (average_quality * 0.25)) * freshness_score), 3),
                    "strategy": strategy_name,
                    "evidence": {
                        "run_count": run_count,
                        "recovery_rate": round(recovery_rate, 3),
                        "failure_rate": round(failure_rate, 3),
                        "freshness_score": round(freshness_score, 3),
                    },
                }
            )
        if failure_rate >= 0.45 and recovery_rate >= 0.35 and contradiction_hold_rate < 0.25:
            meta_rules.append(
                {
                    "rule": f"strategy_{strategy_name}_fragile_but_recoverable",
                    "confidence": round(min(0.95, ((failure_rate * 0.35) + (recovery_rate * 0.45) + (average_quality * 0.15)) * freshness_score), 3),
                    "strategy": strategy_name,
                    "evidence": {
                        "run_count": run_count,
                        "failure_rate": round(failure_rate, 3),
                        "recovery_rate": round(recovery_rate, 3),
                        "contradiction_hold_rate": round(contradiction_hold_rate, 3),
                        "freshness_score": round(freshness_score, 3),
                    },
                }
            )
        if failure_rate >= 0.45:
            meta_rules.append(
                {
                    "rule": f"strategy_{strategy_name}_execution_fragile",
                    "confidence": round(min(0.99, ((failure_rate * 0.6) + (contradiction_hold_rate * 0.25)) * freshness_score), 3),
                    "strategy": strategy_name,
                    "evidence": {
                        "run_count": run_count,
                        "failure_rate": round(failure_rate, 3),
                        "contradiction_hold_rate": round(contradiction_hold_rate, 3),
                        "freshness_score": round(freshness_score, 3),
                    },
                }
            )
        if failure_rate >= 0.45 and (recovery_rate < 0.35 or contradiction_hold_rate >= 0.25):
            meta_rules.append(
                {
                    "rule": f"strategy_{strategy_name}_fragile_and_unsafe",
                    "confidence": round(min(0.99, ((failure_rate * 0.55) + (max(0.0, 0.35 - recovery_rate) * 0.5) + (contradiction_hold_rate * 0.25)) * freshness_score), 3),
                    "strategy": strategy_name,
                    "evidence": {
                        "run_count": run_count,
                        "failure_rate": round(failure_rate, 3),
                        "recovery_rate": round(recovery_rate, 3),
                        "contradiction_hold_rate": round(contradiction_hold_rate, 3),
                        "freshness_score": round(freshness_score, 3),
                    },
                }
            )
    return meta_rules


def _update_memory(cwd: str, survivors: list[dict[str, Any]]) -> dict[str, Any]:
    memory = _load_memory(cwd)
    patterns = dict(memory.get("patterns") or {})
    for survivor in survivors:
        signature = str(survivor.get("abstract_pattern", ""))
        if not signature:
            continue
        record = dict(patterns.get(signature) or {})
        contexts = list(record.get("contexts") or [])
        context_signature = str(survivor.get("context_signature", ""))
        if context_signature and context_signature not in contexts:
            contexts.append(context_signature)
        abstract_contexts = list(record.get("abstract_contexts") or [])
        abstract_context_signature = str(survivor.get("abstract_context_signature", ""))
        if abstract_context_signature and abstract_context_signature not in abstract_contexts:
            abstract_contexts.append(abstract_context_signature)
        validated_abstract_contexts = list(record.get("validated_abstract_contexts") or [])
        if bool(survivor.get("cross_context_validated", False)) and abstract_context_signature and abstract_context_signature not in validated_abstract_contexts:
            validated_abstract_contexts.append(abstract_context_signature)
        survival_count = int(record.get("survival_count", 0) or 0) + 1
        previous_average = float(record.get("average_score", 0.0) or 0.0)
        score = float(survivor.get("survival_score", 0.0) or 0.0)
        average_score = round(((previous_average * (survival_count - 1)) + score) / max(1, survival_count), 2)
        failure_conditions = list(record.get("failure_conditions") or [])
        for issue in list(dict(survivor.get("precheck") or {}).get("issues") or []):
            code = str(issue.get("code", ""))
            if code and code not in failure_conditions:
                failure_conditions.append(code)
        validated_context_count = len(validated_abstract_contexts)
        cross_context_score = round(
            min(
                1.0,
                (average_score / 100.0) * 0.55
                + min(0.25, validated_context_count * 0.11)
                + min(0.2, len(abstract_contexts) * 0.06),
            ),
            3,
        )
        patterns[signature] = {
            "pattern_signature": signature,
            "survival_count": survival_count,
            "average_score": average_score,
            "last_score": score,
            "contexts": contexts[-10:],
            "abstract_contexts": abstract_contexts[-10:],
            "validated_abstract_contexts": validated_abstract_contexts[-10:],
            "context_range": len(contexts[-10:]),
            "validated_context_count": validated_context_count,
            "cross_context_score": cross_context_score,
            "failure_conditions": failure_conditions[-10:],
            "structure": str(survivor.get("abstract_pattern", "")),
            "source_branch_ids": list(dict.fromkeys((list(record.get("source_branch_ids") or []) + [str(survivor.get("source_branch_id", ""))])))[-6:],
        }

    knowledge: list[dict[str, Any]] = []
    for signature, record in sorted(patterns.items(), key=lambda item: (-float(item[1].get("average_score", 0.0) or 0.0), -int(item[1].get("survival_count", 0) or 0)))[:6]:
        context_range = int(record.get("context_range", 0) or 0)
        validated_context_count = int(record.get("validated_context_count", 0) or 0)
        cross_context_score = float(record.get("cross_context_score", 0.0) or 0.0)
        confidence = round(
            min(
                0.99,
                max(
                    cross_context_score,
                    (float(record.get("average_score", 0.0) or 0.0) / 100.0) * (0.65 + min(0.2, context_range * 0.08) + min(0.15, validated_context_count * 0.06)),
                ),
            ),
            3,
        )
        knowledge.append(
            {
                "rule": f"Prefer structure `{record.get('structure', signature)}` when similar bounded requests reappear.",
                "conditions": f"context_range>={max(1, context_range)}; validated_contexts>={max(1, validated_context_count)}; failure_conditions={','.join(record.get('failure_conditions', [])) or 'none'}",
                "confidence": confidence,
                "pattern_signature": signature,
                "cross_context_score": cross_context_score,
            }
        )

    strategy_outcomes = dict(memory.get("strategy_outcomes") or {})
    memory["patterns"] = patterns
    memory["knowledge"] = knowledge
    memory["strategy_outcomes"] = strategy_outcomes
    memory["meta_rules"] = _derive_meta_rules(patterns, strategy_outcomes)
    memory["updated_utc"] = _utc_now()
    put_state_store(cwd, "self_derivation_memory", memory)
    _save_json(_memory_path(cwd), memory)
    return memory


def _intensity_rank(value: str) -> int:
    return {
        "none": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
        "extreme": 4,
    }.get(str(value or "").strip().lower(), 5)


def _strategy_blocks_interpretation(plan: dict[str, Any], strategy_guidance: dict[str, Any]) -> bool:
    derivation = dict(plan.get("self_derivation_interpretation") or {})
    intensity = str(derivation.get("mutation_intensity", "none")).strip().lower()
    kind = str(derivation.get("kind", "")).strip().lower()
    suppressed = {
        str(item).strip().lower()
        for item in list(strategy_guidance.get("suppressed_mutation_intensities", []))
        if str(item).strip()
    }
    if intensity in suppressed and kind != "candidate":
        return True
    return False


def _strategy_defaults(strategy: str) -> dict[str, Any]:
    normalized = str(strategy or "").strip().lower()
    if normalized == "verification_first":
        return {
            "preferred_mode": "deliberate",
            "preferred_branch_types": ["verification_first", "evidence_first"],
            "preferred_mutation_intensity": "low",
            "preferred_mutation_operators": ["reorder_verification_first", "delay_mutation", "reorder_verify_then_present"],
            "suppressed_mutation_intensities": ["extreme"],
        }
    if normalized == "dependency_aware":
        return {
            "preferred_mode": "deliberate",
            "preferred_branch_types": ["evidence_first", "verification_first"],
            "preferred_mutation_intensity": "medium",
            "preferred_mutation_operators": ["reorder_verify_then_present", "delay_mutation", "partial_removal"],
            "suppressed_mutation_intensities": ["extreme"],
        }
    if normalized == "target_isolated":
        return {
            "preferred_mode": "exploratory",
            "preferred_branch_types": ["single_target", "verification_first"],
            "preferred_mutation_intensity": "medium",
            "preferred_mutation_operators": ["target_isolation", "reorder_verification_first", "swap_last_two"],
            "suppressed_mutation_intensities": ["extreme"],
        }
    if normalized == "conservative":
        return {
            "preferred_mode": "safe",
            "preferred_branch_types": ["observation_only", "minimal_safe", "conservative_execution"],
            "preferred_mutation_intensity": "low",
            "preferred_mutation_operators": ["reorder_verification_first", "observation_only", "partial_removal"],
            "suppressed_mutation_intensities": ["high", "extreme"],
        }
    return {
        "preferred_mode": "",
        "preferred_branch_types": [],
        "preferred_mutation_intensity": "",
        "preferred_mutation_operators": [],
        "suppressed_mutation_intensities": [],
    }


def _strategy_outcome_profile(record: dict[str, Any]) -> str:
    failure_rate = float(record.get("failure_rate", 0.0) or 0.0)
    recovery_rate = float(record.get("recovery_rate", 0.0) or 0.0)
    contradiction_hold_rate = float(record.get("contradiction_hold_rate", 0.0) or 0.0)
    success_rate = float(record.get("success_rate", 0.0) or 0.0)
    average_outcome_quality = float(record.get("average_outcome_quality", 0.0) or 0.0)
    if failure_rate >= 0.45 and recovery_rate >= 0.35 and contradiction_hold_rate < 0.25:
        return "fragile_but_recoverable"
    if failure_rate >= 0.45 and (recovery_rate < 0.35 or contradiction_hold_rate >= 0.25):
        return "fragile_and_unsafe"
    if success_rate >= 0.72 and contradiction_hold_rate <= 0.18 and average_outcome_quality >= 0.62:
        return "proven"
    if recovery_rate >= 0.35 and failure_rate <= 0.45:
        return "recovery_supported"
    return "neutral"


def _candidate_strategy_outcome_guidance(
    strategy_name: str,
    record: dict[str, Any],
    *,
    relevance_bonus: float,
    shape_match: dict[str, Any] | None = None,
    condition_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    defaults = _strategy_defaults(strategy_name)
    profile = _strategy_outcome_profile(record)
    freshness = _strategy_record_freshness(record, condition_profile=condition_profile)
    freshness_score = float(freshness.get("freshness_score", 0.8) or 0.8)
    shape_match = dict(shape_match or {})
    shape_match_score = float(shape_match.get("match_score", 0.0) or 0.0)
    resilience_score = float(record.get("resilience_score", 0.0) or 0.0)
    success_rate = float(record.get("success_rate", 0.0) or 0.0)
    recovery_rate = float(record.get("recovery_rate", 0.0) or 0.0)
    failure_rate = float(record.get("failure_rate", 0.0) or 0.0)
    contradiction_hold_rate = float(record.get("contradiction_hold_rate", 0.0) or 0.0)
    base_memory_score = (
        resilience_score
        + (success_rate * 0.08)
        + (recovery_rate * 0.04)
        - (failure_rate * 0.06)
        - (contradiction_hold_rate * 0.05)
    )
    outcome_score = round(
        max(
            0.0,
            min(
                1.0,
                (base_memory_score * freshness_score) + relevance_bonus + min(0.25, shape_match_score * 0.2),
            ),
        ),
        3,
    )
    defaults["preferred_mode"] = str(defaults.get("preferred_mode", "")).strip()
    if profile == "fragile_but_recoverable":
        defaults["preferred_mode"] = "safe"
        defaults["preferred_mutation_intensity"] = "low"
        defaults["suppressed_mutation_intensities"] = list(
            dict.fromkeys(list(defaults.get("suppressed_mutation_intensities", [])) + ["high", "extreme"])
        )
    elif profile == "fragile_and_unsafe":
        conservative_defaults = _strategy_defaults("conservative")
        defaults = {
            **conservative_defaults,
            "preferred_strategy": "conservative",
        }
    return {
        "strategy": str(defaults.pop("preferred_strategy", strategy_name)).strip().lower(),
        "profile": profile,
        "outcome_score": outcome_score,
        "defaults": defaults,
        "record": {
            "run_count": int(record.get("run_count", 0) or 0),
            "success_rate": round(success_rate, 3),
            "failure_rate": round(failure_rate, 3),
            "recovery_rate": round(recovery_rate, 3),
            "contradiction_hold_rate": round(contradiction_hold_rate, 3),
            "average_outcome_quality": round(float(record.get("average_outcome_quality", 0.0) or 0.0), 3),
            "resilience_score": round(resilience_score, 3),
            "freshness_score": round(freshness_score, 3),
            "days_since_last_run": freshness.get("days_since_last_run"),
            "version_alignment_score": round(float(freshness.get("version_alignment_score", 1.0) or 1.0), 3),
            "planner_version_match": bool(freshness.get("planner_version_match", True)),
            "code_version_match": bool(freshness.get("code_version_match", True)),
            "record_planner_version": str(freshness.get("record_planner_version", "")),
            "record_code_version": str(freshness.get("record_code_version", "")),
            "shape_match_score": round(shape_match_score, 3),
            "shape_match_exact": bool(shape_match.get("exact_match", False)),
            "shape_match_signature": str(shape_match.get("matched_signature", "")),
            "condition_match_score": round(float(freshness.get("condition_match_score", 0.0) or 0.0), 3),
            "condition_match_exact": bool(freshness.get("condition_match_exact", False)),
            "condition_signature": str(freshness.get("condition_signature", "")),
            "subsystem_surface": str(freshness.get("subsystem_surface", "")),
        },
    }


def _strategy_guided_generation_priority(plan: dict[str, Any], strategy_guidance: dict[str, Any]) -> tuple[Any, ...]:
    derivation = dict(plan.get("self_derivation_interpretation") or {})
    operator = str(derivation.get("mutation_operator", "")).strip().lower()
    intensity = str(derivation.get("mutation_intensity", "none")).strip().lower()
    kind = str(derivation.get("kind", "")).strip().lower()
    preferred_intensity = str(strategy_guidance.get("preferred_mutation_intensity", "")).strip().lower()
    preferred_operators = {
        str(item).strip().lower()
        for item in list(strategy_guidance.get("preferred_mutation_operators", []))
        if str(item).strip()
    }
    strategy = str(strategy_guidance.get("preferred_strategy", "")).strip().lower()
    blocked = _strategy_blocks_interpretation(plan, strategy_guidance)
    kind_priority = {
        "candidate": 4,
        "mutation": 3,
        "alternative_logic": 2,
        "partial": 1,
        "hybrid": 0,
        "stress_variant": -1,
    }.get(kind, 0)
    score = 0
    if kind == "candidate":
        score += 12
    if operator in preferred_operators:
        score += 6
    if preferred_intensity and intensity == preferred_intensity:
        score += 4
    if strategy == "verification_first" and operator in {"reorder_verification_first", "reorder_verify_then_present", "delay_mutation"}:
        score += 2
    if strategy == "dependency_aware" and operator in {"reorder_verify_then_present", "delay_mutation", "partial_removal"}:
        score += 2
    if strategy == "target_isolated" and operator in {"target_isolation", "reorder_verification_first"}:
        score += 2
    if strategy == "conservative" and kind == "stress_variant":
        score -= 4
    if blocked:
        score -= 10
    return (
        score,
        kind_priority,
        1 if operator in preferred_operators else 0,
        1 if preferred_intensity and intensity == preferred_intensity else 0,
        -_intensity_rank(intensity),
        operator,
    )


def derive_interpretations(
    cwd: str,
    request: str,
    primary_plan: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    desired_count: int = 16,
) -> dict[str, Any]:
    pattern_memory = _load_memory(cwd)
    strategy_guidance = dict(primary_plan.get("survivor_strategy_guidance") or survivor_strategy_guidance(cwd, primary_plan))
    interpretations = _generate_interpretations(primary_plan, candidates, desired_count=desired_count, strategy_guidance=strategy_guidance)
    evaluated: list[dict[str, Any]] = []
    for interpretation in interpretations:
        report = _pressure_report(interpretation, pattern_memory)
        derivation = dict(interpretation.get("self_derivation_interpretation") or {})
        abstract_context_signature = str(report.get("abstract_context_signature", ""))
        current_pattern = dict(dict(pattern_memory.get("patterns") or {}).get(str(report.get("pattern_signature", ""))) or {})
        known_contexts = set(str(item) for item in list(current_pattern.get("validated_abstract_contexts") or []) if str(item))
        known_contexts.add(abstract_context_signature)
        cross_context_validated = (
            float(report.get("survival_score", 0.0) or 0.0) >= 55.0
            and int(dict(report.get("precheck") or {}).get("conflict_count", 0) or 0) <= 1
            and float(dict(report.get("simulation") or {}).get("expected_success", 0.0) or 0.0) >= 0.52
        )
        evaluated.append(
            {
                "id": str(derivation.get("id", "")),
                "source_branch_id": str(derivation.get("source_branch_id", "")),
                "mutation_operator": str(derivation.get("mutation_operator", "")),
                "mutation_intensity": str(derivation.get("mutation_intensity", "")),
                "kind": str(derivation.get("kind", "")),
                "survival_score": float(report.get("survival_score", 0.0) or 0.0),
                "predicted_risk": str(dict(report.get("simulation") or {}).get("predicted_risk", "")),
                "expected_success": float(dict(report.get("simulation") or {}).get("expected_success", 0.0) or 0.0),
                "conflict_count": int(dict(report.get("precheck") or {}).get("conflict_count", 0) or 0),
                "abstract_pattern": str(report.get("pattern_signature", "")),
                "context_signature": str(report.get("context_signature", "")),
                "pressure": dict(report.get("pressure") or {}),
                "precheck": dict(report.get("precheck") or {}),
                "simulation": dict(report.get("simulation") or {}),
                "abstract_context_signature": abstract_context_signature,
                "cross_context_validated": cross_context_validated,
                "cross_context_validation_count": len(known_contexts),
            }
        )

    evaluated.sort(
        key=lambda item: (
            -float(item.get("survival_score", 0.0) or 0.0),
            -float(item.get("expected_success", 0.0) or 0.0),
            int(item.get("conflict_count", 0) or 0),
        )
    )
    survivors = [item for item in evaluated if float(item.get("survival_score", 0.0) or 0.0) >= 45.0][:5]
    if not survivors and evaluated:
        survivors = evaluated[:1]
    memory = _update_memory(cwd, survivors)
    recommended_branch_id = str((survivors[0] if survivors else {}).get("source_branch_id", "")) or str(((primary_plan.get("branch") or {}).get("id", "primary")))
    generated_intensity_counts: dict[str, int] = {}
    for interpretation in interpretations:
        intensity = str(dict(interpretation.get("self_derivation_interpretation") or {}).get("mutation_intensity", "none")).strip().lower() or "none"
        generated_intensity_counts[intensity] = int(generated_intensity_counts.get(intensity, 0) or 0) + 1
    report = {
        "ok": True,
        "generated_utc": _utc_now(),
        "request": request,
        "generated_count": len(evaluated),
        "survivor_count": len(survivors),
        "desired_count": max(12, desired_count),
        "recommended_branch_id": recommended_branch_id,
        "top_survivors": survivors,
        "generated_intensity_counts": generated_intensity_counts,
        "strategy_guidance": strategy_guidance,
        "knowledge": list(memory.get("knowledge") or []),
        "meta_rules": list(memory.get("meta_rules") or []),
        "pattern_count": len(dict(memory.get("patterns") or {})),
        "strategy_outcome_count": len(dict(memory.get("strategy_outcomes") or {})),
        "memory_path": str(_memory_path(cwd)),
    }
    put_state_store(cwd, "self_derivation_latest", report)
    _save_json(_latest_path(cwd), report)
    flush_state_writes(paths=[_memory_path(cwd), _latest_path(cwd)])
    return report


def self_derivation_status(cwd: str) -> dict[str, Any]:
    latest = _load_json(_latest_path(cwd), {})
    memory = _load_memory(cwd)
    patterns = dict(memory.get("patterns") or {})
    strategy_outcomes = dict(memory.get("strategy_outcomes") or {})
    quarantined_strategy_outcomes = dict(memory.get("quarantined_strategy_outcomes") or {})
    strategy_freshness_total = 0.0
    version_mismatch_count = 0
    stale_strategy_count = 0
    fresh_strategy_count = 0
    branch_shape_profile_count = 0
    condition_profile_count = 0
    condition_surface_counts: dict[str, int] = {}
    surface_freshness_profiles: dict[str, dict[str, Any]] = {}
    freshest_strategy: dict[str, Any] = {}
    stalest_strategy: dict[str, Any] = {}
    recovery_profiles: dict[str, int] = {}
    latest_revalidation: dict[str, Any] = {}
    for strategy_name, raw_record in strategy_outcomes.items():
        record = dict(raw_record or {})
        freshness = _strategy_record_freshness(record)
        freshness_score = float(freshness.get("freshness_score", 0.0) or 0.0)
        recovery_profile = _strategy_outcome_profile(record)
        recovery_profiles[recovery_profile] = int(recovery_profiles.get(recovery_profile, 0) or 0) + 1
        strategy_freshness_total += freshness_score
        if freshness_score >= 0.75:
            fresh_strategy_count += 1
        if freshness_score < 0.4:
            stale_strategy_count += 1
        if not bool(freshness.get("planner_version_match", True)) or not bool(freshness.get("code_version_match", True)):
            version_mismatch_count += 1
        freshest_candidate = {
            "strategy": str(strategy_name),
            "freshness_score": round(freshness_score, 3),
            "recovery_profile": recovery_profile,
            "version_alignment_score": round(float(freshness.get("version_alignment_score", 1.0) or 1.0), 3),
        }
        if not freshest_strategy or freshness_score > float(freshest_strategy.get("freshness_score", 0.0) or 0.0):
            freshest_strategy = freshest_candidate
        if not stalest_strategy or freshness_score < float(stalest_strategy.get("freshness_score", 1.0) or 1.0):
            stalest_strategy = freshest_candidate
        branch_shape_profile_count += len(dict(record.get("shape_profiles") or {}))
        condition_profiles = dict(record.get("condition_profiles") or {})
        if not condition_profiles and dict(record.get("last_condition_profile") or {}):
            condition_profiles = {
                str(dict(record.get("last_condition_profile") or {}).get("signature", "") or "last_condition"): {
                    "condition_profile": dict(record.get("last_condition_profile") or {})
                }
            }
        condition_profile_count += len(condition_profiles)
        for raw_condition in condition_profiles.values():
            condition = dict(raw_condition or {})
            condition_profile = dict(condition.get("condition_profile") or record.get("last_condition_profile") or {})
            surface = str(condition_profile.get("subsystem_surface", "") or "general_surface")
            condition_surface_counts[surface] = int(condition_surface_counts.get(surface, 0) or 0) + 1
            condition_freshness = _strategy_record_freshness(record, condition_profile=condition_profile)
            _accumulate_surface_freshness(
                surface_freshness_profiles,
                surface=surface,
                freshness=condition_freshness,
                recovery_profile=recovery_profile,
                quarantined=False,
            )
        last_revalidation_utc = _parse_utc(str(record.get("last_revalidation_utc", "") or ""))
        if last_revalidation_utc and (
            not latest_revalidation
            or last_revalidation_utc > _parse_utc(str(latest_revalidation.get("last_revalidation_utc", "") or "1970-01-01T00:00:00+00:00"))
        ):
            latest_revalidation = {
                "strategy": str(strategy_name),
                "last_revalidation_utc": last_revalidation_utc.isoformat(),
                "revalidation_status": str(record.get("revalidation_status", "") or "active"),
                "revalidation_count": int(record.get("revalidation_count", 0) or 0),
            }
    for raw_record in quarantined_strategy_outcomes.values():
        record = dict(raw_record or {})
        branch_shape_profile_count += len(dict(record.get("shape_profiles") or {}))
        condition_profiles = dict(record.get("condition_profiles") or {})
        if not condition_profiles and dict(record.get("last_condition_profile") or {}):
            condition_profiles = {
                str(dict(record.get("last_condition_profile") or {}).get("signature", "") or "last_condition"): {
                    "condition_profile": dict(record.get("last_condition_profile") or {})
                }
            }
        recovery_profile = _strategy_outcome_profile(record)
        condition_profile_count += len(condition_profiles)
        for raw_condition in condition_profiles.values():
            condition = dict(raw_condition or {})
            condition_profile = dict(condition.get("condition_profile") or record.get("last_condition_profile") or {})
            surface = str(condition_profile.get("subsystem_surface", "") or "general_surface")
            condition_surface_counts[surface] = int(condition_surface_counts.get(surface, 0) or 0) + 1
            condition_freshness = _strategy_record_freshness(record, condition_profile=condition_profile)
            _accumulate_surface_freshness(
                surface_freshness_profiles,
                surface=surface,
                freshness=condition_freshness,
                recovery_profile=recovery_profile,
                quarantined=True,
            )
        last_revalidation_utc = _parse_utc(str(record.get("last_revalidation_utc", "") or ""))
        if last_revalidation_utc and (
            not latest_revalidation
            or last_revalidation_utc > _parse_utc(str(latest_revalidation.get("last_revalidation_utc", "") or "1970-01-01T00:00:00+00:00"))
        ):
            latest_revalidation = {
                "strategy": str(record.get("strategy", "")),
                "last_revalidation_utc": last_revalidation_utc.isoformat(),
                "revalidation_status": str(record.get("revalidation_status", "") or "kept_quarantined"),
                "revalidation_count": int(record.get("revalidation_count", 0) or 0),
            }
    revalidation_ready_count = 0
    for strategy_name, raw_record in quarantined_strategy_outcomes.items():
        record = dict(raw_record or {})
        canary_plan = _strategy_canary_plan(str(strategy_name), record)
        current_condition = _strategy_condition_profile(canary_plan)
        freshness = _strategy_record_freshness(record, condition_profile=current_condition)
        shape_match = _shape_match_summary(record, _branch_shape_profile(canary_plan))
        if float(freshness.get("freshness_score", 0.0) or 0.0) >= 0.45 and (
            float(shape_match.get("match_score", 0.0) or 0.0) >= 0.3 or float(freshness.get("condition_match_score", 0.0) or 0.0) >= 0.45
        ):
            revalidation_ready_count += 1
    best_pattern = {}
    if patterns:
        best_pattern = dict(
            sorted(
                patterns.values(),
                key=lambda item: (-float(item.get("average_score", 0.0) or 0.0), -int(item.get("survival_count", 0) or 0)),
            )[0]
        )
    status = {
        "ok": True,
        "latest_path": str(_latest_path(cwd)),
        "memory_path": str(_memory_path(cwd)),
        "latest": latest,
        "pattern_count": len(patterns),
        "knowledge_count": len(list(memory.get("knowledge") or [])),
        "meta_rule_count": len(list(memory.get("meta_rules") or [])),
        "strategy_outcome_count": len(strategy_outcomes),
        "quarantined_strategy_count": len(quarantined_strategy_outcomes),
        "validated_pattern_count": sum(1 for item in patterns.values() if int(dict(item).get("validated_context_count", 0) or 0) > 0),
        "strategy_freshness_score": round(strategy_freshness_total / max(1, len(strategy_outcomes)), 3) if strategy_outcomes else 0.0,
        "fresh_strategy_count": fresh_strategy_count,
        "stale_strategy_count": stale_strategy_count,
        "version_mismatch_count": version_mismatch_count,
        "revalidation_ready_count": revalidation_ready_count,
        "branch_shape_profile_count": branch_shape_profile_count,
        "condition_profile_count": condition_profile_count,
        "condition_surface_counts": condition_surface_counts,
        "surface_freshness_profiles": {
            str(surface): {
                **dict(profile),
                "recovery_profiles": dict(profile.get("recovery_profiles") or {}),
            }
            for surface, profile in sorted(surface_freshness_profiles.items())
        },
        "top_recovery_profile": max(recovery_profiles.items(), key=lambda item: item[1])[0] if recovery_profiles else "neutral",
        "recovery_profiles": recovery_profiles,
        "freshest_strategy": freshest_strategy,
        "stalest_strategy": stalest_strategy,
        "latest_revalidation": latest_revalidation,
        "planner_version": _current_planner_version(),
        "code_version": _current_strategy_code_version(),
        "best_pattern": best_pattern,
    }
    flush_state_writes(paths=[_memory_path(cwd), _latest_path(cwd)])
    return status


def self_derivation_revalidate(cwd: str, *, strategy: str = "", limit: int = 3) -> dict[str, Any]:
    memory = _load_memory(cwd)
    strategy_outcomes = dict(memory.get("strategy_outcomes") or {})
    quarantined = dict(memory.get("quarantined_strategy_outcomes") or {})
    selected: list[tuple[str, dict[str, Any]]] = []
    requested_strategy = str(strategy or "").strip().lower()
    for strategy_name, raw_record in quarantined.items():
        if requested_strategy and str(strategy_name).strip().lower() != requested_strategy:
            continue
        selected.append((str(strategy_name), dict(raw_record or {})))
    selected.sort(
        key=lambda item: (
            -float(dict(item[1]).get("average_outcome_quality", 0.0) or 0.0),
            -int(dict(item[1]).get("run_count", 0) or 0),
            str(item[0]),
        )
    )
    attempted = selected[: max(1, int(limit or 1))] if selected else []
    evaluations: list[dict[str, Any]] = []
    restored_count = 0
    kept_quarantined_count = 0
    now_utc = _utc_now()
    for strategy_name, record in attempted:
        canary_plan = _strategy_canary_plan(strategy_name, record)
        precheck = simulate_plan_conflicts(
            list(canary_plan.get("steps", [])),
            list(canary_plan.get("request_decomposition", [])),
            dict(canary_plan.get("request_targets", {})),
            read_only_request=False,
        )
        simulation = simulate_plan(
            list(canary_plan.get("steps", [])),
            list(canary_plan.get("request_decomposition", [])),
            dict(canary_plan.get("request_targets", {})),
            planner_confidence=float(canary_plan.get("planner_confidence", 0.65) or 0.65),
            risk_level=str(canary_plan.get("risk_level", "low") or "low"),
            ambiguity_flags=list(canary_plan.get("ambiguity_flags", [])),
            route_history_bias={},
            precheck=precheck,
            memory_strength="strong",
        )
        current_condition = _strategy_condition_profile(canary_plan)
        freshness = _strategy_record_freshness(record, condition_profile=current_condition)
        shape_match = _shape_match_summary(record, _branch_shape_profile(canary_plan))
        guidance = _candidate_strategy_outcome_guidance(
            strategy_name,
            record,
            relevance_bonus=0.12,
            shape_match=shape_match,
            condition_profile=current_condition,
        )
        profile = str(guidance.get("profile", "neutral") or "neutral")
        pass_threshold = (
            int(precheck.get("conflict_count", 0) or 0) <= 1
            and float(simulation.get("expected_success", 0.0) or 0.0) >= 0.58
            and float(guidance.get("outcome_score", 0.0) or 0.0) >= 0.62
            and profile != "fragile_and_unsafe"
            and (
                float(shape_match.get("match_score", 0.0) or 0.0) >= 0.3
                or float(freshness.get("condition_match_score", 0.0) or 0.0) >= 0.45
            )
        )
        updated_record = dict(record)
        updated_record["planner_version"] = _current_planner_version()
        updated_record["code_version"] = _current_strategy_code_version()
        updated_record["planner_version_history"] = list(
            dict.fromkeys(
                [str(item).strip() for item in list(updated_record.get("planner_version_history", [])) if str(item).strip()]
                + [_current_planner_version()]
            )
        )[-6:]
        updated_record["code_version_history"] = list(
            dict.fromkeys(
                [str(item).strip() for item in list(updated_record.get("code_version_history", [])) if str(item).strip()]
                + [_current_strategy_code_version()]
            )
        )[-6:]
        updated_record["last_revalidation_utc"] = now_utc
        updated_record["revalidation_count"] = int(updated_record.get("revalidation_count", 0) or 0) + 1
        updated_record["last_revalidation_result"] = {
            "ok": bool(pass_threshold),
            "profile": profile,
            "outcome_score": round(float(guidance.get("outcome_score", 0.0) or 0.0), 3),
            "expected_success": round(float(simulation.get("expected_success", 0.0) or 0.0), 3),
            "conflict_count": int(precheck.get("conflict_count", 0) or 0),
            "shape_match_score": round(float(shape_match.get("match_score", 0.0) or 0.0), 3),
            "condition_match_score": round(float(freshness.get("condition_match_score", 0.0) or 0.0), 3),
        }
        if pass_threshold:
            updated_record["revalidation_status"] = "restored"
            updated_record["restored_utc"] = now_utc
            updated_record.pop("quarantine_reason", None)
            updated_record.pop("quarantined_utc", None)
            updated_record.pop("planner_generations_missed", None)
            updated_record.pop("code_generations_missed", None)
            strategy_outcomes[strategy_name] = updated_record
            quarantined.pop(strategy_name, None)
            restored_count += 1
        else:
            updated_record["revalidation_status"] = "kept_quarantined"
            quarantined[strategy_name] = updated_record
            kept_quarantined_count += 1
        evaluations.append(
            {
                "strategy": strategy_name,
                "ok": bool(pass_threshold),
                "profile": profile,
                "expected_success": round(float(simulation.get("expected_success", 0.0) or 0.0), 3),
                "predicted_risk": str(simulation.get("predicted_risk", "")),
                "conflict_count": int(precheck.get("conflict_count", 0) or 0),
                "shape_match_score": round(float(shape_match.get("match_score", 0.0) or 0.0), 3),
                "condition_match_score": round(float(freshness.get("condition_match_score", 0.0) or 0.0), 3),
                "subsystem_surface": str(current_condition.get("subsystem_surface", "")),
                "reason": "canary_restored" if pass_threshold else "canary_kept_quarantined",
            }
        )
    memory["strategy_outcomes"] = strategy_outcomes
    memory["quarantined_strategy_outcomes"] = quarantined
    memory["meta_rules"] = _derive_meta_rules(dict(memory.get("patterns") or {}), strategy_outcomes)
    memory["updated_utc"] = _utc_now()
    put_state_store(cwd, "self_derivation_memory", memory)
    _save_json(_memory_path(cwd), memory)
    recommended_action = "Observe strategy memory." if not attempted else (
        "Use restored strategy memory on real work and keep pressure evidence current." if restored_count > 0 else "Keep quarantined strategies out of active guidance until fresh evidence re-earns them."
    )
    result = {
        "ok": True,
        "requested_strategy": requested_strategy,
        "attempted_count": len(attempted),
        "restored_count": restored_count,
        "kept_quarantined_count": kept_quarantined_count,
        "remaining_quarantined_count": len(quarantined),
        "recommended_action": recommended_action,
        "evaluations": evaluations,
        "memory_path": str(_memory_path(cwd)),
    }
    flush_state_writes(paths=[_memory_path(cwd)])
    return result


def pattern_guided_steps(steps: list[dict[str, Any]], pattern_signature: str) -> list[dict[str, Any]]:
    requested_roles = [str(part).strip() for part in str(pattern_signature or "").split("->") if str(part).strip()]
    if not requested_roles:
        return [dict(step) for step in steps]

    def role_priority(role: str) -> int:
        try:
            return requested_roles.index(role)
        except ValueError:
            return len(requested_roles)

    ranked: list[tuple[int, int, int, float, dict[str, Any]]] = []
    for index, step in enumerate(steps):
        cloned = dict(step)
        role = _step_role(cloned)
        cloned["survivor_pattern_role"] = role
        ranked.append(
            (
                role_priority(role),
                0 if role in requested_roles else 1,
                0 if str(cloned.get("risk_level", "low")) == "low" else 1 if str(cloned.get("risk_level", "low")) == "medium" else 2,
                -float(cloned.get("route_confidence", 0.0) or 0.0),
                index,
                cloned,
            )
        )
    return [item[-1] for item in sorted(ranked, key=lambda item: item[:-1])]


def survivor_generation_guidance(cwd: str, plan: dict[str, Any], *, limit: int = 3) -> dict[str, Any]:
    memory = _load_memory(cwd)
    patterns = dict(memory.get("patterns") or {})
    meta_rules = list(memory.get("meta_rules") or [])
    current_pattern = _abstract_pattern(list(plan.get("steps", [])))
    context_signature = _context_signature(plan)

    recommended_patterns: list[dict[str, Any]] = []
    for pattern_signature, raw_record in patterns.items():
        record = dict(raw_record or {})
        contexts = list(record.get("contexts") or [])
        context_match = 1.0 if context_signature and context_signature in contexts else 0.35 if contexts else 0.0
        average_score = float(record.get("average_score", 0.0) or 0.0)
        survival_count = int(record.get("survival_count", 0) or 0)
        cross_context_score = float(record.get("cross_context_score", 0.0) or 0.0)
        validated_context_count = int(record.get("validated_context_count", 0) or 0)
        meta_rule_bonus = 0.0
        for meta_rule in meta_rules:
            if str(meta_rule.get("rule", "")) == "verification_first_survives_better" and str(pattern_signature).startswith("verify"):
                meta_rule_bonus = max(meta_rule_bonus, float(meta_rule.get("confidence", 0.0) or 0.0) * 0.15)
        score = round(
            max(
                0.0,
                min(
                    1.0,
                    max(cross_context_score, (average_score / 100.0) * 0.65)
                    + min(0.2, survival_count * 0.04)
                    + (context_match * 0.15)
                    + min(0.15, validated_context_count * 0.05)
                    + meta_rule_bonus,
                ),
            ),
            3,
        )
        recommended_patterns.append(
            {
                "pattern_signature": str(pattern_signature),
                "score": score,
                "average_score": average_score,
                "survival_count": survival_count,
                "context_match": round(context_match, 3),
                "cross_context_score": cross_context_score,
                "validated_context_count": validated_context_count,
                "meta_rule_bonus": round(meta_rule_bonus, 3),
                "failure_conditions": list(record.get("failure_conditions") or []),
                "source_branch_ids": list(record.get("source_branch_ids") or []),
                "is_current_pattern": str(pattern_signature) == current_pattern,
            }
        )

    recommended_patterns.sort(
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            -float(item.get("average_score", 0.0) or 0.0),
            -int(item.get("survival_count", 0) or 0),
            1 if bool(item.get("is_current_pattern", False)) else 0,
        )
    )
    filtered = [item for item in recommended_patterns if not bool(item.get("is_current_pattern", False))]
    return {
        "ok": True,
        "current_pattern": current_pattern,
        "context_signature": context_signature,
        "history_ready": bool(patterns),
        "prefer_verification_first": any(str(item.get("rule", "")) == "verification_first_survives_better" for item in meta_rules),
        "recommended_patterns": filtered[: max(1, limit)],
        "knowledge_count": len(list(memory.get("knowledge") or [])),
        "meta_rule_count": len(meta_rules),
    }


def survivor_strategy_guidance(cwd: str, plan: dict[str, Any]) -> dict[str, Any]:
    guidance = survivor_generation_guidance(cwd, plan, limit=1)
    memory = _load_memory(cwd)
    patterns = dict(memory.get("patterns") or {})
    strategy_outcomes = dict(memory.get("strategy_outcomes") or {})
    current_pattern = _abstract_pattern(list(plan.get("steps", [])))
    top_pattern = dict((guidance.get("recommended_patterns") or [{}])[0] or {})
    if not top_pattern and current_pattern in patterns:
        record = dict(patterns.get(current_pattern) or {})
        top_pattern = {
            "pattern_signature": current_pattern,
            "score": max(float(record.get("cross_context_score", 0.0) or 0.0), float(record.get("average_score", 0.0) or 0.0) / 100.0),
            "average_score": float(record.get("average_score", 0.0) or 0.0),
            "survival_count": int(record.get("survival_count", 0) or 0),
            "context_match": 1.0 if str(_context_signature(plan)) in list(record.get("contexts") or []) else 0.35,
            "cross_context_score": float(record.get("cross_context_score", 0.0) or 0.0),
            "validated_context_count": int(record.get("validated_context_count", 0) or 0),
            "meta_rule_bonus": 0.0,
            "failure_conditions": list(record.get("failure_conditions") or []),
            "source_branch_ids": list(record.get("source_branch_ids") or []),
            "is_current_pattern": True,
        }
    abstraction = semantic_abstraction_profile(
        str(plan.get("request", "")),
        dict(plan.get("request_targets", {})),
        list(plan.get("request_decomposition", [])),
    )
    target_families = set(str(item) for item in list(abstraction.get("target_families", [])) if str(item))
    request_decomposition = list(plan.get("request_decomposition", []))
    dependency_count = sum(len(list(item.get("depends_on", []))) for item in request_decomposition)
    conditional_count = sum(1 for item in request_decomposition if bool(item.get("conditional", False)))
    target_items = list(dict(plan.get("request_targets", {})).get("items", []))
    mutating_count = sum(1 for step in list(plan.get("steps", [])) if step_allows_mutation(str(step.get("kind", ""))))
    planner_confidence = float(plan.get("planner_confidence", 0.0) or 0.0)
    ambiguity_count = len(list(plan.get("ambiguity_flags", [])))
    current_shape = _branch_shape_profile(plan)
    current_condition = _strategy_condition_profile(plan)
    pattern_signature = str(top_pattern.get("pattern_signature", "")).strip()
    cross_context_score = float(top_pattern.get("cross_context_score", 0.0) or 0.0)
    validated_context_count = int(top_pattern.get("validated_context_count", 0) or 0)
    score = round(
        max(
            float(top_pattern.get("score", 0.0) or 0.0),
            cross_context_score + min(0.12, validated_context_count * 0.04),
        ),
        3,
    )

    preferred_strategy = ""
    preferred_mode = ""
    preferred_branch_types: list[str] = []
    preferred_mutation_intensity = ""
    preferred_mutation_operators: list[str] = []
    suppressed_mutation_intensities: list[str] = []
    reasons: list[str] = []
    strategy_outcome_bonus = 0.0
    strategy_outcome_penalty = 0.0
    recovery_profile = "neutral"
    outcome_guided = False
    outcome_guided_strategy = ""
    strategy_outcome_summary: dict[str, Any] = {}

    if pattern_signature.startswith("verify"):
        preferred_strategy = "verification_first"
        preferred_mode = "deliberate" if score < 0.82 else "safe"
        preferred_branch_types = ["verification_first", "evidence_first"]
        preferred_mutation_intensity = "low"
        preferred_mutation_operators = ["reorder_verification_first", "delay_mutation", "reorder_verify_then_present"]
        suppressed_mutation_intensities = ["extreme"] if score >= 0.72 else []
        reasons.append("validated_verify_pattern")
    elif "mutate" in pattern_signature and len(target_families) > 1:
        preferred_strategy = "target_isolated"
        preferred_mode = "exploratory"
        preferred_branch_types = ["single_target", "verification_first"]
        preferred_mutation_intensity = "medium"
        preferred_mutation_operators = ["target_isolation", "reorder_verification_first", "swap_last_two"]
        suppressed_mutation_intensities = ["extreme"] if score >= 0.82 else []
        reasons.append("validated_mixed_target_pattern")
    elif pattern_signature.startswith("dispatch") and "workspace_source" in target_families:
        preferred_strategy = "dependency_aware"
        preferred_mode = "deliberate"
        preferred_branch_types = ["evidence_first", "verification_first"]
        preferred_mutation_intensity = "medium"
        preferred_mutation_operators = ["reorder_verify_then_present", "delay_mutation", "partial_removal"]
        suppressed_mutation_intensities = ["extreme"] if score >= 0.72 else []
        reasons.append("validated_dispatch_pattern")
    elif pattern_signature.startswith("observe"):
        preferred_strategy = "conservative"
        preferred_mode = "safe"
        preferred_branch_types = ["observation_only", "minimal_safe"]
        preferred_mutation_intensity = "low"
        preferred_mutation_operators = ["reorder_verification_first", "observation_only", "partial_removal"]
        suppressed_mutation_intensities = ["high", "extreme"] if score >= 0.72 else ["extreme"]
        reasons.append("validated_observation_pattern")

    if bool(guidance.get("prefer_verification_first")) and preferred_strategy not in {"conservative", "target_isolated"}:
        preferred_strategy = preferred_strategy or "verification_first"
        preferred_mode = preferred_mode or "deliberate"
        preferred_branch_types = list(dict.fromkeys(preferred_branch_types + ["verification_first", "evidence_first"]))
        preferred_mutation_intensity = preferred_mutation_intensity or "low"
        preferred_mutation_operators = list(dict.fromkeys(preferred_mutation_operators + ["reorder_verification_first", "delay_mutation"]))
        suppressed_mutation_intensities = list(dict.fromkeys(suppressed_mutation_intensities + ["extreme"]))
        reasons.append("meta_rule_verification_first_survives_better")

    if not preferred_strategy and bool(guidance.get("prefer_verification_first")) and current_pattern.startswith("verify"):
        preferred_strategy = "verification_first"
        preferred_mode = "deliberate"
        preferred_branch_types = ["verification_first", "evidence_first"]
        preferred_mutation_intensity = "low"
        preferred_mutation_operators = ["reorder_verification_first", "delay_mutation"]
        suppressed_mutation_intensities = ["extreme"]
        reasons.append("current_pattern_matches_verification_meta_rule")
        score = max(score, 0.62)
    if preferred_strategy:
        strategy_record = dict(strategy_outcomes.get(preferred_strategy) or {})
        if strategy_record:
            shape_match = _shape_match_summary(strategy_record, current_shape)
            freshness = _strategy_record_freshness(strategy_record, condition_profile=current_condition)
            success_rate = float(strategy_record.get("success_rate", 0.0) or 0.0)
            failure_rate = float(strategy_record.get("failure_rate", 0.0) or 0.0)
            recovery_rate = float(strategy_record.get("recovery_rate", 0.0) or 0.0)
            contradiction_hold_rate = float(strategy_record.get("contradiction_hold_rate", 0.0) or 0.0)
            average_outcome_quality = float(strategy_record.get("average_outcome_quality", 0.0) or 0.0)
            freshness_score = float(freshness.get("freshness_score", 0.8) or 0.8)
            recovery_profile = _strategy_outcome_profile(strategy_record)
            strategy_outcome_summary = {
                "strategy": preferred_strategy,
                "profile": recovery_profile,
                "run_count": int(strategy_record.get("run_count", 0) or 0),
                "resilience_score": round(float(strategy_record.get("resilience_score", 0.0) or 0.0), 3),
                "success_rate": round(success_rate, 3),
                "failure_rate": round(failure_rate, 3),
                "recovery_rate": round(recovery_rate, 3),
                "contradiction_hold_rate": round(contradiction_hold_rate, 3),
                "freshness_score": round(freshness_score, 3),
                "days_since_last_run": freshness.get("days_since_last_run"),
                "version_alignment_score": round(float(freshness.get("version_alignment_score", 1.0) or 1.0), 3),
                "planner_version_match": bool(freshness.get("planner_version_match", True)),
                "code_version_match": bool(freshness.get("code_version_match", True)),
                "record_planner_version": str(freshness.get("record_planner_version", "")),
                "record_code_version": str(freshness.get("record_code_version", "")),
                "shape_match_score": round(float(shape_match.get("match_score", 0.0) or 0.0), 3),
                "shape_match_exact": bool(shape_match.get("exact_match", False)),
                "shape_match_signature": str(shape_match.get("matched_signature", "")),
                "condition_match_score": round(float(freshness.get("condition_match_score", 0.0) or 0.0), 3),
                "condition_match_exact": bool(freshness.get("condition_match_exact", False)),
                "condition_signature": str(freshness.get("condition_signature", "")),
                "subsystem_surface": str(freshness.get("subsystem_surface", "")),
            }
            strategy_outcome_bonus = round(min(0.12, ((success_rate * 0.06) + (average_outcome_quality * 0.05) + (recovery_rate * 0.03)) * freshness_score), 3)
            strategy_outcome_penalty = round(min(0.16, ((failure_rate * 0.12) + (contradiction_hold_rate * 0.12)) * freshness_score), 3)
            score = round(
                max(
                    0.0,
                    min(
                        1.0,
                        score
                        + strategy_outcome_bonus
                        - strategy_outcome_penalty
                        + min(0.08, float(shape_match.get("match_score", 0.0) or 0.0) * 0.05)
                        + min(0.05, float(freshness.get("condition_match_score", 0.0) or 0.0) * 0.04),
                    ),
                ),
                3,
            )
            if recovery_profile == "fragile_but_recoverable":
                preferred_mode = "safe"
                preferred_mutation_intensity = "low"
                suppressed_mutation_intensities = list(dict.fromkeys(suppressed_mutation_intensities + ["high", "extreme"]))
                reasons.append("strategy_outcomes_fragile_but_recoverable")
            elif recovery_profile == "fragile_and_unsafe":
                preferred_strategy = "conservative"
                conservative_defaults = _strategy_defaults("conservative")
                preferred_mode = str(conservative_defaults.get("preferred_mode", "safe"))
                preferred_branch_types = list(conservative_defaults.get("preferred_branch_types", []))
                preferred_mutation_intensity = str(conservative_defaults.get("preferred_mutation_intensity", "low"))
                preferred_mutation_operators = list(conservative_defaults.get("preferred_mutation_operators", []))
                suppressed_mutation_intensities = list(conservative_defaults.get("suppressed_mutation_intensities", []))
                reasons.append("strategy_outcomes_fragile_and_unsafe")
            elif recovery_profile == "proven":
                reasons.append("strategy_outcomes_confirm_execution")
            elif recovery_profile == "recovery_supported":
                reasons.append("strategy_outcomes_recovery_supported")

    if not preferred_strategy:
        candidate_outcomes: list[dict[str, Any]] = []
        for strategy_name, raw_record in strategy_outcomes.items():
            record = dict(raw_record or {})
            if int(record.get("run_count", 0) or 0) < 2:
                continue
            normalized = str(strategy_name).strip().lower()
            shape_match = _shape_match_summary(record, current_shape)
            condition_freshness = _strategy_record_freshness(record, condition_profile=current_condition)
            relevance_bonus = 0.0
            relevant = bool(float(shape_match.get("match_score", 0.0) or 0.0) >= 0.3 or float(condition_freshness.get("condition_match_score", 0.0) or 0.0) >= 0.45)
            if normalized == "verification_first" and (mutating_count or str(plan.get("risk_level", "low")).lower() in {"medium", "high"}):
                relevance_bonus += 0.12
                relevant = True
            if normalized == "dependency_aware" and (dependency_count or conditional_count):
                relevance_bonus += 0.14
                relevant = True
            if normalized == "target_isolated" and (len(target_items) > 1 or len(target_families) > 1):
                relevance_bonus += 0.12
                relevant = True
            if normalized == "conservative" and (ambiguity_count or planner_confidence < 0.62 or bool(plan.get("read_only_request", False))):
                relevance_bonus += 0.12
                relevant = True
            if not relevant:
                continue
            candidate_outcomes.append(
                _candidate_strategy_outcome_guidance(
                    normalized,
                    record,
                    relevance_bonus=relevance_bonus,
                    shape_match=shape_match,
                    condition_profile=current_condition,
                )
            )
        candidate_outcomes.sort(key=lambda item: float(item.get("outcome_score", 0.0) or 0.0), reverse=True)
        best_outcome = dict(candidate_outcomes[0] or {}) if candidate_outcomes else {}
        if best_outcome:
            profile = str(best_outcome.get("profile", "neutral"))
            outcome_score = float(best_outcome.get("outcome_score", 0.0) or 0.0)
            if not strategy_outcome_summary:
                strategy_outcome_summary = dict(best_outcome.get("record") or {})
                if strategy_outcome_summary:
                    strategy_outcome_summary["strategy"] = str(best_outcome.get("strategy", "")).strip().lower()
                    strategy_outcome_summary["profile"] = profile
            if ((outcome_score >= 0.62 and profile in {"proven", "recovery_supported", "fragile_but_recoverable"}) or (profile == "fragile_and_unsafe" and outcome_score >= 0.2)):
                defaults = dict(best_outcome.get("defaults") or {})
                preferred_strategy = str(best_outcome.get("strategy", "")).strip().lower()
                preferred_mode = str(defaults.get("preferred_mode", "")).strip()
                preferred_branch_types = [str(item) for item in list(defaults.get("preferred_branch_types", [])) if str(item)]
                preferred_mutation_intensity = str(defaults.get("preferred_mutation_intensity", "")).strip().lower()
                preferred_mutation_operators = [str(item) for item in list(defaults.get("preferred_mutation_operators", [])) if str(item)]
                suppressed_mutation_intensities = [str(item) for item in list(defaults.get("suppressed_mutation_intensities", [])) if str(item)]
                recovery_profile = profile
                outcome_guided = True
                outcome_guided_strategy = preferred_strategy
                strategy_outcome_summary = dict(best_outcome.get("record") or {})
                strategy_outcome_summary["strategy"] = preferred_strategy
                strategy_outcome_summary["profile"] = recovery_profile
                reasons.append("strategy_outcome_guidance")
                if profile == "fragile_but_recoverable":
                    reasons.append("strategy_outcomes_fragile_but_recoverable")
                elif profile == "fragile_and_unsafe":
                    reasons.append("strategy_outcomes_fragile_and_unsafe")
                elif profile == "proven":
                    reasons.append("strategy_outcomes_confirm_execution")
                elif profile == "recovery_supported":
                    reasons.append("strategy_outcomes_recovery_supported")
    if validated_context_count <= 0 and not bool(guidance.get("prefer_verification_first")) and not outcome_guided:
        preferred_strategy = ""
        preferred_mode = ""
        preferred_branch_types = []
        preferred_mutation_intensity = ""
        preferred_mutation_operators = []
        suppressed_mutation_intensities = []
        recovery_profile = "neutral"
        outcome_guided = False
        outcome_guided_strategy = ""
    if (score < 0.62 and not outcome_guided) or not preferred_strategy:
        preferred_strategy = ""
        preferred_mode = ""
        preferred_branch_types = []
        preferred_mutation_intensity = ""
        preferred_mutation_operators = []
        suppressed_mutation_intensities = []
        if not outcome_guided:
            recovery_profile = "neutral"
            outcome_guided_strategy = ""

    return {
        "ok": True,
        "history_ready": bool(guidance.get("history_ready", False)),
        "pattern_signature": pattern_signature,
        "score": score,
        "cross_context_score": cross_context_score,
        "validated_context_count": validated_context_count,
        "preferred_strategy": preferred_strategy,
        "preferred_mode": preferred_mode,
        "preferred_branch_types": preferred_branch_types,
        "preferred_mutation_intensity": preferred_mutation_intensity,
        "preferred_mutation_operators": preferred_mutation_operators,
        "suppressed_mutation_intensities": suppressed_mutation_intensities,
        "strategy_outcome_bonus": strategy_outcome_bonus,
        "strategy_outcome_penalty": strategy_outcome_penalty,
        "recovery_profile": recovery_profile,
        "outcome_guided": outcome_guided,
        "outcome_guided_strategy": outcome_guided_strategy,
        "strategy_outcome_summary": strategy_outcome_summary,
        "current_shape_signature": str(current_shape.get("signature", "")),
        "current_condition_signature": str(current_condition.get("signature", "")),
        "reasons": reasons,
    }


def record_strategy_outcome(cwd: str, plan: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    strategy = str(dict(plan.get("smart_planner") or {}).get("strategy", "")).strip()
    if not strategy:
        return {"ok": False, "reason": "strategy_missing"}
    memory = _load_memory(cwd)
    strategy_outcomes = dict(memory.get("strategy_outcomes") or {})
    record = dict(strategy_outcomes.get(strategy) or {})
    results = list(run.get("results", []))
    plan_steps = list(plan.get("steps", []))
    contradiction_hold = str(dict(run.get("contradiction_gate") or {}).get("decision", "")) == "hold"
    recovered = bool(dict(run.get("replan") or {}).get("applied", False)) or any(bool(item.get("handled_by_fallback", False)) for item in results)
    completed_steps = sum(1 for item in results if bool(item.get("ok", False)) or bool(item.get("handled_by_fallback", False)) or bool(item.get("skipped", False)))
    completion_ratio = round(min(1.0, completed_steps / max(1, len(plan_steps))), 3)
    run_ok = bool(run.get("ok", False))
    failure = not run_ok
    now_utc = _utc_now()
    if run_ok:
        outcome_quality = 1.0
    elif recovered:
        outcome_quality = 0.72
    else:
        outcome_quality = max(0.05, completion_ratio * 0.45)
    if contradiction_hold:
        outcome_quality = min(outcome_quality, 0.25)
    run_count = int(record.get("run_count", 0) or 0) + 1
    success_count = int(record.get("success_count", 0) or 0) + int(run_ok)
    failure_count = int(record.get("failure_count", 0) or 0) + int(failure)
    recovery_count = int(record.get("recovery_count", 0) or 0) + int(recovered)
    contradiction_hold_count = int(record.get("contradiction_hold_count", 0) or 0) + int(contradiction_hold)
    reroute_count = int(record.get("reroute_count", 0) or 0) + int(bool(dict(run.get("replan") or {}).get("attempted", False)))
    previous_average = float(record.get("average_outcome_quality", 0.0) or 0.0)
    average_outcome_quality = round(((previous_average * (run_count - 1)) + float(outcome_quality)) / max(1, run_count), 3)
    success_rate = round(success_count / max(1, run_count), 3)
    failure_rate = round(failure_count / max(1, run_count), 3)
    recovery_rate = round(recovery_count / max(1, run_count), 3)
    contradiction_hold_rate = round(contradiction_hold_count / max(1, run_count), 3)
    planner_version = str(plan.get("planner_version", "") or _current_planner_version()).strip()
    code_version = _current_strategy_code_version()
    branch_shape = _branch_shape_profile(plan)
    branch_shape_signature = str(branch_shape.get("signature", ""))
    condition_profile = _strategy_condition_profile(plan)
    condition_signature = str(condition_profile.get("signature", ""))
    shape_profiles = dict(record.get("shape_profiles") or {})
    shape_profile = dict(shape_profiles.get(branch_shape_signature) or {})
    shape_run_count = int(shape_profile.get("run_count", 0) or 0) + 1
    shape_success_count = int(shape_profile.get("success_count", 0) or 0) + int(run_ok)
    shape_failure_count = int(shape_profile.get("failure_count", 0) or 0) + int(failure)
    shape_recovery_count = int(shape_profile.get("recovery_count", 0) or 0) + int(recovered)
    previous_shape_average = float(shape_profile.get("average_outcome_quality", 0.0) or 0.0)
    shape_average_outcome_quality = round(((previous_shape_average * (shape_run_count - 1)) + float(outcome_quality)) / max(1, shape_run_count), 3)
    shape_profiles[branch_shape_signature] = {
        "branch_shape": {key: value for key, value in branch_shape.items() if key != "signature"},
        "run_count": shape_run_count,
        "success_count": shape_success_count,
        "failure_count": shape_failure_count,
        "recovery_count": shape_recovery_count,
        "success_rate": round(shape_success_count / max(1, shape_run_count), 3),
        "failure_rate": round(shape_failure_count / max(1, shape_run_count), 3),
        "recovery_rate": round(shape_recovery_count / max(1, shape_run_count), 3),
        "average_outcome_quality": shape_average_outcome_quality,
        "last_seen_utc": now_utc,
        "planner_version": planner_version,
        "code_version": code_version,
    }
    condition_profiles = dict(record.get("condition_profiles") or {})
    condition_record = dict(condition_profiles.get(condition_signature) or {})
    condition_run_count = int(condition_record.get("run_count", 0) or 0) + 1
    condition_success_count = int(condition_record.get("success_count", 0) or 0) + int(run_ok)
    condition_failure_count = int(condition_record.get("failure_count", 0) or 0) + int(failure)
    condition_recovery_count = int(condition_record.get("recovery_count", 0) or 0) + int(recovered)
    condition_profiles[condition_signature] = {
        "condition_profile": {key: value for key, value in condition_profile.items() if key != "signature"},
        "run_count": condition_run_count,
        "success_count": condition_success_count,
        "failure_count": condition_failure_count,
        "recovery_count": condition_recovery_count,
        "success_rate": round(condition_success_count / max(1, condition_run_count), 3),
        "failure_rate": round(condition_failure_count / max(1, condition_run_count), 3),
        "recovery_rate": round(condition_recovery_count / max(1, condition_run_count), 3),
        "last_seen_utc": now_utc,
        "planner_version": planner_version,
        "code_version": code_version,
    }
    planner_version_history = list(dict.fromkeys(([str(record.get("planner_version", "")).strip()] if str(record.get("planner_version", "")).strip() else []) + [str(item).strip() for item in list(record.get("planner_version_history", [])) if str(item).strip()] + [planner_version]))[-6:]
    code_version_history = list(dict.fromkeys(([str(record.get("code_version", "")).strip()] if str(record.get("code_version", "")).strip() else []) + [str(item).strip() for item in list(record.get("code_version_history", [])) if str(item).strip()] + [code_version]))[-6:]
    resilience_score = round(
        max(
            0.0,
            min(
                1.0,
                (average_outcome_quality * 0.55)
                + (success_rate * 0.3)
                + (recovery_rate * 0.08)
                - (failure_rate * 0.12)
                - (contradiction_hold_rate * 0.08),
            ),
        ),
        3,
    )
    updated_record = {
        "strategy": strategy,
        "latest_mode": str(dict(plan.get("smart_planner") or {}).get("strategy_mode", "")).strip(),
        "planner_version": planner_version,
        "code_version": code_version,
        "planner_version_history": planner_version_history,
        "code_version_history": code_version_history,
        "first_run_utc": str(record.get("first_run_utc", "") or now_utc),
        "last_run_utc": now_utc,
        "run_count": run_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "recovery_count": recovery_count,
        "contradiction_hold_count": contradiction_hold_count,
        "reroute_count": reroute_count,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "recovery_rate": recovery_rate,
        "contradiction_hold_rate": contradiction_hold_rate,
        "average_outcome_quality": average_outcome_quality,
        "resilience_score": resilience_score,
        "last_branch_shape_signature": branch_shape_signature,
        "last_branch_shape": {key: value for key, value in branch_shape.items() if key != "signature"},
        "shape_profiles": shape_profiles,
        "last_condition_signature": condition_signature,
        "last_condition_profile": {key: value for key, value in condition_profile.items() if key != "signature"},
        "condition_profiles": condition_profiles,
        "last_outcome": {
            "ok": run_ok,
            "recovered": recovered,
            "contradiction_hold": contradiction_hold,
            "completion_ratio": completion_ratio,
            "branch_id": str(dict(plan.get("branch") or {}).get("id", "")),
        },
    }
    strategy_outcomes[strategy] = updated_record
    memory["strategy_outcomes"] = strategy_outcomes
    memory["meta_rules"] = _derive_meta_rules(dict(memory.get("patterns") or {}), strategy_outcomes)
    memory["updated_utc"] = _utc_now()
    put_state_store(cwd, "self_derivation_memory", memory)
    _save_json(_memory_path(cwd), memory)
    flush_state_writes(paths=[_memory_path(cwd)])
    return {"ok": True, "strategy": strategy, "record": updated_record, "path": str(_memory_path(cwd))}


def survivor_history_score(cwd: str, plan: dict[str, Any], *, trigger: str = "") -> dict[str, Any]:
    memory = _load_memory(cwd)
    patterns = dict(memory.get("patterns") or {})
    meta_rules = list(memory.get("meta_rules") or [])
    pattern_signature = _abstract_pattern(list(plan.get("steps", [])))
    context_signature = _context_signature(plan)
    record = dict(patterns.get(pattern_signature) or {})
    contexts = list(record.get("contexts") or [])
    context_match = 1.0 if context_signature and context_signature in contexts else 0.35 if contexts else 0.0
    average_score = float(record.get("average_score", 0.0) or 0.0)
    survival_count = int(record.get("survival_count", 0) or 0)
    cross_context_score = float(record.get("cross_context_score", 0.0) or 0.0)
    validated_context_count = int(record.get("validated_context_count", 0) or 0)
    failure_conditions = list(record.get("failure_conditions") or [])
    meta_rule_bonus = 0.0
    for meta_rule in meta_rules:
        if str(meta_rule.get("rule", "")) == "verification_first_survives_better" and pattern_signature.startswith("verify"):
            meta_rule_bonus = max(meta_rule_bonus, float(meta_rule.get("confidence", 0.0) or 0.0) * 0.15)
    trigger_penalty = 0.0
    if trigger and failure_conditions:
        normalized_trigger = str(trigger).strip().lower()
        if any(normalized_trigger in str(condition).strip().lower() for condition in failure_conditions):
            trigger_penalty = 0.08
    score = round(
        max(
            0.0,
            min(
                1.0,
                max(cross_context_score, (average_score / 100.0) * 0.65)
                + min(0.2, survival_count * 0.04)
                + (context_match * 0.15)
                + min(0.15, validated_context_count * 0.05)
                + meta_rule_bonus
                - trigger_penalty,
            ),
        ),
        3,
    )
    return {
        "score": score,
        "pattern_signature": pattern_signature,
        "context_signature": context_signature,
        "average_score": average_score,
        "survival_count": survival_count,
        "context_match": round(context_match, 3),
        "cross_context_score": cross_context_score,
        "validated_context_count": validated_context_count,
        "meta_rule_bonus": round(meta_rule_bonus, 3),
        "failure_conditions": failure_conditions,
    }

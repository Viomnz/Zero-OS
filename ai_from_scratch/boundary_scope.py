from __future__ import annotations

import json
import re
from pathlib import Path


ALLOWED_DOMAINS = {
    "engineering",
    "planning",
    "analysis",
    "security",
    "monitoring",
    "operations",
    "system",
    "coding",
}

HIGH_RISK_KEYWORDS = {
    "weapon",
    "exploit",
    "zero-day",
    "illegal",
    "harm",
    "bypass",
}

UNAUTHORIZED_KEYWORDS = {
    "delete system32",
    "format c:",
    "disable security",
    "disable firewall",
}


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _infer_domain(prompt: str) -> str:
    p = _normalize(prompt)
    if any(k in p for k in ("build", "code", "file", "compile", "function", "api")):
        return "engineering"
    if any(k in p for k in ("plan", "roadmap", "strategy", "route")):
        return "planning"
    if any(k in p for k in ("analyze", "analysis", "compare", "evaluate")):
        return "analysis"
    if any(k in p for k in ("security", "firewall", "virus", "audit")):
        return "security"
    if any(k in p for k in ("monitor", "status", "health", "observe")):
        return "monitoring"
    if any(k in p for k in ("process", "optimize", "system", "memory", "storage")):
        return "operations"
    return "unknown"


def evaluate_scope(cwd: str, prompt: str, channel: str) -> dict:
    p = _normalize(prompt)
    domain = _infer_domain(prompt)
    domain_allowed = domain in ALLOWED_DOMAINS
    authority_allowed = not any(k in p for k in UNAUTHORIZED_KEYWORDS)
    knowledge_reliable = "??" not in p and len(p.split()) >= 2
    operational_limit_ok = channel in {"human", "system_api", "physical_device"}
    high_risk = any(k in p for k in HIGH_RISK_KEYWORDS)

    inside_scope = domain_allowed and authority_allowed and knowledge_reliable and operational_limit_ok and not high_risk
    decision = "allow" if inside_scope else ("defer" if domain_allowed and authority_allowed else "reject")
    reason = "within scope" if inside_scope else "outside scope"

    out = {
        "ok": True,
        "inside_scope": inside_scope,
        "decision": decision,
        "reason": reason,
        "domain": domain,
        "checks": {
            "domain_allowed": domain_allowed,
            "authority_allowed": authority_allowed,
            "knowledge_reliable": knowledge_reliable,
            "operational_limit_ok": operational_limit_ok,
            "high_risk": high_risk,
        },
    }
    (_runtime(cwd) / "boundary_scope.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

from zero_os.antivirus import monitor_set, monitor_status, policy_set as antivirus_policy_set, policy_status as antivirus_policy_status
from zero_os.production_core import freedom_mode_set, sandbox_status
from zero_os.runtime_smart_logic import security_action_decision
from zero_os.self_repair import self_repair_set, self_repair_status
from zero_os.state import set_mark_strict, set_net_strict
from zero_os.triad_balance import triad_ops_set, triad_ops_status


def _trust_root_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "keys" / "trust_root.key"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def init_trust_root(cwd: str) -> dict:
    p = _trust_root_path(cwd)
    if not p.exists():
        p.write_text(secrets.token_hex(48), encoding="utf-8")
    key = p.read_text(encoding="utf-8", errors="replace").strip()
    pub = hashlib.sha256(key.encode("utf-8")).hexdigest()
    out = {"ok": True, "path": str(p), "public_fingerprint": pub}
    t = Path(cwd).resolve() / ".zero_os" / "runtime" / "trust_root.json"
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def harden_apply(cwd: str) -> dict:
    actions = []
    set_mark_strict(cwd, True)
    actions.append("mark_strict:on")
    set_net_strict(cwd, True)
    actions.append("net_strict:on")

    freedom_mode_set(cwd, "guarded")
    actions.append("freedom:guarded")

    triad_ops_set(cwd, True, 120, "log+inbox")
    actions.append("triad_ops:on")

    self_repair_set(cwd, True, 120)
    actions.append("self_repair:on")

    monitor_set(cwd, True, 120)
    actions.append("antivirus_monitor:on")

    trust = init_trust_root(cwd)
    actions.append("trust_root:initialized")
    logic = security_action_decision(cwd, True, True, True)

    return {
        "ok": True,
        "actions": actions,
        "trust_root": trust,
        "smart_logic": logic,
        "status": harden_status(cwd),
    }


def harden_status(cwd: str) -> dict:
    runtime_trust = Path(cwd).resolve() / ".zero_os" / "runtime" / "trust_root.json"
    trust_ok = runtime_trust.exists()
    triad = triad_ops_status(cwd)
    repair = self_repair_status(cwd)
    av = monitor_status(cwd)
    sandbox = sandbox_status(cwd)
    deny_count = len(sandbox.get("deny_prefix", []))
    score = 0
    if trust_ok:
        score += 1
    if triad.get("enabled", False):
        score += 1
    if repair.get("enabled", False):
        score += 1
    if av.get("enabled", False):
        score += 1
    if deny_count > 0:
        score += 1
    return {
        "ok": True,
        "harden_score": score,
        "harden_total": 5,
        "trust_root_ready": trust_ok,
        "triad_ops_enabled": triad.get("enabled", False),
        "self_repair_enabled": repair.get("enabled", False),
        "antivirus_monitor_enabled": av.get("enabled", False),
        "sandbox_deny_rules": deny_count,
    }


def _smart_logic_policy_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "smart_logic_policy.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _write_zero_ai_security_policy(cwd: str) -> dict:
    payload = {
        "global": {"review_enabled": True},
        "engines": {
            "zero_ai_gate_smart_logic_v1": {"min_confidence": 0.8},
            "zero_ai_internal_smart_logic_v1": {"min_confidence": 0.82},
            "cure_firewall_smart_logic_v1": {"min_confidence": 0.85},
            "antivirus_smart_logic_v1": {"min_confidence": 0.9},
        },
    }
    _smart_logic_policy_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def zero_ai_security_apply(cwd: str) -> dict:
    actions = []
    base = harden_apply(cwd)
    actions.extend(base.get("actions", []))
    triad_ops_set(cwd, True, 60, "log+inbox")
    actions.append("triad_ops:strict_interval_60")
    self_repair_set(cwd, True, 60)
    actions.append("self_repair:strict_interval_60")
    monitor_set(cwd, True, 60)
    actions.append("antivirus_monitor:strict_interval_60")
    antivirus_policy_set(cwd, "heuristic_threshold", "45")
    actions.append("antivirus_policy:heuristic_threshold=45")
    antivirus_policy_set(cwd, "response_mode", "quarantine_high")
    actions.append("antivirus_policy:response_mode=quarantine_high")
    policy = _write_zero_ai_security_policy(cwd)
    actions.append("smart_logic_policy:strict")
    logic = security_action_decision(cwd, True, True, True)
    return {
        "ok": True,
        "actions": actions,
        "base_hardening": base.get("status", {}),
        "smart_logic_policy": policy,
        "smart_logic": logic,
        "status": zero_ai_security_status(cwd),
    }


def zero_ai_security_status(cwd: str) -> dict:
    base = harden_status(cwd)
    av = antivirus_policy_status(cwd)
    p = _smart_logic_policy_path(cwd)
    policy = {}
    if p.exists():
        try:
            policy = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            policy = {}
    engines = (policy.get("engines", {}) or {})
    strict_thresholds = (
        float((engines.get("zero_ai_gate_smart_logic_v1", {}) or {}).get("min_confidence", 0.0)) >= 0.8
        and float((engines.get("zero_ai_internal_smart_logic_v1", {}) or {}).get("min_confidence", 0.0)) >= 0.82
        and float((engines.get("cure_firewall_smart_logic_v1", {}) or {}).get("min_confidence", 0.0)) >= 0.85
        and float((engines.get("antivirus_smart_logic_v1", {}) or {}).get("min_confidence", 0.0)) >= 0.9
    )
    checks = {
        "base_hardening": bool(base.get("harden_score", 0) >= 5),
        "antivirus_response_mode_strict": str(av.get("response_mode", "")) == "quarantine_high",
        "antivirus_threshold_strict": int(av.get("heuristic_threshold", 100)) <= 45,
        "smart_logic_thresholds_strict": strict_thresholds,
    }
    score = sum(1 for v in checks.values() if v)
    return {
        "ok": True,
        "zero_ai_security_score": score,
        "zero_ai_security_total": len(checks),
        "hardened": score == len(checks),
        "checks": checks,
        "base": base,
        "antivirus_policy": {
            "heuristic_threshold": av.get("heuristic_threshold"),
            "response_mode": av.get("response_mode"),
        },
        "smart_logic_policy_path": str(p),
    }

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

from zero_os.antivirus import monitor_set, monitor_status
from zero_os.production_core import freedom_mode_set, sandbox_status
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

    return {
        "ok": True,
        "actions": actions,
        "trust_root": trust,
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

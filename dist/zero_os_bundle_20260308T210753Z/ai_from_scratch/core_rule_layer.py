from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from pathlib import Path


DEFAULT_CORE_RULES = {
    "identity": "zero_ai_core",
    "version": 1,
    "immutable_rules": {
        "three_signal_agreement_required": True,
        "reject_on_any_signal_failure": True,
        "zero_baseline_reset": True,
    },
    "signal_definitions": ["logic", "environment", "survival"],
    "execution_condition": "logic_and_environment_and_survival_must_pass",
}


def _core_rules_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / "laws" / "core_rules.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _core_sig_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "core_rules.signature"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _key_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "keys" / "core_rules.key"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _key(cwd: str) -> bytes:
    p = _key_path(cwd)
    if not p.exists():
        p.write_text(secrets.token_hex(32), encoding="utf-8")
    return p.read_text(encoding="utf-8", errors="replace").strip().encode("utf-8")


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(cwd: str, payload: dict) -> str:
    return hmac.new(_key(cwd), _canonical(payload), hashlib.sha256).hexdigest()


def ensure_core_rules(cwd: str) -> dict:
    p = _core_rules_path(cwd)
    s = _core_sig_path(cwd)
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_CORE_RULES, indent=2) + "\n", encoding="utf-8")
        s.write_text(_sign(cwd, DEFAULT_CORE_RULES), encoding="utf-8")
        return {"ok": True, "created": True}
    if not s.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            data = dict(DEFAULT_CORE_RULES)
            p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        s.write_text(_sign(cwd, data), encoding="utf-8")
        return {"ok": True, "created": False, "signature_repaired": True}
    return {"ok": True, "created": False}


def load_core_rules(cwd: str) -> dict:
    ensure_core_rules(cwd)
    try:
        return json.loads(_core_rules_path(cwd).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(DEFAULT_CORE_RULES)


def verify_core_rules(cwd: str) -> dict:
    ensure_core_rules(cwd)
    data = load_core_rules(cwd)
    sig = _core_sig_path(cwd).read_text(encoding="utf-8", errors="replace").strip()
    expected = _sign(cwd, data)
    ok = hmac.compare_digest(sig, expected)
    return {"ok": ok, "identity": data.get("identity", ""), "version": data.get("version", 0)}


def attempt_modify_core_rules(cwd: str, updates: dict, actor: str) -> dict:
    # Identity rule: reasoner path cannot modify core rules.
    if actor != "admin":
        return {"ok": False, "reason": "attempt_modify_core_rules rejected for non-admin actor"}
    current = load_core_rules(cwd)
    merged = dict(current)
    merged.update(updates)
    _core_rules_path(cwd).write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    _core_sig_path(cwd).write_text(_sign(cwd, merged), encoding="utf-8")
    return {"ok": True, "reason": "core rules updated by admin"}

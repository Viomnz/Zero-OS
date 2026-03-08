from __future__ import annotations

import hashlib
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from zero_os.antivirus import policy_set as antivirus_policy_set
from zero_os.enterprise_security import enterprise_enable, policy_lock_apply, rollout_set, siem_emit
from zero_os.production_core import snapshot_create, snapshot_list, snapshot_restore
from zero_os.security_hardening import zero_ai_security_apply
from zero_os.self_repair import self_repair_set
from zero_os.triad_balance import triad_ops_set


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _keys(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "keys"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _key_registry_path(cwd: str) -> Path:
    return _runtime(cwd) / "enterprise_key_registry.json"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _fingerprint(secret_text: str) -> str:
    return hashlib.sha256(secret_text.encode("utf-8")).hexdigest()


def key_status(cwd: str) -> dict:
    reg = _load_json(_key_registry_path(cwd), {"active": {}, "revoked": []})
    return {"ok": True, "active_count": len(reg.get("active", {})), "revoked_count": len(reg.get("revoked", [])), "registry": reg}


def key_rotate(cwd: str, key_name: str = "operator_actions.key") -> dict:
    path = _keys(cwd) / key_name
    old = path.read_text(encoding="utf-8", errors="replace").strip() if path.exists() else ""
    new_secret = secrets.token_hex(48)
    path.write_text(new_secret, encoding="utf-8")
    reg = _load_json(_key_registry_path(cwd), {"active": {}, "revoked": []})
    if old:
        reg["revoked"].append(
            {"key_name": key_name, "fingerprint": _fingerprint(old), "revoked_utc": _utc_now(), "reason": "rotated"}
        )
    reg["active"][key_name] = {"fingerprint": _fingerprint(new_secret), "rotated_utc": _utc_now()}
    _save_json(_key_registry_path(cwd), reg)
    return {"ok": True, "key_name": key_name, "active_fingerprint": reg["active"][key_name]["fingerprint"], "status": key_status(cwd)}


def key_revoke(cwd: str, key_name: str) -> dict:
    path = _keys(cwd) / key_name
    if not path.exists():
        return {"ok": False, "reason": "key not found", "key_name": key_name}
    cur = path.read_text(encoding="utf-8", errors="replace").strip()
    reg = _load_json(_key_registry_path(cwd), {"active": {}, "revoked": []})
    reg["revoked"].append(
        {"key_name": key_name, "fingerprint": _fingerprint(cur), "revoked_utc": _utc_now(), "reason": "manual_revoke"}
    )
    reg.get("active", {}).pop(key_name, None)
    _save_json(_key_registry_path(cwd), reg)
    path.unlink(missing_ok=True)
    return {"ok": True, "key_name": key_name, "status": key_status(cwd)}


def immutable_audit_export(cwd: str) -> dict:
    base = Path(cwd).resolve() / ".zero_os"
    immutable_dir = base / "immutable"
    immutable_dir.mkdir(parents=True, exist_ok=True)
    ledger = immutable_dir / "audit_ledger.jsonl"
    source_files = [base / "audit.log", base / "enterprise" / "siem_events.jsonl", base / "runtime" / "triad_alerts.jsonl"]
    entries = []
    for src in source_files:
        if not src.exists():
            continue
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        entries.append({"source": str(src), "sha256": digest, "size": len(text)})
    prev_hash = ""
    if ledger.exists():
        try:
            last = ledger.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1]
            prev_hash = json.loads(last).get("entry_hash", "")
        except Exception:
            prev_hash = ""
    payload = {"time_utc": _utc_now(), "entries": entries, "prev_hash": prev_hash}
    entry_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    rec = {"entry_hash": entry_hash, **payload}
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"ok": True, "ledger_path": str(ledger), "entry_hash": entry_hash, "source_count": len(entries)}


def runbooks_sync(cwd: str) -> dict:
    doc = Path(cwd).resolve() / "docs" / "SECURITY_RUNBOOKS.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    body = """# Security Runbooks

## Incident: Malware/Finding Spike
- Command: `antivirus monitor tick .`
- Command: `triad balance run`
- Command: `enterprise siem emit high malware_spike`

## Incident: Integrity Drift
- Command: `zero ai gap status`
- Command: `zero ai gap fix`
- Command: `enterprise immutable audit export`

## Incident: Recovery
- Command: `enterprise dr drill rto=120`
- Command: `enterprise rollback run critical`
"""
    doc.write_text(body, encoding="utf-8")
    return {"ok": True, "path": str(doc)}


def rollout_apply(cwd: str, env: str, canary_percent: int = 10) -> dict:
    e = env.strip().lower()
    if e not in {"dev", "stage", "prod"}:
        return {"ok": False, "reason": "env must be dev|stage|prod"}
    rollout = rollout_set(cwd, e)
    if not rollout.get("ok", False):
        return rollout
    enterprise_enable(cwd, e in {"stage", "prod"})
    triad_ops_set(cwd, True, 120 if e == "dev" else 60, "log+inbox")
    self_repair_set(cwd, True, 120 if e == "dev" else 60)
    antivirus_policy_set(cwd, "response_mode", "manual" if e == "dev" else "quarantine_high")
    if e == "prod":
        policy_lock_apply(cwd)
        zero_ai_security_apply(cwd)
    profile = {"environment": e, "canary_percent": max(1, min(100, int(canary_percent))), "applied_utc": _utc_now()}
    _save_json(_runtime(cwd) / "rollout_canary_profile.json", profile)
    return {"ok": True, "rollout": rollout, "profile": profile}


def alert_routing_set(cwd: str, webhook: str, critical_min: str = "high") -> dict:
    policy = {"webhook": webhook.strip(), "critical_min": critical_min.strip().lower(), "updated_utc": _utc_now()}
    _save_json(_runtime(cwd) / "alert_routing.json", policy)
    enterprise_enable(cwd, True, webhook.strip())
    return {"ok": True, "routing": policy}


def alert_routing_status(cwd: str) -> dict:
    p = _runtime(cwd) / "alert_routing.json"
    if not p.exists():
        return {"ok": False, "missing": True, "hint": "run: enterprise alert routing set webhook=<url> critical=<level>"}
    return {"ok": True, "routing": _load_json(p, {})}


def alert_routing_emit(cwd: str, event: str, severity: str, payload: dict | None = None) -> dict:
    st = alert_routing_status(cwd)
    payload = payload or {}
    if not st.get("ok", False):
        return {"ok": False, "reason": "routing not configured"}
    return siem_emit(cwd, event, severity, payload)


def dr_drill(cwd: str, rto_seconds: int = 120) -> dict:
    start = time.time()
    created = snapshot_create(cwd)
    sid = created.get("id", "")
    if not sid:
        snaps = snapshot_list(cwd).get("snapshots", [])
        if snaps:
            sid = snaps[-1].get("id", "")
    restored = snapshot_restore(cwd, sid) if sid else {"ok": False}
    elapsed = round(time.time() - start, 3)
    passed = bool(restored.get("ok", False)) and elapsed <= float(rto_seconds)
    out = {
        "ok": True,
        "snapshot_id": sid,
        "restore_ok": bool(restored.get("ok", False)),
        "elapsed_seconds": elapsed,
        "rto_target_seconds": int(rto_seconds),
        "rto_passed": passed,
        "time_utc": _utc_now(),
    }
    _save_json(_runtime(cwd) / "dr_drill_report.json", out)
    return out


def enterprise_max_maturity_apply(cwd: str) -> dict:
    actions = []
    actions.append({"key_rotate": key_rotate(cwd, "operator_actions.key")})
    actions.append({"immutable_audit_export": immutable_audit_export(cwd)})
    actions.append({"runbooks_sync": runbooks_sync(cwd)})
    actions.append({"rollout_apply": rollout_apply(cwd, "stage", 10)})
    actions.append({"dr_drill": dr_drill(cwd, 180)})
    return {"ok": True, "time_utc": _utc_now(), "actions": actions}

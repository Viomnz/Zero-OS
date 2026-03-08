from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from zero_os.app_store_universal import detect_device, list_packages, resolve_package


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "store" / "prod_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "accounts": {},
        "licenses": {},
        "entitlements": {},
        "installs": {},
        "security": {"required_signing": True, "required_malware_scan": True},
        "storage": {"object_store": "local-blob", "replicas": 2, "revisions": {}},
        "cdn": {"enabled": True, "regions": ["us-west", "us-east"]},
        "reviews": {},
        "analytics": {"downloads": {}, "installs": {}, "crashes": {}, "search_queries": {}},
        "compliance": {"ios_external_store_allowed": False, "policy_version": "1.0"},
        "telemetry": {"events": [], "slo": {"availability": 99.9, "p95_install_sec": 120}, "error_budget_burn": 0.0, "abuse": {"blocked_ips": []}},
    }


def _load(cwd: str) -> dict:
    p = _state_path(cwd)
    if not p.exists():
        d = _default_state()
        _save(cwd, d)
        return d
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        d = _default_state()
        _save(cwd, d)
        return d


def _save(cwd: str, state: dict) -> None:
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _event(state: dict, typ: str, payload: dict) -> None:
    state["telemetry"]["events"].append({"time_utc": _utc_now(), "type": typ, "payload": payload})
    state["telemetry"]["events"] = state["telemetry"]["events"][-300:]


def account_create(cwd: str, email: str, tier: str = "free") -> dict:
    s = _load(cwd)
    uid = str(uuid.uuid4())[:12]
    s["accounts"][uid] = {"email": email.strip().lower(), "tier": tier.strip().lower(), "created_utc": _utc_now()}
    _event(s, "account_create", {"user": uid})
    _save(cwd, s)
    return {"ok": True, "user_id": uid, "account": s["accounts"][uid]}


def billing_charge(cwd: str, user_id: str, amount: float, currency: str = "USD") -> dict:
    s = _load(cwd)
    if user_id not in s["accounts"]:
        return {"ok": False, "reason": "user not found"}
    tx = {"id": str(uuid.uuid4())[:12], "amount": float(amount), "currency": currency.upper(), "time_utc": _utc_now(), "status": "captured"}
    s["accounts"][user_id].setdefault("transactions", []).append(tx)
    _event(s, "billing_charge", {"user": user_id, "amount": amount})
    _save(cwd, s)
    return {"ok": True, "transaction": tx}


def license_grant(cwd: str, user_id: str, app_name: str) -> dict:
    s = _load(cwd)
    if user_id not in s["accounts"]:
        return {"ok": False, "reason": "user not found"}
    key = f"{user_id}:{app_name.lower()}"
    lic = {"license_id": str(uuid.uuid4())[:16], "user_id": user_id, "app": app_name, "granted_utc": _utc_now(), "active": True}
    s["licenses"][key] = lic
    s["entitlements"].setdefault(user_id, []).append(app_name)
    _event(s, "license_grant", {"user": user_id, "app": app_name})
    _save(cwd, s)
    return {"ok": True, "license": lic}


def install_app(cwd: str, user_id: str, app_name: str, os_name: str = "") -> dict:
    s = _load(cwd)
    if user_id not in s["accounts"]:
        return {"ok": False, "reason": "user not found"}
    if app_name not in s["entitlements"].get(user_id, []):
        return {"ok": False, "reason": "missing entitlement"}
    device = detect_device()
    if os_name:
        device["os"] = os_name.lower()
    # iOS policy gate
    if device["os"] == "ios" and not s["compliance"]["ios_external_store_allowed"]:
        return {"ok": False, "reason": "ios policy restriction: external store disallowed"}
    resolved = resolve_package(cwd, app_name, device["os"], device["cpu"], device["architecture"], device["security"])
    if not resolved.get("ok", False):
        return {"ok": False, "reason": "resolve failed", "resolve": resolved}
    iid = str(uuid.uuid4())[:12]
    rec = {"install_id": iid, "user_id": user_id, "app": app_name, "os": resolved["os"], "version": resolved["version"], "target": resolved["target"], "state": "installed", "installed_utc": _utc_now()}
    s["installs"][iid] = rec
    s["analytics"]["downloads"][app_name] = int(s["analytics"]["downloads"].get(app_name, 0)) + 1
    s["analytics"]["installs"][app_name] = int(s["analytics"]["installs"].get(app_name, 0)) + 1
    _event(s, "install", {"id": iid, "app": app_name})
    _save(cwd, s)
    return {"ok": True, "install": rec}


def uninstall_app(cwd: str, install_id: str) -> dict:
    s = _load(cwd)
    rec = s["installs"].get(install_id)
    if not rec:
        return {"ok": False, "reason": "install not found"}
    rec["state"] = "uninstalled"
    rec["uninstalled_utc"] = _utc_now()
    _event(s, "uninstall", {"id": install_id})
    _save(cwd, s)
    return {"ok": True, "install": rec}


def upgrade_app(cwd: str, install_id: str, version: str) -> dict:
    s = _load(cwd)
    rec = s["installs"].get(install_id)
    if not rec:
        return {"ok": False, "reason": "install not found"}
    rec["version"] = version.strip()
    rec["upgraded_utc"] = _utc_now()
    _event(s, "upgrade", {"id": install_id, "version": version})
    _save(cwd, s)
    return {"ok": True, "install": rec}


def security_enforce(cwd: str, app_name: str) -> dict:
    # Minimal real enforcement hook over published metadata.
    store = list_packages(cwd)
    candidates = [a for a in store.get("apps", []) if str(a.get("name", "")).lower() == app_name.lower()]
    if not candidates:
        return {"ok": False, "reason": "app not found"}
    app = sorted(candidates, key=lambda x: str(x.get("version", "")))[-1]
    sec = app.get("security", {})
    ok = bool(sec.get("signature_present", False))
    return {
        "ok": ok,
        "app": app_name,
        "enforcement": {
            "signature_chain": "pass" if ok else "fail",
            "malware_scan": "pass" if sec.get("malware_scan") != "not_run" else "warn",
        },
    }


def storage_replicate(cwd: str, app_name: str, version: str) -> dict:
    s = _load(cwd)
    key = f"{app_name}:{version}"
    rev = str(uuid.uuid4())[:8]
    s["storage"]["revisions"].setdefault(key, []).append({"revision": rev, "time_utc": _utc_now(), "replicas": s["storage"]["replicas"]})
    _event(s, "replicate", {"key": key, "revision": rev})
    _save(cwd, s)
    return {"ok": True, "key": key, "revision": rev, "replicas": s["storage"]["replicas"]}


def storage_rollback(cwd: str, app_name: str, version: str) -> dict:
    s = _load(cwd)
    key = f"{app_name}:{version}"
    revs = s["storage"]["revisions"].get(key, [])
    if len(revs) < 2:
        return {"ok": False, "reason": "no previous revision"}
    current = revs.pop()
    previous = revs[-1]
    _event(s, "rollback", {"key": key, "from": current["revision"], "to": previous["revision"]})
    _save(cwd, s)
    return {"ok": True, "key": key, "active_revision": previous["revision"]}


def review_add(cwd: str, app_name: str, user_id: str, rating: int, text: str = "") -> dict:
    s = _load(cwd)
    r = {"user_id": user_id, "rating": max(1, min(5, int(rating))), "text": text.strip(), "time_utc": _utc_now()}
    s["reviews"].setdefault(app_name, []).append(r)
    _event(s, "review", {"app": app_name, "rating": r["rating"]})
    _save(cwd, s)
    return {"ok": True, "review": r}


def search_apps(cwd: str, query: str) -> dict:
    s = _load(cwd)
    q = query.strip().lower()
    apps = list_packages(cwd).get("apps", [])
    hits = [a for a in apps if q in str(a.get("name", "")).lower()]
    ranked = sorted(hits, key=lambda a: int(s["analytics"]["downloads"].get(a["name"], 0)), reverse=True)
    s["analytics"]["search_queries"][q] = int(s["analytics"]["search_queries"].get(q, 0)) + 1
    _event(s, "search", {"q": q, "hits": len(ranked)})
    _save(cwd, s)
    return {"ok": True, "query": q, "results": [{"name": a["name"], "version": a["version"]} for a in ranked]}


def analytics_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "analytics": s["analytics"]}


def compliance_set(cwd: str, ios_external_store_allowed: bool) -> dict:
    s = _load(cwd)
    s["compliance"]["ios_external_store_allowed"] = bool(ios_external_store_allowed)
    _event(s, "compliance_set", {"ios_external_store_allowed": bool(ios_external_store_allowed)})
    _save(cwd, s)
    return {"ok": True, "compliance": s["compliance"]}


def compliance_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "compliance": s["compliance"]}


def telemetry_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "telemetry": s["telemetry"]}


def slo_set(cwd: str, availability: float, p95_install_sec: int) -> dict:
    s = _load(cwd)
    s["telemetry"]["slo"] = {"availability": float(availability), "p95_install_sec": int(p95_install_sec)}
    _event(s, "slo_set", s["telemetry"]["slo"])
    _save(cwd, s)
    return {"ok": True, "slo": s["telemetry"]["slo"]}


def abuse_block_ip(cwd: str, ip: str) -> dict:
    s = _load(cwd)
    if ip not in s["telemetry"]["abuse"]["blocked_ips"]:
        s["telemetry"]["abuse"]["blocked_ips"].append(ip)
    _event(s, "abuse_block_ip", {"ip": ip})
    _save(cwd, s)
    return {"ok": True, "blocked_ips": s["telemetry"]["abuse"]["blocked_ips"]}

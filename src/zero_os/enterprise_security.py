from __future__ import annotations

import hashlib
import hmac
import json
import platform
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from zero_os.production_core import snapshot_create, snapshot_restore, snapshot_list


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "enterprise"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _policy_path(cwd: str) -> Path:
    return _root(cwd) / "policy.json"


def _roles_path(cwd: str) -> Path:
    return _root(cwd) / "roles.json"


def _siem_path(cwd: str) -> Path:
    return _root(cwd) / "siem_events.jsonl"


def _integrations_path(cwd: str) -> Path:
    return _root(cwd) / "integrations.json"


def _rollout_path(cwd: str) -> Path:
    return _root(cwd) / "rollout_profile.json"


def _key_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "keys" / "operator_actions.key"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(secrets.token_hex(32), encoding="utf-8")
    return p


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sign(cwd: str, payload: dict) -> str:
    key = _key_path(cwd).read_text(encoding="utf-8", errors="replace").strip().encode("utf-8")
    msg = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _policy(cwd: str) -> dict:
    default = {
        "enabled": False,
        "require_signed_critical_actions": True,
        "siem_webhook": "",
        "forbidden_prefixes": ["format ", "diskpart ", "rm -rf /", "del c:\\"],
        "critical_prefixes": ["powershell run ", "shell run ", "terminal run ", "process kill "],
    }
    p = _policy_path(cwd)
    cur = _load(p, default)
    for k, v in default.items():
        cur.setdefault(k, v)
    _save(p, cur)
    return cur


def _roles(cwd: str) -> dict:
    default = {"roles": {"owner": "admin"}}
    p = _roles_path(cwd)
    cur = _load(p, default)
    if "roles" not in cur or not isinstance(cur["roles"], dict):
        cur = default
    _save(p, cur)
    return cur


def set_role(cwd: str, user: str, role: str) -> dict:
    role_n = role.strip().lower()
    if role_n not in {"admin", "operator", "viewer"}:
        return {"ok": False, "reason": "role must be admin|operator|viewer"}
    data = _roles(cwd)
    data["roles"][user.strip().lower()] = role_n
    _save(_roles_path(cwd), data)
    return {"ok": True, "roles": data["roles"]}


def role_of(cwd: str, user: str) -> str:
    data = _roles(cwd)
    return str(data["roles"].get(user.strip().lower(), "viewer"))


def sign_action(cwd: str, user: str, action: str) -> dict:
    payload = {"user": user.strip().lower(), "action": action.strip(), "issued_utc": _utc_now()}
    token = _sign(cwd, payload)
    return {"ok": True, "token": token, "payload": payload}


def verify_action(cwd: str, payload: dict, token: str) -> bool:
    return hmac.compare_digest(_sign(cwd, payload), str(token or ""))


def edr_probe(cwd: str) -> dict:
    os_name = platform.system().lower()
    return {
        "ok": True,
        "os": os_name,
        "kernel_hook_ready": False,
        "driver_level_enforcement": False,
        "notes": "Kernel/driver EDR hooks require external platform integration.",
    }


def enterprise_enable(cwd: str, enabled: bool, siem_webhook: str | None = None) -> dict:
    p = _policy(cwd)
    p["enabled"] = bool(enabled)
    if siem_webhook is not None:
        p["siem_webhook"] = siem_webhook.strip()
    _save(_policy_path(cwd), p)
    return {"ok": True, "policy": p}


def enterprise_status(cwd: str) -> dict:
    return {
        "ok": True,
        "policy": _policy(cwd),
        "roles": _roles(cwd).get("roles", {}),
        "edr": edr_probe(cwd),
        "integrations": integration_status(cwd),
        "rollout": rollout_status(cwd),
    }


def integration_status(cwd: str) -> dict:
    default = {
        "edr": {"enabled": False, "provider": "", "endpoint": ""},
        "siem": {"enabled": False, "provider": "", "webhook": ""},
        "iam": {"enabled": False, "provider": "", "tenant": ""},
        "zerotrust": {"enabled": False, "provider": "", "policy_url": ""},
    }
    cur = _load(_integrations_path(cwd), default)
    for k, v in default.items():
        cur.setdefault(k, v)
    _save(_integrations_path(cwd), cur)
    score = 0
    total = 4
    for k in ("edr", "siem", "iam", "zerotrust"):
        if bool(cur.get(k, {}).get("enabled", False)):
            score += 1
    return {"ok": True, "score": score, "total": total, "items": cur}


def integration_configure(cwd: str, name: str, enabled: bool, provider: str = "", endpoint: str = "") -> dict:
    n = name.strip().lower()
    if n not in {"edr", "siem", "iam", "zerotrust"}:
        return {"ok": False, "reason": "integration must be edr|siem|iam|zerotrust"}
    data = integration_status(cwd).get("items", {})
    item = data.get(n, {})
    item["enabled"] = bool(enabled)
    if provider:
        item["provider"] = provider.strip()
    if n == "siem":
        item["webhook"] = endpoint.strip()
    elif n == "iam":
        item["tenant"] = endpoint.strip()
    elif n == "zerotrust":
        item["policy_url"] = endpoint.strip()
    else:
        item["endpoint"] = endpoint.strip()
    data[n] = item
    _save(_integrations_path(cwd), data)
    return {"ok": True, "integration": n, "config": item}


def integration_probe(cwd: str, name: str) -> dict:
    n = name.strip().lower()
    status = integration_status(cwd).get("items", {})
    item = status.get(n, {})
    if not item:
        return {"ok": False, "reason": "integration not found"}
    if not item.get("enabled", False):
        return {"ok": False, "integration": n, "reason": "disabled"}
    endpoint = ""
    if n == "siem":
        endpoint = str(item.get("webhook", ""))
    elif n == "iam":
        endpoint = str(item.get("tenant", ""))
    elif n == "zerotrust":
        endpoint = str(item.get("policy_url", ""))
    else:
        endpoint = str(item.get("endpoint", ""))
    if not endpoint:
        return {"ok": False, "integration": n, "reason": "missing endpoint/tenant"}
    return {"ok": True, "integration": n, "provider": item.get("provider", ""), "endpoint": endpoint}


def rollout_status(cwd: str) -> dict:
    default = {
        "environment": "dev",
        "locked_high_risk_defaults": False,
    }
    cur = _load(_rollout_path(cwd), default)
    for k, v in default.items():
        cur.setdefault(k, v)
    _save(_rollout_path(cwd), cur)
    return cur


def rollout_set(cwd: str, environment: str) -> dict:
    env = environment.strip().lower()
    if env not in {"dev", "stage", "prod"}:
        return {"ok": False, "reason": "environment must be dev|stage|prod"}
    cur = rollout_status(cwd)
    cur["environment"] = env
    _save(_rollout_path(cwd), cur)
    return {"ok": True, "rollout": cur}


def policy_lock_apply(cwd: str) -> dict:
    pol = _policy(cwd)
    # Freeze high-risk defaults.
    pol["enabled"] = True
    pol["require_signed_critical_actions"] = True
    pol["forbidden_prefixes"] = ["format ", "diskpart ", "rm -rf /", "del c:\\"]
    pol["critical_prefixes"] = ["powershell run ", "shell run ", "terminal run ", "process kill "]
    _save(_policy_path(cwd), pol)
    roll = rollout_status(cwd)
    roll["locked_high_risk_defaults"] = True
    _save(_rollout_path(cwd), roll)
    return {"ok": True, "policy": pol, "rollout": roll}


def siem_emit(cwd: str, event: str, severity: str, payload: dict) -> dict:
    rec = {
        "time_utc": _utc_now(),
        "event": event,
        "severity": severity,
        "payload": payload,
    }
    with _siem_path(cwd).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

    webhook = str(_policy(cwd).get("siem_webhook", "")).strip()
    pushed = False
    push_error = ""
    if webhook:
        try:
            req = Request(
                webhook,
                data=json.dumps(rec).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Zero-OS-Enterprise/1"},
                method="POST",
            )
            with urlopen(req, timeout=8):
                pass
            pushed = True
        except Exception as exc:
            push_error = str(exc)
    return {"ok": True, "logged": True, "pushed": pushed, "push_error": push_error}


def preexec_check(cwd: str, command: str, user: str = "owner", token: str = "", signed_payload: dict | None = None) -> tuple[bool, str]:
    pol = _policy(cwd)
    if not pol.get("enabled", False):
        return (True, "enterprise policy disabled")
    cmd = command.strip().lower()
    for pref in pol.get("forbidden_prefixes", []):
        if cmd.startswith(str(pref).lower()):
            return (False, f"blocked by enterprise forbidden prefix: {pref}")

    role = role_of(cwd, user)
    if role == "viewer":
        return (False, "viewer role cannot execute commands")

    critical = any(cmd.startswith(str(p).lower()) for p in pol.get("critical_prefixes", []))
    if critical and pol.get("require_signed_critical_actions", True):
        if not signed_payload or not token:
            return (False, "critical action requires signed payload token")
        if not verify_action(cwd, signed_payload, token):
            return (False, "invalid signed action token")
    return (True, "allowed")


def rollback_playbook_run(cwd: str, incident: str) -> dict:
    inc = incident.strip().lower()
    snaps = snapshot_list(cwd).get("snapshots", [])
    if not snaps:
        created = snapshot_create(cwd)
        return {"ok": True, "incident": inc, "action": "snapshot_created", "snapshot": created.get("id")}

    last_id = snaps[-1].get("id")
    if inc in {"critical", "ransomware", "integrity_failure"}:
        res = snapshot_restore(cwd, str(last_id))
        return {"ok": bool(res.get("ok", False)), "incident": inc, "action": "snapshot_restored", "snapshot": last_id}
    return {"ok": True, "incident": inc, "action": "monitor_only", "snapshot": last_id}


def adversarial_validate(cwd: str) -> dict:
    cmd = [
        "python",
        "-m",
        "unittest",
        "tests.test_antivirus_system",
        "tests.test_quantum_virus_curefirewall",
        "tests.test_security_integrity_layer",
        "-q",
    ]
    proc = subprocess.run(cmd, cwd=str(Path(cwd).resolve()), capture_output=True, text=True)
    report = {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
        "time_utc": _utc_now(),
    }
    _save(_root(cwd) / "adversarial_validation.json", report)
    return report

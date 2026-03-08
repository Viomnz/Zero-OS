from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "native_store" / "enterprise_ops.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _default_state() -> dict:
    return {
        "signing": {
            "provider": {"type": "kms", "name": "aws-kms", "key_ref": "", "hsm_enabled": False},
            "trusted_signers": [],
            "last_sign_utc": "",
        },
        "vendor_channels": {
            "microsoft": {"configured": False, "tenant": "", "submission_status": "not_configured"},
            "apple": {"configured": False, "team_id": "", "notarization_status": "not_configured"},
            "google_play": {"configured": False, "project": "", "track_status": "not_configured"},
            "app_store_connect": {"configured": False, "issuer": "", "submission_status": "not_configured"},
        },
        "backend_prod": {
            "ha_replicas": 0,
            "tls_enabled": False,
            "monitoring": False,
            "alerting": False,
            "durable_storage": False,
            "dr_strategy": "none",
        },
        "desktop_prod": {
            "native_binary": False,
            "updater_live": False,
            "install_service_live": False,
            "os_registration_live": False,
            "crash_reporting_live": False,
        },
        "secrets_platform": {"provider": "", "certificate_authority": "", "revocation_enabled": False},
        "ops_governance": {"on_call_team": [], "release_approvers": [], "change_freeze": False},
        "deployed_testing": {"target": "", "last_run_utc": "", "passed": False},
    }


def _load(cwd: str) -> dict:
    path = _state_path(cwd)
    if not path.exists():
        data = _default_state()
        _save(cwd, data)
        return data
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _save(cwd: str, state: dict) -> None:
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def status(cwd: str) -> dict:
    state = _load(cwd)
    ready = {
        "vendor_signing": bool(state["signing"]["provider"]["key_ref"]),
        "vendor_submission": all(v["configured"] for v in state["vendor_channels"].values()),
        "backend_prod": all(
            [
                state["backend_prod"]["ha_replicas"] >= 2,
                state["backend_prod"]["tls_enabled"],
                state["backend_prod"]["monitoring"],
                state["backend_prod"]["alerting"],
                state["backend_prod"]["durable_storage"],
                state["backend_prod"]["dr_strategy"] != "none",
            ]
        ),
        "desktop_prod": all(state["desktop_prod"].values()),
        "secrets_platform": bool(state["secrets_platform"]["provider"] and state["secrets_platform"]["certificate_authority"] and state["secrets_platform"]["revocation_enabled"]),
        "ops_governance": bool(state["ops_governance"]["on_call_team"] and state["ops_governance"]["release_approvers"]),
        "deployed_testing": bool(state["deployed_testing"]["target"] and state["deployed_testing"]["passed"]),
    }
    return {"ok": True, "readiness": ready, "state": state}


def signing_provider_set(cwd: str, provider_type: str, name: str, key_ref: str, hsm_enabled: bool) -> dict:
    state = _load(cwd)
    state["signing"]["provider"] = {"type": provider_type, "name": name, "key_ref": key_ref, "hsm_enabled": bool(hsm_enabled)}
    state["signing"]["last_sign_utc"] = _utc_now()
    _save(cwd, state)
    return {"ok": True, "signing": state["signing"]}


def vendor_channel_configure(cwd: str, channel: str, identity: str) -> dict:
    state = _load(cwd)
    key = channel.strip().lower()
    if key not in state["vendor_channels"]:
        return {"ok": False, "reason": "unknown channel"}
    entry = state["vendor_channels"][key]
    entry["configured"] = True
    if key == "microsoft":
        entry["tenant"] = identity
        entry["submission_status"] = "configured"
    elif key == "apple":
        entry["team_id"] = identity
        entry["notarization_status"] = "configured"
    elif key == "google_play":
        entry["project"] = identity
        entry["track_status"] = "configured"
    else:
        entry["issuer"] = identity
        entry["submission_status"] = "configured"
    _save(cwd, state)
    return {"ok": True, "channel": key, "config": entry}


def backend_prod_set(cwd: str, replicas: int, tls: bool, monitoring: bool, alerting: bool, durable_storage: bool, dr_strategy: str) -> dict:
    state = _load(cwd)
    state["backend_prod"] = {
        "ha_replicas": int(replicas),
        "tls_enabled": bool(tls),
        "monitoring": bool(monitoring),
        "alerting": bool(alerting),
        "durable_storage": bool(durable_storage),
        "dr_strategy": dr_strategy,
    }
    _save(cwd, state)
    return {"ok": True, "backend_prod": state["backend_prod"]}


def desktop_prod_set(cwd: str, native_binary: bool, updater_live: bool, install_service_live: bool, os_registration_live: bool, crash_reporting_live: bool) -> dict:
    state = _load(cwd)
    state["desktop_prod"] = {
        "native_binary": bool(native_binary),
        "updater_live": bool(updater_live),
        "install_service_live": bool(install_service_live),
        "os_registration_live": bool(os_registration_live),
        "crash_reporting_live": bool(crash_reporting_live),
    }
    _save(cwd, state)
    return {"ok": True, "desktop_prod": state["desktop_prod"]}


def secrets_platform_set(cwd: str, provider: str, certificate_authority: str, revocation_enabled: bool) -> dict:
    state = _load(cwd)
    state["secrets_platform"] = {
        "provider": provider,
        "certificate_authority": certificate_authority,
        "revocation_enabled": bool(revocation_enabled),
    }
    _save(cwd, state)
    return {"ok": True, "secrets_platform": state["secrets_platform"]}


def ops_governance_set(cwd: str, on_call_team: list[str], release_approvers: list[str], change_freeze: bool) -> dict:
    state = _load(cwd)
    state["ops_governance"] = {
        "on_call_team": on_call_team,
        "release_approvers": release_approvers,
        "change_freeze": bool(change_freeze),
    }
    _save(cwd, state)
    return {"ok": True, "ops_governance": state["ops_governance"]}


def deployed_test_record(cwd: str, target: str, passed: bool) -> dict:
    state = _load(cwd)
    state["deployed_testing"] = {"target": target, "last_run_utc": _utc_now(), "passed": bool(passed)}
    _save(cwd, state)
    return {"ok": True, "deployed_testing": state["deployed_testing"]}


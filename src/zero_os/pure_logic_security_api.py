from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zero_os import antivirus as legacy_antivirus
from zero_os.security_control_plane import load_state, mutate_state
from zero_os.security_signing import sign_antivirus_feed, verify_antivirus_feed


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legacy_policy_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "antivirus" / "policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_suppressions_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "antivirus" / "suppressions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_feed_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "antivirus" / "threat_feed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_policy_defaults() -> dict:
    return {
        "heuristic_threshold": 65,
        "auto_quarantine": False,
        "exclude_paths": [".git", ".zero_os/production/snapshots"],
        "exclude_extensions": [".png", ".jpg", ".jpeg", ".mp3", ".mp4"],
        "max_files_per_scan": 5000,
        "max_file_mb": 8,
        "archive_max_depth": 2,
        "archive_max_entries": 700,
        "restore_overwrite": False,
        "response_mode": "manual",
    }


def reconcile_security_projection(cwd: str) -> dict:
    """Project authoritative control-plane state into legacy scanner files.

    The legacy antivirus engine remains a mechanism. Its policy/suppression JSON
    files are compatibility projections and are overwritten from the protected
    Security Control Plane before supported scan paths execute.
    """
    state = load_state(cwd)
    policy = _legacy_policy_defaults()
    policy.update(dict(state.antivirus_policy))
    _legacy_policy_path(cwd).write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    suppressions = {"items": [dict(x) for x in state.suppressions]}
    _legacy_suppressions_path(cwd).write_text(json.dumps(suppressions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "control_revision": state.revision,
        "control_digest": state.digest(),
        "policy": policy,
        "suppression_count": len(state.suppressions),
        "epistemic_role": "control_plane_authoritative_legacy_files_are_projection_only",
    }


def policy_status(cwd: str) -> dict:
    return reconcile_security_projection(cwd)["policy"]


def _parse_policy_value(key: str, value: str):
    k = str(key).strip().lower()
    if k in {"heuristic_threshold", "max_files_per_scan", "max_file_mb", "archive_max_depth", "archive_max_entries"}:
        return max(0, int(value))
    if k in {"auto_quarantine", "restore_overwrite"}:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if k == "response_mode":
        v = str(value).strip().lower()
        if v not in {"manual", "quarantine_high", "quarantine_critical"}:
            raise ValueError("unsupported response_mode")
        return v
    if k in {"exclude_paths", "exclude_extensions"}:
        return [x.strip() for x in str(value).split(",") if x.strip()]
    raise ValueError("unsupported policy key")


def policy_set(cwd: str, key: str, value: str) -> dict:
    parsed = _parse_policy_value(key, value)
    result = mutate_state(cwd, "set_antivirus_policy", {"key": str(key).strip().lower(), "value": parsed})
    if not result.get("ok"):
        return result
    projection = reconcile_security_projection(cwd)
    return {"ok": True, "revision": result["revision"], "policy": projection["policy"]}


def suppression_list(cwd: str) -> dict:
    state = load_state(cwd)
    items = [dict(x) for x in state.suppressions]
    return {"ok": True, "count": len(items), "items": items, "control_revision": state.revision}


def suppression_add(cwd: str, signature_id: str, path_prefix: str = "", hours: int = 24) -> dict:
    now = datetime.now(timezone.utc)
    item = {
        "id": hashlib.sha256(f"{signature_id}|{path_prefix}|{now.isoformat()}".encode()).hexdigest()[:12],
        "signature_id": str(signature_id).strip(),
        "path_prefix": str(path_prefix).strip().replace("\\", "/"),
        "created_utc": now.isoformat(),
        "expires_utc": (now + timedelta(hours=max(1, int(hours)))).isoformat(),
    }
    result = mutate_state(cwd, "add_suppression", {"item": item})
    if not result.get("ok"):
        return result
    reconcile_security_projection(cwd)
    return {"ok": True, "revision": result["revision"], **item}


def suppression_remove(cwd: str, suppression_id: str) -> dict:
    result = mutate_state(cwd, "remove_suppression", {"id": str(suppression_id)})
    if not result.get("ok"):
        return result
    reconcile_security_projection(cwd)
    return {"ok": True, "revision": result["revision"], "removed_id": str(suppression_id)}


def threat_feed_status(cwd: str) -> dict:
    path = _legacy_feed_path(cwd)
    if not path.exists():
        path.write_text(json.dumps(legacy_antivirus.default_threat_feed(), indent=2) + "\n", encoding="utf-8")
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return legacy_antivirus.default_threat_feed()


def threat_feed_update(cwd: str) -> dict:
    # Feed mutation is security-control mutation. Reuse the policy_change handoff
    # by advancing the feed-key generation, then write the updated feed.
    result = mutate_state(cwd, "rotate_feed_key", {})
    if not result.get("ok"):
        return result
    current = threat_feed_status(cwd)
    current["updated_utc"] = _utc_now()
    current["version"] = int(current.get("version", 0)) + 1
    _legacy_feed_path(cwd).write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "revision": result["revision"], "feed": current}


def threat_feed_export_signed(cwd: str, out_path: str) -> dict:
    envelope = sign_antivirus_feed(cwd, threat_feed_status(cwd))
    target = Path(out_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "version": int(envelope.get("feed", {}).get("version", 0)),
        "key_generation": envelope.get("key_generation"),
        "control_revision": envelope.get("control_revision"),
    }


def threat_feed_import_signed(cwd: str, in_path: str) -> dict:
    path = Path(in_path).resolve()
    if not path.exists():
        return {"ok": False, "reason": "signed_feed_file_missing"}
    try:
        envelope = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "reason": "signed_feed_file_invalid"}
    current_version = int(threat_feed_status(cwd).get("version", 0))
    verified = verify_antivirus_feed(cwd, envelope, minimum_version=current_version)
    if not verified.get("ok"):
        return verified
    # Import changes a protected security input, so it still needs a fresh
    # policy_change authority handoff even when the signature is valid.
    authorization = mutate_state(cwd, "set_firewall_policy", {"key": "last_antivirus_feed_import_version", "value": verified["version"]})
    if not authorization.get("ok"):
        return authorization
    feed = dict(envelope.get("feed") or {})
    _legacy_feed_path(cwd).write_text(json.dumps(feed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "signature_valid": True, "version": verified["version"], "control_revision": authorization["revision"]}


def scan_target(cwd: str, target: str, *, scan_snapshot: dict | None = None) -> dict:
    projection = reconcile_security_projection(cwd)
    report = legacy_antivirus.scan_target(cwd, target, scan_snapshot=scan_snapshot)
    report["pure_logic_control_revision"] = projection["control_revision"]
    report["pure_logic_control_digest"] = projection["control_digest"]
    report["security_policy_authority"] = "security_control_plane"
    return report


def quarantine_file(cwd: str, rel_path: str, reason: str = "manual") -> dict:
    reconcile_security_projection(cwd)
    return legacy_antivirus.quarantine_file(cwd, rel_path, reason=reason)


def quarantine_list(cwd: str) -> dict:
    return legacy_antivirus.quarantine_list(cwd)


def quarantine_restore(cwd: str, item_id: str) -> dict:
    reconcile_security_projection(cwd)
    return legacy_antivirus.quarantine_restore(cwd, item_id)


def monitor_status(cwd: str) -> dict:
    return legacy_antivirus.monitor_status(cwd)


def monitor_set(cwd: str, enabled: bool, interval_seconds: int | None = None) -> dict:
    # Monitoring configuration changes security behavior. Require the same
    # constitutional policy-change handoff before delegating to the mechanism.
    result = mutate_state(cwd, "set_firewall_policy", {
        "key": "antivirus_monitor",
        "value": {"enabled": bool(enabled), "interval_seconds": interval_seconds},
    })
    if not result.get("ok"):
        return result
    out = legacy_antivirus.monitor_set(cwd, enabled, interval_seconds)
    out["control_revision"] = result["revision"]
    return out


def monitor_tick(cwd: str, target: str = ".") -> dict:
    reconcile_security_projection(cwd)
    return legacy_antivirus.monitor_tick(cwd, target)

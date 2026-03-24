from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
import os
from pathlib import Path

from zero_os.enterprise_security import edr_probe, integration_probe, integration_status
from zero_os.runtime_smart_logic import recovery_decision, rollout_decision
from zero_os.security_hardening import harden_apply
from zero_os.state_cache import flush_state_writes, load_json_state, queue_json_state


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "resilience"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load(path: Path, default):
    return load_json_state(path, default)


def _queue_save(path: Path, payload) -> None:
    queue_json_state(path, payload)


def _save_durable(path: Path, payload) -> None:
    queue_json_state(path, payload)
    flush_state_writes(paths=[path])


def _trust_files(cwd: str) -> list[Path]:
    base = Path(cwd).resolve()
    candidates = [
        base / ".zero_os" / "keys" / "trust_root.key",
        base / ".zero_os" / "runtime" / "trust_root.json",
        base / ".zero_os" / "keys" / "operator_actions.key",
        base / "laws" / "recursion_law.txt",
        base / "src" / "zero_os" / "core.py",
    ]
    return [p for p in candidates if p.exists()]


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(65536)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def kernel_driver_compromise_status(cwd: str) -> dict:
    base = Path(cwd).resolve()
    attested = (base / ".zero_os" / "runtime" / "tpm_attestation.json").exists()
    secure_boot_env = str(os.getenv("ZERO_OS_SECURE_BOOT_ATTESTED", "0")).strip().lower() in {"1", "true", "yes", "on"}
    checks = {
        "kernel_docs_present": (base / "docs" / "kernel" / "README.md").exists(),
        "driver_manifest_present": (base / "drivers" / "manifest.json").exists(),
        "trust_root_present": (base / ".zero_os" / "keys" / "trust_root.key").exists(),
        "core_file_present": (base / "src" / "zero_os" / "core.py").exists(),
        "secure_boot_attested": secure_boot_env or attested,
    }
    failed = [k for k, v in checks.items() if not v]
    out = {
        "ok": len(failed) == 0,
        "time_utc": _utc_now(),
        "compromise_signal": len(failed) > 0,
        "checks": checks,
        "failed_checks": failed,
    }
    _queue_save(_root(cwd) / "kernel_driver_status.json", out)
    return out


def kernel_driver_emergency_lockdown(cwd: str) -> dict:
    hard = harden_apply(cwd)
    out = {
        "ok": True,
        "time_utc": _utc_now(),
        "mode": "kernel_driver_emergency_lockdown",
        "hardening": hard,
    }
    _queue_save(_root(cwd) / "kernel_driver_lockdown.json", out)
    return out


def firmware_rootkit_scan(cwd: str) -> dict:
    base = Path(cwd).resolve()
    suspicious_paths = [
        base / "bootkit.bin",
        base / "rootkit.sys",
        base / ".zero_os" / "runtime" / "unsigned_boot.json",
    ]
    found = [str(p) for p in suspicious_paths if p.exists()]
    edr = edr_probe(cwd)
    out = {
        "ok": len(found) == 0,
        "time_utc": _utc_now(),
        "firmware_rootkit_signal": len(found) > 0,
        "found_artifacts": found,
        "edr_probe": edr,
        "notes": "Host-level firmware/rootkit assurance requires external EDR/TPM attestation.",
    }
    _queue_save(_root(cwd) / "firmware_rootkit_scan.json", out)
    return out


def external_outage_status(cwd: str) -> dict:
    integ = integration_status(cwd)
    items = integ.get("items", {}) if isinstance(integ, dict) else {}
    checks = {}
    outages = []
    for name in ("edr", "siem", "iam", "zerotrust"):
        item = items.get(name, {}) if isinstance(items, dict) else {}
        enabled = bool(item.get("enabled", False))
        if not enabled:
            checks[name] = {"enabled": False, "ok": True, "reason": "disabled"}
            continue
        p = integration_probe(cwd, name)
        ok = bool(p.get("ok", False))
        checks[name] = {"enabled": True, "ok": ok, "reason": p.get("reason", "")}
        if not ok:
            outages.append(name)
    out = {
        "ok": len(outages) == 0,
        "time_utc": _utc_now(),
        "outage_count": len(outages),
        "outages": outages,
        "checks": checks,
    }
    _queue_save(_root(cwd) / "external_outage_status.json", out)
    return out


def external_outage_failover_apply(cwd: str) -> dict:
    status = external_outage_status(cwd)
    logic = rollout_decision(cwd, "prod", True, int(status.get("outage_count", 0)))
    mode = {
        "enabled": True,
        "time_utc": _utc_now(),
        "reason": "external_outage" if status.get("outage_count", 0) > 0 else "none",
        "local_failsafe": {
            "enterprise_policy_lock": True,
            "strict_mode": True,
            "local_audit_only": True,
        },
    }
    _save_durable(_root(cwd) / "external_failover_mode.json", mode)
    return {"ok": True, "status": status, "failover": mode, "smart_logic": logic}


def immutable_trust_backup_create(cwd: str) -> dict:
    files = _trust_files(cwd)
    sid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = _root(cwd) / "immutable_trust" / sid
    dst.mkdir(parents=True, exist_ok=True)
    manifest = []
    base = Path(cwd).resolve()
    for f in files:
        rel = str(f.resolve().relative_to(base)).replace("\\", "/")
        to = dst / rel
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, to)
        manifest.append({"path": rel, "sha256": _digest(f)})
    payload = {
        "ok": True,
        "id": sid,
        "time_utc": _utc_now(),
        "file_count": len(manifest),
        "files": manifest,
    }
    offsite_env = str(os.getenv("ZERO_OS_OFFSITE_DIR", "")).strip()
    offsite_root = Path(offsite_env).expanduser() if offsite_env else Path(cwd).resolve() / ".zero_os" / "offsite"
    if not offsite_env:
        offsite_root = Path(cwd).resolve() / ".zero_os" / "offsite"
    offsite_dst = offsite_root / "immutable_trust" / sid
    offsite_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(dst, offsite_dst, dirs_exist_ok=True)
    payload["offsite_replica"] = str(offsite_dst)
    _save_durable(dst / "manifest.json", payload)
    _save_durable(_root(cwd) / "immutable_trust_latest.json", payload)
    return payload


def immutable_trust_backup_status(cwd: str) -> dict:
    root = _root(cwd) / "immutable_trust"
    ids = [p.name for p in root.iterdir() if p.is_dir()] if root.exists() else []
    latest = sorted(ids)[-1] if ids else ""
    return {"ok": True, "count": len(ids), "latest": latest}


def immutable_trust_recover(cwd: str, backup_id: str = "latest") -> dict:
    status = immutable_trust_backup_status(cwd)
    if status["count"] == 0:
        created = immutable_trust_backup_create(cwd)
        backup_id = created["id"]
    chosen = status["latest"] if backup_id == "latest" and status["latest"] else backup_id
    src = _root(cwd) / "immutable_trust" / chosen
    if not src.exists():
        logic = recovery_decision(cwd, False, False, "system")
        return {"ok": False, "reason": f"backup not found: {chosen}", "smart_logic": logic}
    logic = recovery_decision(cwd, True, True, "system")
    manifest = _load(src / "manifest.json", {})
    files = manifest.get("files", []) if isinstance(manifest, dict) else []
    base = Path(cwd).resolve()
    restored = []
    for rec in files:
        rel = str(rec.get("path", "")).strip()
        if not rel:
            continue
        from_p = src / rel
        to_p = base / rel
        if not from_p.exists():
            continue
        to_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(from_p, to_p)
        restored.append(rel)
    out = {"ok": True, "backup_id": chosen, "restored_count": len(restored), "restored": restored, "smart_logic": logic}
    _queue_save(_root(cwd) / "immutable_trust_recovery.json", out)
    return out

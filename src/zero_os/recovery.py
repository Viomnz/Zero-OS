from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _snapshots_root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "production" / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def zero_ai_backup_status(cwd: str) -> dict:
    root = _snapshots_root(cwd)
    snaps = [p for p in root.iterdir() if p.is_dir()] if root.exists() else []
    latest = sorted(snaps, key=lambda x: x.name)[-1].name if snaps else ""
    cure_backup = Path(cwd).resolve() / ".zero_os" / "backups" / "cure_firewall"
    return {
        "ok": True,
        "snapshot_count": len(snaps),
        "latest_snapshot": latest,
        "cure_firewall_backup_exists": cure_backup.exists(),
        "cure_firewall_backup_path": str(cure_backup),
    }


def zero_ai_backup_create(cwd: str) -> dict:
    base = Path(cwd).resolve()
    sid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = _snapshots_root(cwd) / sid
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for rel in ("ai_from_scratch", "src", "zero_os_config", "security"):
        src = base / rel
        if not src.exists():
            continue
        to = dst / rel
        if src.is_dir():
            shutil.copytree(src, to, dirs_exist_ok=True)
        else:
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, to)
        copied.append(rel)
    meta = {"id": sid, "time_utc": _utc_now(), "copied": copied}
    (dst / "snapshot.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, **meta}


def zero_ai_recover(cwd: str, snapshot_id: str = "latest") -> dict:
    base = Path(cwd).resolve()
    rt = _runtime(cwd)
    status_before = zero_ai_backup_status(cwd)
    if status_before["snapshot_count"] == 0:
        created = zero_ai_backup_create(cwd)
        chosen = created["id"]
    else:
        chosen = status_before["latest_snapshot"] if snapshot_id == "latest" else snapshot_id
    src = _snapshots_root(cwd) / chosen
    if not src.exists():
        return {"ok": False, "reason": f"snapshot not found: {chosen}"}

    # Isolation marker for orchestrators/tools.
    isolate = {
        "time_utc": _utc_now(),
        "status": "isolated",
        "reason": "zero_ai_recovery_initiated",
    }
    (rt / "zero_ai_isolation.json").write_text(json.dumps(isolate, indent=2) + "\n", encoding="utf-8")

    restored = []
    for rel in ("ai_from_scratch", "src", "zero_os_config", "security"):
        from_p = src / rel
        to_p = base / rel
        if not from_p.exists():
            continue
        if from_p.is_dir():
            shutil.copytree(from_p, to_p, dirs_exist_ok=True)
        else:
            to_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(from_p, to_p)
        restored.append(rel)

    report = {
        "ok": True,
        "time_utc": _utc_now(),
        "recovery_mode": "controlled",
        "snapshot_used": chosen,
        "restored": restored,
        "next_steps": [
            "run: python ai_from_scratch/daemon_ctl.py health",
            "run: python ai_from_scratch/daemon_ctl.py refresh-monitor",
            "if healthy, resume normal operations",
        ],
    }
    (rt / "zero_ai_recovery_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


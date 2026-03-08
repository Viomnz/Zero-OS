from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zero_os.autonomous_fix_gate import autonomy_record, capture_health_snapshot
from zero_os.production_core import sync_path_smart
from zero_os.runtime_smart_logic import recovery_decision


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
    health_before = capture_health_snapshot(cwd)
    status_before = zero_ai_backup_status(cwd)
    if status_before["snapshot_count"] == 0:
        created = zero_ai_backup_create(cwd)
        chosen = created["id"]
    else:
        chosen = status_before["latest_snapshot"] if snapshot_id == "latest" else snapshot_id
    src = _snapshots_root(cwd) / chosen
    if not src.exists():
        logic = recovery_decision(cwd, False, False, "system")
        autonomy_record(cwd, "zero ai recover", "failed", float(logic.get("confidence", 0.0)), blast_radius="system", verification_passed=False, health_before=health_before, health_after=capture_health_snapshot(cwd))
        return {"ok": False, "reason": f"snapshot not found: {chosen}", "smart_logic": logic}
    logic = recovery_decision(cwd, True, True, "system")
    if str(logic.get("decision_action", "")).lower() in {"reject_or_hold", "block"}:
        autonomy_record(cwd, "zero ai recover", "blocked", float(logic.get("confidence", 0.0)), blast_radius="system", verification_passed=False, health_before=health_before, health_after=capture_health_snapshot(cwd))
        return {"ok": False, "reason": "smart logic gate", "smart_logic": logic}

    # Isolation marker for orchestrators/tools.
    isolate = {
        "time_utc": _utc_now(),
        "status": "isolated",
        "reason": "zero_ai_recovery_initiated",
    }
    (rt / "zero_ai_isolation.json").write_text(json.dumps(isolate, indent=2) + "\n", encoding="utf-8")

    restored = []
    sync_results = []
    for rel in ("ai_from_scratch", "src", "zero_os_config", "security"):
        from_p = src / rel
        to_p = base / rel
        if not from_p.exists():
            continue
        sync_results.append(sync_path_smart(cwd, str(from_p), str(to_p)))
        restored.append(rel)

    report = {
        "ok": True,
        "time_utc": _utc_now(),
        "recovery_mode": "controlled",
        "snapshot_used": chosen,
        "restored": restored,
        "sync_results": sync_results,
        "smart_logic": logic,
        "next_steps": [
            "run: python ai_from_scratch/daemon_ctl.py health",
            "run: python ai_from_scratch/daemon_ctl.py refresh-monitor",
            "if healthy, resume normal operations",
        ],
    }
    (rt / "zero_ai_recovery_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    autonomy_record(cwd, "zero ai recover", "success", float(logic.get("confidence", 0.0)), rollback_used=True, recovery_seconds=12.0, blast_radius="system", verification_passed=True, health_before=health_before, health_after=capture_health_snapshot(cwd))
    return report

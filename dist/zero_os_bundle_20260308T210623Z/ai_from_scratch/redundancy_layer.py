from __future__ import annotations

import json
import shutil
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _backup_root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "redundancy"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_redundancy(cwd: str, min_backups: int = 2) -> dict:
    rt = _runtime(cwd)
    root = _backup_root(cwd)
    critical = [
        rt / "internal_zero_reasoner_state.json",
        rt / "internal_zero_reasoner_memory.json",
        rt / "signal_reliability.json",
        rt / "decision_trace.json",
        rt / "learning_feedback.json",
    ]
    available = [p for p in critical if p.exists() and p.is_file()]

    backups = []
    for idx in range(max(1, int(min_backups))):
        slot = root / f"backup_{idx+1}"
        slot.mkdir(parents=True, exist_ok=True)
        copied = []
        for src in available:
            dst = slot / src.name
            shutil.copy2(src, dst)
            copied.append(src.name)
        backups.append({"slot": slot.name, "copied": copied, "count": len(copied)})

    primary_ok = len(available) > 0
    failover_ready = sum(1 for b in backups if b["count"] > 0) >= max(1, int(min_backups))
    active = "primary" if primary_ok else ("backup_1" if failover_ready else "degraded")

    out = {
        "ok": bool(primary_ok or failover_ready),
        "primary_ok": primary_ok,
        "failover_ready": failover_ready,
        "active_module": active,
        "critical_available": [p.name for p in available],
        "backup_count": len(backups),
        "backups": backups,
    }
    _save(rt / "redundancy_layer.json", out)
    return out


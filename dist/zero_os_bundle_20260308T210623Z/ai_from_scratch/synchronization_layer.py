from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


STATE_FILES = (
    "boot_initialization.json",
    "boundary_scope.json",
    "checkpoint_integrity.json",
    "calibration.json",
    "degradation_detection.json",
    "context_awareness.json",
    "knowledge_model.json",
    "signal_reliability.json",
)


def _runtime_dir(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _collect_existing(runtime: Path, names: Iterable[str]) -> list[Path]:
    found: list[Path] = []
    for name in names:
        f = runtime / name
        if f.exists():
            found.append(f)
    return found


def run_synchronization(base: str, max_skew_seconds: float = 300.0) -> dict:
    base_path = Path(base)
    runtime = _runtime_dir(base_path)
    files = _collect_existing(runtime, STATE_FILES)
    if not files:
        stamp = runtime / "sync_state.json"
        payload = {
            "ok": True,
            "synchronized": True,
            "reason": "no state files yet",
            "max_skew_seconds": float(max_skew_seconds),
            "observed_files": [],
            "stale_modules": [],
            "actions": {"sync_stamp_updated": True},
        }
        stamp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload

    times = {f.name: f.stat().st_mtime for f in files}
    newest = max(times.values())
    stale = [name for name, ts in times.items() if (newest - ts) > max_skew_seconds]

    payload = {
        "ok": len(stale) == 0,
        "synchronized": len(stale) == 0,
        "reason": "aligned" if len(stale) == 0 else "state skew detected",
        "max_skew_seconds": float(max_skew_seconds),
        "observed_files": sorted(times.keys()),
        "stale_modules": sorted(stale),
        "actions": {"sync_stamp_updated": True},
    }
    (runtime / "sync_state.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


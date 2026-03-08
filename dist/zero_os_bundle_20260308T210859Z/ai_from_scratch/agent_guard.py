from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


CRITICAL_FILES = [
    "ai_from_scratch/daemon.py",
    "ai_from_scratch/daemon_ctl.py",
    "src/zero_os/cure_firewall.py",
    "src/zero_os/capabilities/system.py",
    "src/zero_os/hyperlayer/__init__.py",
    "src/zero_os/hyperlayer/contracts.py",
    "src/zero_os/hyperlayer/runtime_core.py",
    "src/zero_os/hyperlayer/adapters/__init__.py",
    "src/zero_os/hyperlayer/adapters/base.py",
    "src/zero_os/hyperlayer/adapters/windows.py",
    "src/zero_os/hyperlayer/adapters/linux.py",
    "src/zero_os/hyperlayer/adapters/macos.py",
]


def trusted_root(base: Path) -> Path:
    p = base / ".zero_os" / "runtime" / "trusted_files"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def baseline_path(base: Path) -> Path:
    p = base / ".zero_os" / "runtime" / "agent_integrity_baseline.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def health_path(base: Path) -> Path:
    p = base / ".zero_os" / "runtime" / "agent_health.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def quarantine_compromise(base: Path, health_report: dict) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = base / ".zero_os" / "quarantine" / stamp
    files_dir = root / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for item in health_report.get("mismatches", []):
        rel = item.get("file", "")
        if not rel:
            continue
        src = (base / rel).resolve()
        if src.exists() and src.is_file():
            dst = files_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)

    manifest = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "reason": "agent_integrity_compromised",
        "copied_files": copied,
        "missing_files": health_report.get("missing", []),
        "mismatches": health_report.get("mismatches", []),
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "quarantine_dir": str(root),
        "manifest": str(manifest_path),
        "copied_files": copied,
    }


def build_baseline(base: Path) -> dict:
    files = {}
    trusted = trusted_root(base)
    for rel in CRITICAL_FILES:
        p = (base / rel).resolve()
        if p.exists() and p.is_file():
            files[rel] = _sha256(p)
            dst = trusted / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    baseline_path(base).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def check_health(base: Path) -> dict:
    bpath = baseline_path(base)
    if not bpath.exists():
        baseline = build_baseline(base)
    else:
        baseline = json.loads(bpath.read_text(encoding="utf-8", errors="replace"))

    expected = baseline.get("files", {})
    mismatches = []
    missing = []
    for rel, exp_hash in expected.items():
        p = (base / rel).resolve()
        if not p.exists():
            missing.append(rel)
            continue
        got = _sha256(p)
        if got != exp_hash:
            mismatches.append({"file": rel, "expected": exp_hash, "actual": got})

    healthy = not mismatches and not missing
    report = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "healthy": healthy,
        "missing": missing,
        "mismatches": mismatches,
    }
    health_path(base).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def restore_compromised(base: Path, health_report: dict) -> dict:
    trusted = trusted_root(base)
    restored = []
    failed = []

    targets = set(health_report.get("missing", []))
    for item in health_report.get("mismatches", []):
        rel = item.get("file", "")
        if rel:
            targets.add(rel)

    for rel in sorted(targets):
        src = trusted / rel
        dst = (base / rel).resolve()
        if not src.exists() or not src.is_file():
            failed.append({"file": rel, "reason": "trusted snapshot missing"})
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(rel)

    result = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "restored_files": restored,
        "failed": failed,
    }
    restore_log = base / ".zero_os" / "runtime" / "agent_restore.json"
    restore_log.parent.mkdir(parents=True, exist_ok=True)
    restore_log.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result

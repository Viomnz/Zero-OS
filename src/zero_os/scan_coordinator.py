from __future__ import annotations

import hashlib
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from zero_os.state_registry import boot_state_registry, get_state_store, update_state_store


_SKIP_ROOT_NAMES = {
    ".git",
    ".zero_os",
    "__pycache__",
    ".venv",
    ".pytest_cache",
    "venv",
    "node_modules",
}

_FIREWALL_SUFFIXES = {
    ".py",
    ".ps1",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
}

_PREFERRED_FIREWALL_PATHS = (
    "src/main.py",
    "src/zero_os/__init__.py",
    "README.md",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_snapshot(target: str = ".") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_utc": "",
        "target": str(target or "."),
        "max_files": 0,
        "file_count": 0,
        "added_path_count": 0,
        "removed_path_count": 0,
        "changed_path_count": 0,
        "unchanged_path_count": 0,
        "changed_paths": [],
        "inventory": {},
        "hash_cache": {},
        "hash_cache_entry_count": 0,
        "hash_cache_hit_count": 0,
        "hash_cache_miss_count": 0,
        "preferred_antivirus_target": ".",
        "preferred_firewall_targets": [],
    }


def _normalize_target(base: Path, raw_target: str) -> str:
    target_text = str(raw_target or ".").strip() or "."
    if target_text in {".", "./"}:
        return "."
    candidate = Path(target_text)
    resolved = (base / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        return str(resolved.relative_to(base)).replace("\\", "/")
    except ValueError:
        return target_text.replace("\\", "/")


def _resolve_target(base: Path, raw_target: str) -> Path:
    target_text = str(raw_target or ".").strip() or "."
    candidate = Path(target_text)
    return (base / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()


def _snapshot_recent(snapshot: dict[str, Any], *, seconds: int = 5) -> bool:
    generated = str(snapshot.get("generated_utc", "") or "").strip()
    if not generated:
        return False
    try:
        parsed = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - parsed.astimezone(timezone.utc) <= timedelta(seconds=max(1, int(seconds)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(base: Path, target: Path, *, max_files: int) -> list[Path]:
    if target.is_file():
        return [target]
    if not target.exists() or not target.is_dir():
        return []

    files: list[Path] = []
    for root, dirnames, filenames in os.walk(target):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in _SKIP_ROOT_NAMES and not name.startswith(".tmp")
        ]
        root_path = Path(root)
        for filename in filenames:
            path = root_path / filename
            files.append(path)
            if len(files) >= max_files:
                return files
    return files


def _inventory_for_files(base: Path, files: list[Path]) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for path in files:
        try:
            rel = str(path.resolve().relative_to(base)).replace("\\", "/")
            stat = path.stat()
        except (OSError, ValueError):
            continue
        inventory[rel] = {
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "suffix": str(path.suffix.lower()),
        }
    return inventory


def _preferred_antivirus_target(target: str, inventory: dict[str, dict[str, Any]]) -> str:
    if target not in {"", "."}:
        return target
    if any(path == "src" or path.startswith("src/") for path in inventory):
        return "src"
    return "."


def _preferred_firewall_targets(inventory: dict[str, dict[str, Any]], *, limit: int = 25) -> list[str]:
    chosen: list[str] = []
    for rel in _PREFERRED_FIREWALL_PATHS:
        if rel in inventory and rel not in chosen:
            chosen.append(rel)
    def priority(rel: str) -> tuple[int, str]:
        if rel.startswith("src/"):
            return (0, rel)
        if rel.startswith("tests/"):
            return (1, rel)
        if rel.startswith("docs/") or rel.startswith("laws/"):
            return (2, rel)
        if rel.startswith(".github/workflows/"):
            return (3, rel)
        if rel.startswith("."):
            return (6, rel)
        return (4, rel)

    for rel in sorted(inventory, key=priority):
        if len(chosen) >= limit:
            break
        suffix = str((inventory.get(rel) or {}).get("suffix", "")).lower()
        if suffix not in _FIREWALL_SUFFIXES or rel in chosen:
            continue
        chosen.append(rel)
    return chosen


def snapshot_target_paths(scan_snapshot: dict[str, Any] | None, target: str, *, max_files: int | None = None) -> list[str]:
    snapshot = dict(scan_snapshot or {})
    inventory = dict(snapshot.get("inventory") or {})
    if not inventory:
        return []
    normalized = str(target or ".").replace("\\", "/").strip() or "."
    selected: list[str]
    if normalized in {"", ".", "./"}:
        selected = sorted(inventory)
    elif normalized in inventory:
        selected = [normalized]
    else:
        prefix = normalized.rstrip("/").rstrip("\\")
        prefix = f"{prefix}/" if prefix else ""
        selected = [path for path in sorted(inventory) if path.startswith(prefix)]
    if max_files is not None:
        return selected[: max(0, int(max_files))]
    return selected


def snapshot_hash_for_path(
    scan_snapshot: dict[str, Any] | None,
    rel_path: str,
    *,
    size: int | None = None,
    mtime_ns: int | None = None,
) -> str:
    snapshot = dict(scan_snapshot or {})
    cache = dict(snapshot.get("hash_cache") or {})
    entry = dict(cache.get(str(rel_path).replace("\\", "/")) or {})
    digest = str(entry.get("sha256", "") or "")
    if not digest:
        return ""
    if size is not None and int(entry.get("size", -1)) != int(size):
        return ""
    if mtime_ns is not None and int(entry.get("mtime_ns", -1)) != int(mtime_ns):
        return ""
    return digest


def workspace_scan_summary(scan_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = dict(scan_snapshot or {})
    return {
        "target": str(snapshot.get("target", ".") or "."),
        "file_count": int(snapshot.get("file_count", 0) or 0),
        "changed_path_count": int(snapshot.get("changed_path_count", 0) or 0),
        "hash_cache_entry_count": int(snapshot.get("hash_cache_entry_count", 0) or 0),
        "hash_cache_hit_count": int(snapshot.get("hash_cache_hit_count", 0) or 0),
        "hash_cache_miss_count": int(snapshot.get("hash_cache_miss_count", 0) or 0),
        "preferred_antivirus_target": str(snapshot.get("preferred_antivirus_target", ".") or "."),
        "preferred_firewall_target_count": len(list(snapshot.get("preferred_firewall_targets") or [])),
        "preferred_firewall_targets": list(snapshot.get("preferred_firewall_targets") or []),
        "generated_utc": str(snapshot.get("generated_utc", "") or ""),
    }


def workspace_scan_status(cwd: str) -> dict[str, Any]:
    boot_state_registry(cwd, names=["workspace_scan_snapshot"])
    snapshot = get_state_store(cwd, "workspace_scan_snapshot", _default_snapshot("."))
    if not snapshot:
        snapshot = _default_snapshot(".")
    return {"ok": True, **workspace_scan_summary(snapshot)}


def build_workspace_scan_snapshot(
    cwd: str,
    *,
    target: str = ".",
    max_files: int = 8000,
    force: bool = False,
) -> dict[str, Any]:
    base = Path(cwd).resolve()
    normalized_target = _normalize_target(base, target)
    boot_state_registry(cwd, names=["workspace_scan_snapshot"])
    previous = get_state_store(cwd, "workspace_scan_snapshot", _default_snapshot(normalized_target))
    if not isinstance(previous, dict):
        previous = _default_snapshot(normalized_target)

    if (
        not force
        and str(previous.get("target", ".")) == normalized_target
        and bool(previous.get("inventory"))
        and _snapshot_recent(previous)
    ):
        return previous

    target_path = _resolve_target(base, target)
    files = _iter_files(base, target_path, max_files=max(1, int(max_files)))
    inventory = _inventory_for_files(base, files)
    previous_inventory = dict(previous.get("inventory") or {}) if str(previous.get("target", ".")) == normalized_target else {}
    previous_hash_cache = dict(previous.get("hash_cache") or {})

    current_paths = set(inventory)
    previous_paths = set(previous_inventory)
    added = sorted(current_paths - previous_paths)
    removed = sorted(previous_paths - current_paths)
    changed = sorted(
        path
        for path in current_paths & previous_paths
        if dict(previous_inventory.get(path) or {}) != dict(inventory.get(path) or {})
    )
    unchanged_count = max(0, len(current_paths) - len(added) - len(changed))

    firewall_targets = _preferred_firewall_targets(inventory)
    hash_targets = set(firewall_targets)
    if normalized_target not in {"", "."} and normalized_target in inventory:
        hash_targets.add(normalized_target)
    for rel in (added + changed)[:16]:
        hash_targets.add(rel)

    hash_cache: dict[str, dict[str, Any]] = {}
    hash_cache_hit_count = 0
    hash_cache_miss_count = 0
    for rel, raw_cached in previous_hash_cache.items():
        entry = dict(inventory.get(rel) or {})
        cached = dict(raw_cached or {})
        if not entry:
            continue
        if (
            str(cached.get("sha256", "")).strip()
            and int(cached.get("size", -1)) == int(entry.get("size", -1))
            and int(cached.get("mtime_ns", -1)) == int(entry.get("mtime_ns", -1))
        ):
            hash_cache[rel] = cached
    for rel in sorted(hash_targets):
        entry = dict(inventory.get(rel) or {})
        if not entry:
            continue
        cached = dict(hash_cache.get(rel) or {})
        if str(cached.get("sha256", "")).strip():
            hash_cache_hit_count += 1
            continue
        digest = _sha256(base / rel)
        hash_cache[rel] = {
            "sha256": digest,
            "size": int(entry.get("size", 0) or 0),
            "mtime_ns": int(entry.get("mtime_ns", 0) or 0),
        }
        hash_cache_miss_count += 1

    snapshot = {
        "schema_version": 1,
        "generated_utc": _utc_now(),
        "target": normalized_target,
        "max_files": int(max_files),
        "file_count": len(inventory),
        "added_path_count": len(added),
        "removed_path_count": len(removed),
        "changed_path_count": len(changed),
        "unchanged_path_count": unchanged_count,
        "changed_paths": (added + changed)[:200],
        "inventory": deepcopy(inventory),
        "hash_cache": deepcopy(hash_cache),
        "hash_cache_entry_count": len(hash_cache),
        "hash_cache_hit_count": hash_cache_hit_count,
        "hash_cache_miss_count": hash_cache_miss_count,
        "preferred_antivirus_target": _preferred_antivirus_target(normalized_target, inventory),
        "preferred_firewall_targets": firewall_targets,
    }
    update_state_store(cwd, "workspace_scan_snapshot", lambda current, payload=deepcopy(snapshot): deepcopy(payload))
    return snapshot

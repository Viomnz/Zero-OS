from __future__ import annotations

import json
import py_compile
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from zero_os.autonomous_fix_gate import autonomy_record, capture_health_snapshot
from zero_os.fast_path_cache import cached_compute
from zero_os.production_core import snapshot_restore, sync_path_smart
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


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _snapshot_index_path(cwd: str) -> Path:
    return _snapshots_root(cwd) / "index.json"


def _find_any(root: Path, patterns: list[str]) -> str:
    for pattern in patterns:
        for match in root.glob(pattern):
            if match.exists():
                return str(match)
    return ""


def _verify_python_tree(root: Path) -> dict:
    signature = {"root": str(root), "stamp": _python_tree_stamp(root)}

    def _compute() -> dict:
        if not root.exists():
            return {"ok": True, "root": str(root), "checked_files": 0, "errors": []}
        errors: list[dict] = []
        checked = 0
        for path in sorted(root.rglob("*.py")):
            checked += 1
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append({"path": str(path), "error": str(exc)})
            except Exception as exc:  # pragma: no cover
                errors.append({"path": str(path), "error": str(exc)})
        return {
            "ok": not errors,
            "root": str(root),
            "checked_files": checked,
            "error_count": len(errors),
            "errors": errors[:25],
        }

    verification, cache_meta = cached_compute(
        "recovery_python_tree_verification",
        str(root),
        signature,
        _compute,
        ttl_seconds=None,
    )
    verification = deepcopy(verification)
    verification["verification_cache_hit"] = bool(cache_meta.get("hit", False))
    return verification


def _required_recovery_files(base: Path) -> dict[str, list[str]]:
    groups = {
        "src": [
            "src/zero_os/contradiction_engine.py",
            "src/zero_os/flow_monitor.py",
            "src/zero_os/smart_workspace.py",
            "src/zero_os/subsystem_controller_registry.py",
            "src/zero_os/zero_ai_pressure_harness.py",
            "src/zero_os/zero_ai_control_workflows.py",
        ],
        "ai_from_scratch": [
            "ai_from_scratch/benchmark_history.py",
            "ai_from_scratch/benchmark_suite.py",
            "ai_from_scratch/eval.py",
            "ai_from_scratch/tokenizer_dataset.py",
        ],
    }
    required: dict[str, list[str]] = {}
    for group, paths in groups.items():
        present = [rel for rel in paths if (base / rel).exists()]
        required[group] = present
    return required


def _snapshot_module_compatibility(base: Path, snapshot_root: Path) -> dict:
    required = _required_recovery_files(base)
    missing: dict[str, list[str]] = {}
    for group, paths in required.items():
        group_missing: list[str] = []
        for rel in paths:
            snapshot_path = snapshot_root / Path(rel)
            if not snapshot_path.exists():
                group_missing.append(rel.replace("\\", "/"))
        if group_missing:
            missing[group] = group_missing
    return {
        "ok": not bool(missing),
        "required": required,
        "missing": missing,
    }


def _python_tree_stamp(root: Path) -> dict:
    if not root.exists():
        return {"exists": False, "file_count": 0, "total_size": 0, "newest_mtime_ns": 0}
    file_count = 0
    total_size = 0
    newest_mtime_ns = 0
    for path in sorted(root.rglob("*.py")):
        try:
            stat = path.stat()
        except OSError:
            continue
        file_count += 1
        total_size += int(stat.st_size)
        newest_mtime_ns = max(newest_mtime_ns, int(stat.st_mtime_ns))
    return {
        "exists": True,
        "file_count": file_count,
        "total_size": total_size,
        "newest_mtime_ns": newest_mtime_ns,
    }


def _snapshot_candidate(base: Path, snapshot_root: Path) -> dict:
    signature = {
        "snapshot_root": str(snapshot_root),
        "src_stamp": _python_tree_stamp(snapshot_root / "src"),
        "ai_stamp": _python_tree_stamp(snapshot_root / "ai_from_scratch"),
        "required": _required_recovery_files(base),
    }

    def _compute() -> dict:
        verification = {
            "snapshot_src": _verify_python_tree(snapshot_root / "src"),
            "snapshot_ai_from_scratch": _verify_python_tree(snapshot_root / "ai_from_scratch"),
        }
        compatibility = _snapshot_module_compatibility(base, snapshot_root)
        python_ok = verification["snapshot_src"]["ok"] and verification["snapshot_ai_from_scratch"]["ok"]
        compatible = python_ok and compatibility["ok"]
        return {
            "snapshot_id": snapshot_root.name,
            "path": str(snapshot_root),
            "has_snapshot_meta": (snapshot_root / "snapshot.json").exists(),
            "verification": verification,
            "module_compatibility": compatibility,
            "python_ok": python_ok,
            "compatible": compatible,
        }

    candidate, cache_meta = cached_compute(
        "recovery_snapshot_candidate",
        str(snapshot_root),
        signature,
        _compute,
        ttl_seconds=None,
    )
    candidate = deepcopy(candidate)
    candidate["verification_cache_hit"] = bool(cache_meta.get("hit", False))
    return candidate


def _load_snapshot_index(cwd: str) -> dict:
    return _load(
        _snapshot_index_path(cwd),
        {
            "schema_version": 2,
            "pinned_snapshot_ids": [],
            "known_good_snapshot_ids": [],
            "quarantined_snapshot_ids": [],
            "latest_compatible_snapshot_id": "",
            "updated_utc": "",
        },
    )


def _snapshot_index_signature(cwd: str) -> dict:
    index = _load_snapshot_index(cwd)
    return {
        "pinned_snapshot_ids": list(index.get("pinned_snapshot_ids", [])),
        "known_good_snapshot_ids": list(index.get("known_good_snapshot_ids", [])),
        "quarantined_snapshot_ids": list(index.get("quarantined_snapshot_ids", [])),
    }


def _save_snapshot_index(cwd: str, payload: dict) -> dict:
    payload["updated_utc"] = _utc_now()
    _snapshot_index_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _compute_quarantined_snapshot_ids(index: dict, candidates: list[dict]) -> list[str]:
    pinned = {str(item) for item in index.get("pinned_snapshot_ids", []) if str(item)}
    known_good = {str(item) for item in index.get("known_good_snapshot_ids", []) if str(item)}
    compatible = {str(candidate.get("snapshot_id", "")) for candidate in candidates if bool(candidate.get("compatible", False))}
    incompatible = {str(candidate.get("snapshot_id", "")) for candidate in candidates if not bool(candidate.get("compatible", False))}
    existing = {
        str(item)
        for item in index.get("quarantined_snapshot_ids", [])
        if str(item)
    }
    known_ids = compatible | incompatible
    next_ids = ((existing | incompatible) & known_ids) - compatible - pinned - known_good
    return sorted(next_ids)


def _update_snapshot_index_if_needed(
    cwd: str,
    index: dict,
    latest_compatible_snapshot_id: str,
    quarantined_snapshot_ids: list[str] | None = None,
) -> dict:
    next_payload = deepcopy(index)
    next_payload["latest_compatible_snapshot_id"] = str(latest_compatible_snapshot_id or "")
    if quarantined_snapshot_ids is not None:
        next_payload["quarantined_snapshot_ids"] = list(quarantined_snapshot_ids)
    current_signature = {
        "pinned_snapshot_ids": list(index.get("pinned_snapshot_ids", [])),
        "known_good_snapshot_ids": list(index.get("known_good_snapshot_ids", [])),
        "quarantined_snapshot_ids": list(index.get("quarantined_snapshot_ids", [])),
        "latest_compatible_snapshot_id": str(index.get("latest_compatible_snapshot_id", "") or ""),
    }
    next_signature = {
        "pinned_snapshot_ids": list(next_payload.get("pinned_snapshot_ids", [])),
        "known_good_snapshot_ids": list(next_payload.get("known_good_snapshot_ids", [])),
        "quarantined_snapshot_ids": list(next_payload.get("quarantined_snapshot_ids", [])),
        "latest_compatible_snapshot_id": str(next_payload.get("latest_compatible_snapshot_id", "") or ""),
    }
    if current_signature == next_signature and _snapshot_index_path(cwd).exists():
        return index
    return _save_snapshot_index(cwd, next_payload)


def zero_ai_recovery_inventory(cwd: str) -> dict:
    base = Path(cwd).resolve()
    root = _snapshots_root(cwd)
    snapshot_dirs = sorted([path for path in root.iterdir() if path.is_dir()], key=lambda item: item.name, reverse=True) if root.exists() else []

    def _inventory_signature() -> dict:
        return {
            "snapshots": [
                {
                    "snapshot_id": snapshot_root.name,
                    "has_snapshot_meta": (snapshot_root / "snapshot.json").exists(),
                    "src_stamp": _python_tree_stamp(snapshot_root / "src"),
                    "ai_stamp": _python_tree_stamp(snapshot_root / "ai_from_scratch"),
                }
                for snapshot_root in snapshot_dirs
            ],
            "required": _required_recovery_files(base),
            "index": _snapshot_index_signature(cwd),
        }

    def _compute_inventory() -> dict:
        candidates = [_snapshot_candidate(base, snapshot_root) for snapshot_root in snapshot_dirs]
        compatible = [candidate for candidate in candidates if candidate.get("compatible", False)]
        incompatible = [candidate for candidate in candidates if not candidate.get("compatible", False)]
        index = _load_snapshot_index(cwd)
        latest = snapshot_dirs[0].name if snapshot_dirs else ""
        latest_compatible = compatible[0]["snapshot_id"] if compatible else ""
        quarantined_snapshot_ids = _compute_quarantined_snapshot_ids(index, candidates)
        saved_index = _update_snapshot_index_if_needed(cwd, index, latest_compatible, quarantined_snapshot_ids)
        quarantined_ids = {str(item) for item in saved_index.get("quarantined_snapshot_ids", []) if str(item)}
        quarantined = [candidate for candidate in incompatible if str(candidate.get("snapshot_id", "")) in quarantined_ids]
        active_incompatible = [candidate for candidate in incompatible if str(candidate.get("snapshot_id", "")) not in quarantined_ids]
        return {
            "ok": True,
            "snapshot_count": len(candidates),
            "latest_snapshot_id": latest,
            "latest_compatible_snapshot_id": latest_compatible,
            "compatible_count": len(compatible),
            "incompatible_count": len(incompatible),
            "pinned_snapshot_ids": list(saved_index.get("pinned_snapshot_ids", [])),
            "known_good_snapshot_ids": list(saved_index.get("known_good_snapshot_ids", [])),
            "quarantined_snapshot_ids": list(saved_index.get("quarantined_snapshot_ids", [])),
            "quarantined_count": len(quarantined),
            "active_incompatible_count": len(active_incompatible),
            "compatible_snapshots": compatible,
            "active_incompatible_snapshots": active_incompatible,
            "quarantined_snapshots": quarantined,
            "incompatible_snapshots": incompatible,
        }

    inventory, cache_meta = cached_compute(
        "recovery_inventory",
        str(root),
        _inventory_signature,
        _compute_inventory,
        ttl_seconds=None,
    )
    inventory = deepcopy(inventory)
    inventory["inventory_cache_hit"] = bool(cache_meta.get("hit", False))
    return inventory


def zero_ai_backup_pin(cwd: str, snapshot_id: str, known_good: bool = False) -> dict:
    inventory = zero_ai_recovery_inventory(cwd)
    known_ids = {item["snapshot_id"] for item in inventory.get("compatible_snapshots", []) + inventory.get("incompatible_snapshots", [])}
    if snapshot_id not in known_ids:
        return {"ok": False, "reason": "snapshot_not_found", "snapshot_id": snapshot_id}
    index = _load_snapshot_index(cwd)
    pinned = list(index.get("pinned_snapshot_ids", []))
    if snapshot_id not in pinned:
        pinned.append(snapshot_id)
    index["pinned_snapshot_ids"] = pinned
    index["quarantined_snapshot_ids"] = [item for item in list(index.get("quarantined_snapshot_ids", [])) if str(item) != snapshot_id]
    if known_good:
        known_good_ids = list(index.get("known_good_snapshot_ids", []))
        if snapshot_id not in known_good_ids:
            known_good_ids.append(snapshot_id)
        index["known_good_snapshot_ids"] = known_good_ids
    _save_snapshot_index(cwd, index)
    return {"ok": True, "snapshot_id": snapshot_id, "known_good": bool(known_good), "index": index}


def zero_ai_backup_prune(cwd: str, keep_latest: int = 2) -> dict:
    inventory = zero_ai_recovery_inventory(cwd)
    root = _snapshots_root(cwd)
    keep_count = max(1, int(keep_latest or 2))
    index = _load_snapshot_index(cwd)
    pinned = set(str(item) for item in index.get("pinned_snapshot_ids", []))
    protected = {str(item) for item in index.get("known_good_snapshot_ids", [])}
    latest = str(inventory.get("latest_snapshot_id", "") or "")
    latest_compatible = str(inventory.get("latest_compatible_snapshot_id", "") or "")
    if latest:
        protected.add(latest)
    if latest_compatible:
        protected.add(latest_compatible)
    protected.update(pinned)

    ordered = [item["snapshot_id"] for item in inventory.get("compatible_snapshots", []) + inventory.get("incompatible_snapshots", [])]
    protected.update(ordered[:keep_count])
    removed: list[str] = []
    skipped: list[str] = []
    for snapshot_id in ordered[keep_count:]:
        if snapshot_id in protected:
            skipped.append(snapshot_id)
            continue
        path = root / snapshot_id
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(snapshot_id)
    refreshed = zero_ai_recovery_inventory(cwd)
    return {
        "ok": True,
        "removed_snapshot_ids": removed,
        "skipped_snapshot_ids": skipped,
        "remaining_snapshot_count": refreshed.get("snapshot_count", 0),
        "latest_snapshot_id": refreshed.get("latest_snapshot_id", ""),
        "latest_compatible_snapshot_id": refreshed.get("latest_compatible_snapshot_id", ""),
    }


def _select_snapshot(base: Path, snapshot_id: str) -> dict:
    cwd = str(base)
    root = _snapshots_root(cwd)
    if snapshot_id != "latest":
        if not any(path.is_dir() for path in root.iterdir()) if root.exists() else True:
            return {"ok": False, "reason": "no_snapshots"}
        candidate = root / snapshot_id
        if not candidate.exists():
            return {"ok": False, "reason": "snapshot_not_found", "snapshot_id": snapshot_id}
        selected = _snapshot_candidate(base, candidate)
        return {"ok": True, "selected": selected, "candidates": [selected]}

    inventory = zero_ai_recovery_inventory(cwd)
    if int(inventory.get("snapshot_count", 0) or 0) == 0:
        return {"ok": False, "reason": "no_snapshots"}
    candidates = inventory.get("compatible_snapshots", []) + inventory.get("incompatible_snapshots", [])
    latest_compatible = str(inventory.get("latest_compatible_snapshot_id", "") or "")
    selected = next((candidate for candidate in candidates if candidate.get("snapshot_id") == latest_compatible), None)
    if selected:
        return {"ok": True, "selected": selected, "candidates": candidates}
    return {"ok": False, "reason": "no_compatible_snapshot", "candidates": candidates}


def _restore_tree_replace(source: Path, target: Path) -> dict:
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target, dirs_exist_ok=True)
        files = sum(1 for item in source.rglob("*") if item.is_file())
        return {
            "ok": True,
            "source": str(source),
            "target": str(target),
            "kind": "dir",
            "decision": "replace",
            "strategy": "trusted_snapshot_replace",
            "files": files,
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {
        "ok": True,
        "source": str(source),
        "target": str(target),
        "kind": "file",
        "decision": "replace",
        "strategy": "trusted_snapshot_replace",
        "files": 1,
    }


def _merge_json_snapshot_preferred(current, snapshot):
    if isinstance(current, dict) and isinstance(snapshot, dict):
        merged = dict(current)
        for key, value in snapshot.items():
            if key in merged:
                merged[key] = _merge_json_snapshot_preferred(merged[key], value)
            else:
                merged[key] = value
        return merged
    if isinstance(current, list) and isinstance(snapshot, list):
        merged = list(snapshot)
        for item in current:
            if item not in merged:
                merged.append(item)
        return merged
    return snapshot if snapshot not in (None, "", [], {}) else current


def _restore_config_tree(source: Path, target: Path) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    results = []
    for item in sorted(source.rglob("*")):
        rel = item.relative_to(source)
        dst = target / rel
        if item.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if item.suffix.lower() == ".json" and dst.exists():
            try:
                snapshot_payload = json.loads(item.read_text(encoding="utf-8", errors="replace"))
                current_payload = json.loads(dst.read_text(encoding="utf-8", errors="replace"))
                merged_payload = _merge_json_snapshot_preferred(current_payload, snapshot_payload)
                dst.write_text(json.dumps(merged_payload, indent=2) + "\n", encoding="utf-8")
                results.append(
                    {
                        "ok": True,
                        "source": str(item),
                        "target": str(dst),
                        "kind": "file",
                        "decision": "merge",
                        "strategy": "snapshot_preferred_json_merge",
                    }
                )
                continue
            except Exception:
                pass
        shutil.copy2(item, dst)
        results.append(
            {
                "ok": True,
                "source": str(item),
                "target": str(dst),
                "kind": "file",
                "decision": "replace",
                "strategy": "config_copy",
            }
        )
    return {
        "ok": all(bool(result.get("ok", False)) for result in results) if results else True,
        "source": str(source),
        "target": str(target),
        "kind": "dir",
        "files": len(results),
        "merged": sum(1 for result in results if result.get("decision") == "merge"),
        "replaced": sum(1 for result in results if result.get("decision") == "replace"),
        "skipped": 0,
        "results": results[:200],
    }


def zero_ai_backup_status(cwd: str) -> dict:
    root = _snapshots_root(cwd)
    snaps = [p for p in root.iterdir() if p.is_dir()] if root.exists() else []
    latest = sorted(snaps, key=lambda x: x.name)[-1].name if snaps else ""
    inventory = zero_ai_recovery_inventory(cwd)
    latest_compatible = str(inventory.get("latest_compatible_snapshot_id", "") or "")
    compatible_count = int(inventory.get("compatible_count", 0) or 0)
    quarantined_count = int(inventory.get("quarantined_count", 0) or 0)
    active_incompatible_count = int(inventory.get("active_incompatible_count", 0) or 0)
    cure_backup = Path(cwd).resolve() / ".zero_os" / "backups" / "cure_firewall"
    detected_paths = {
        "snapshot_meta": _find_any(root, ["*/snapshot.json"]),
        "cure_backup": _find_any(Path(cwd).resolve() / ".zero_os" / "backups", ["cure_firewall/**/*", "cure_firewall/*"]),
    }
    next_priority = []
    if not snaps and not cure_backup.exists() and not detected_paths["snapshot_meta"]:
        next_priority.append("run: zero ai backup create")
    if snaps and compatible_count <= 0:
        next_priority.append("restore snapshot trust: create or pin one compatible recovery snapshot")
    if quarantined_count > 0:
        next_priority.append("review quarantined incompatible snapshots and prune older recovery noise")
    return {
        "ok": True,
        "snapshot_count": len(snaps),
        "latest_snapshot": latest,
        "compatible_count": compatible_count,
        "trusted_snapshot_count": compatible_count,
        "latest_compatible_snapshot_id": latest_compatible,
        "preferred_snapshot_id": latest_compatible or latest,
        "quarantined_snapshot_count": quarantined_count,
        "active_incompatible_snapshot_count": active_incompatible_count,
        "quarantined_snapshot_ids": list(inventory.get("quarantined_snapshot_ids", [])),
        "active_incompatible_snapshot_ids": [item.get("snapshot_id", "") for item in list(inventory.get("active_incompatible_snapshots", []))],
        "recovery_surface_state": "trusted" if compatible_count > 0 and active_incompatible_count == 0 else "degraded",
        "cure_firewall_backup_exists": cure_backup.exists() or bool(detected_paths["cure_backup"]),
        "cure_firewall_backup_path": str(cure_backup),
        "detected_paths": detected_paths,
        "next_priority": next_priority,
    }


def zero_ai_backup_create(cwd: str) -> dict:
    base = Path(cwd).resolve()
    sid_base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sid = sid_base
    dst = _snapshots_root(cwd) / sid
    counter = 1
    while dst.exists():
        sid = f"{sid_base}_{counter:02d}"
        dst = _snapshots_root(cwd) / sid
        counter += 1
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


def _recovery_decision_failed(cwd: str, health_before: dict, reason: str, **extra) -> dict:
    logic = recovery_decision(cwd, False, False, "system")
    autonomy_record(
        cwd,
        "zero ai recover",
        "failed",
        float(logic.get("confidence", 0.0)),
        blast_radius="system",
        verification_passed=False,
        health_before=health_before,
        health_after=capture_health_snapshot(cwd),
    )
    payload = {"ok": False, "reason": reason, "smart_logic": logic}
    payload.update(extra)
    return payload


def _recovery_decision_blocked(cwd: str, health_before: dict, logic: dict, reason: str, **extra) -> dict:
    autonomy_record(
        cwd,
        "zero ai recover",
        "blocked",
        float(logic.get("confidence", 0.0)),
        blast_radius="system",
        verification_passed=False,
        health_before=health_before,
        health_after=capture_health_snapshot(cwd),
    )
    payload = {"ok": False, "reason": reason, "smart_logic": logic}
    payload.update(extra)
    return payload


def _write_recovery_report(cwd: str, report: dict) -> dict:
    (_runtime(cwd) / "zero_ai_recovery_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def zero_ai_recovery_preflight(cwd: str, snapshot_id: str = "latest") -> dict:
    base = Path(cwd).resolve()
    health_before = capture_health_snapshot(cwd)
    status_before = zero_ai_backup_status(cwd)
    selected_snapshot: dict
    chosen = ""

    if status_before["snapshot_count"] == 0:
        created = zero_ai_backup_create(cwd)
        chosen = created["id"]
        selected_snapshot = _snapshot_candidate(base, _snapshots_root(cwd) / chosen)
    else:
        selection = _select_snapshot(base, snapshot_id)
        if not selection.get("ok", False):
            return _recovery_decision_failed(cwd, health_before, str(selection.get("reason", "snapshot_not_found")), selection=selection)
        selected_snapshot = dict(selection["selected"])
        chosen = str(selected_snapshot.get("snapshot_id", ""))

    src = _snapshots_root(cwd) / chosen
    if not src.exists():
        return _recovery_decision_failed(cwd, health_before, f"snapshot not found: {chosen}")

    logic = recovery_decision(cwd, True, True, "system")
    if str(logic.get("decision_action", "")).lower() in {"reject_or_hold", "block"}:
        return _recovery_decision_blocked(cwd, health_before, logic, "smart logic gate")

    verification_before = dict(selected_snapshot.get("verification") or {})
    module_compatibility = dict(selected_snapshot.get("module_compatibility") or {})
    if not verification_before["snapshot_src"]["ok"] or not verification_before["snapshot_ai_from_scratch"]["ok"]:
        return _recovery_decision_blocked(
            cwd,
            health_before,
            logic,
            "snapshot_verification_failed",
            snapshot_used=chosen,
            verification=verification_before,
        )
    if not module_compatibility["ok"]:
        return _recovery_decision_blocked(
            cwd,
            health_before,
            logic,
            "snapshot_module_set_incompatible",
            snapshot_used=chosen,
            verification=verification_before,
            module_compatibility=module_compatibility,
        )

    return {
        "ok": True,
        "stage": "preflight",
        "time_utc": _utc_now(),
        "snapshot_used": chosen,
        "snapshot_root": str(src),
        "snapshot_selection": {"selected": selected_snapshot},
        "verification": {"before": verification_before},
        "module_compatibility": module_compatibility,
        "smart_logic": logic,
        "health_before": health_before,
        "verification_cached": True,
    }


def _restore_selected_snapshot(cwd: str, preflight: dict) -> dict:
    base = Path(cwd).resolve()
    rt = _runtime(cwd)
    chosen = str(preflight.get("snapshot_used", ""))
    src = Path(str(preflight.get("snapshot_root", "")))
    logic = dict(preflight.get("smart_logic") or {})
    health_before = dict(preflight.get("health_before") or {})
    verification_before = dict((preflight.get("verification") or {}).get("before") or {})
    module_compatibility = dict(preflight.get("module_compatibility") or {})

    rollback_snapshot = zero_ai_backup_create(cwd)

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
        if rel in {"ai_from_scratch", "src"}:
            sync_results.append(_restore_tree_replace(from_p, to_p))
        elif rel == "zero_os_config":
            sync_results.append(_restore_config_tree(from_p, to_p))
        else:
            sync_results.append(sync_path_smart(cwd, str(from_p), str(to_p)))
        restored.append(rel)

    verification_after = {
        "live_src": _verify_python_tree(base / "src"),
        "live_ai_from_scratch": _verify_python_tree(base / "ai_from_scratch"),
    }
    verification_ok = verification_after["live_src"]["ok"] and verification_after["live_ai_from_scratch"]["ok"]
    if not verification_ok:
        rollback = snapshot_restore(cwd, rollback_snapshot["id"])
        report = {
            "ok": False,
            "time_utc": _utc_now(),
            "recovery_mode": "controlled",
            "stage": "commit",
            "snapshot_used": chosen,
            "restored": restored,
            "sync_results": sync_results,
            "smart_logic": logic,
            "rollback_snapshot": rollback_snapshot["id"],
            "rollback": rollback,
            "verification": {"before": verification_before, "after": verification_after},
            "module_compatibility": module_compatibility,
            "reason": "post_recovery_verification_failed",
        }
        _write_recovery_report(cwd, report)
        autonomy_record(
            cwd,
            "zero ai recover",
            "failed",
            float(logic.get("confidence", 0.0)),
            rollback_used=True,
            blast_radius="system",
            verification_passed=False,
            health_before=health_before,
            health_after=capture_health_snapshot(cwd),
        )
        return report

    report = {
        "ok": True,
        "time_utc": _utc_now(),
        "recovery_mode": "controlled",
        "stage": "commit",
        "snapshot_used": chosen,
        "snapshot_selection": dict(preflight.get("snapshot_selection") or {}),
        "restored": restored,
        "sync_results": sync_results,
        "smart_logic": logic,
        "rollback_snapshot": rollback_snapshot["id"],
        "verification": {"before": verification_before, "after": verification_after},
        "module_compatibility": module_compatibility,
        "verification_cached": bool(preflight.get("verification_cached", False)),
        "next_steps": [
            "run: python ai_from_scratch/daemon_ctl.py health",
            "run: python ai_from_scratch/daemon_ctl.py refresh-monitor",
            "if healthy, resume normal operations",
        ],
    }
    _write_recovery_report(cwd, report)
    autonomy_record(
        cwd,
        "zero ai recover",
        "success",
        float(logic.get("confidence", 0.0)),
        rollback_used=True,
        recovery_seconds=12.0,
        blast_radius="system",
        verification_passed=True,
        health_before=health_before,
        health_after=capture_health_snapshot(cwd),
    )
    return report


def zero_ai_recover(cwd: str, snapshot_id: str = "latest") -> dict:
    preflight = zero_ai_recovery_preflight(cwd, snapshot_id)
    if not preflight.get("ok", False):
        return preflight
    return _restore_selected_snapshot(cwd, preflight)

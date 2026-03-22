from __future__ import annotations

import json
import py_compile
import shutil
from datetime import datetime, timezone
from pathlib import Path

from zero_os.autonomous_fix_gate import autonomy_record, capture_health_snapshot
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


def _snapshot_candidate(base: Path, snapshot_root: Path) -> dict:
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


def _load_snapshot_index(cwd: str) -> dict:
    return _load(
        _snapshot_index_path(cwd),
        {
            "schema_version": 1,
            "pinned_snapshot_ids": [],
            "known_good_snapshot_ids": [],
            "latest_compatible_snapshot_id": "",
            "updated_utc": "",
        },
    )


def _save_snapshot_index(cwd: str, payload: dict) -> dict:
    payload["updated_utc"] = _utc_now()
    _snapshot_index_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def zero_ai_recovery_inventory(cwd: str) -> dict:
    base = Path(cwd).resolve()
    root = _snapshots_root(cwd)
    snapshots = sorted([path for path in root.iterdir() if path.is_dir()], key=lambda item: item.name, reverse=True) if root.exists() else []
    candidates = [_snapshot_candidate(base, snapshot_root) for snapshot_root in snapshots]
    compatible = [candidate for candidate in candidates if candidate.get("compatible", False)]
    incompatible = [candidate for candidate in candidates if not candidate.get("compatible", False)]
    index = _load_snapshot_index(cwd)
    latest = snapshots[0].name if snapshots else ""
    latest_compatible = compatible[0]["snapshot_id"] if compatible else ""
    index["latest_compatible_snapshot_id"] = latest_compatible
    _save_snapshot_index(cwd, index)
    return {
        "ok": True,
        "snapshot_count": len(candidates),
        "latest_snapshot_id": latest,
        "latest_compatible_snapshot_id": latest_compatible,
        "compatible_count": len(compatible),
        "incompatible_count": len(incompatible),
        "pinned_snapshot_ids": list(index.get("pinned_snapshot_ids", [])),
        "known_good_snapshot_ids": list(index.get("known_good_snapshot_ids", [])),
        "compatible_snapshots": compatible,
        "incompatible_snapshots": incompatible,
    }


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
    inventory = zero_ai_recovery_inventory(cwd)
    if int(inventory.get("snapshot_count", 0) or 0) == 0:
        return {"ok": False, "reason": "no_snapshots"}
    root = _snapshots_root(cwd)
    if snapshot_id != "latest":
        candidate = root / snapshot_id
        if not candidate.exists():
            return {"ok": False, "reason": "snapshot_not_found", "snapshot_id": snapshot_id}
        selected = _snapshot_candidate(base, candidate)
        return {"ok": True, "selected": selected, "candidates": [selected]}

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
    cure_backup = Path(cwd).resolve() / ".zero_os" / "backups" / "cure_firewall"
    detected_paths = {
        "snapshot_meta": _find_any(root, ["*/snapshot.json"]),
        "cure_backup": _find_any(Path(cwd).resolve() / ".zero_os" / "backups", ["cure_firewall/**/*", "cure_firewall/*"]),
    }
    next_priority = []
    if not snaps and not cure_backup.exists() and not detected_paths["snapshot_meta"]:
        next_priority.append("run: zero ai backup create")
    return {
        "ok": True,
        "snapshot_count": len(snaps),
        "latest_snapshot": latest,
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


def zero_ai_recover(cwd: str, snapshot_id: str = "latest") -> dict:
    base = Path(cwd).resolve()
    rt = _runtime(cwd)
    health_before = capture_health_snapshot(cwd)
    status_before = zero_ai_backup_status(cwd)
    if status_before["snapshot_count"] == 0:
        created = zero_ai_backup_create(cwd)
        chosen = created["id"]
        selected_snapshot = _snapshot_candidate(base, _snapshots_root(cwd) / chosen)
    else:
        selection = _select_snapshot(base, snapshot_id)
        if not selection.get("ok", False):
            logic = recovery_decision(cwd, False, False, "system")
            autonomy_record(cwd, "zero ai recover", "failed", float(logic.get("confidence", 0.0)), blast_radius="system", verification_passed=False, health_before=health_before, health_after=capture_health_snapshot(cwd))
            return {"ok": False, "reason": str(selection.get("reason", "snapshot_not_found")), "selection": selection, "smart_logic": logic}
        selected_snapshot = dict(selection["selected"])
        chosen = str(selected_snapshot.get("snapshot_id", ""))
    src = _snapshots_root(cwd) / chosen
    if not src.exists():
        logic = recovery_decision(cwd, False, False, "system")
        autonomy_record(cwd, "zero ai recover", "failed", float(logic.get("confidence", 0.0)), blast_radius="system", verification_passed=False, health_before=health_before, health_after=capture_health_snapshot(cwd))
        return {"ok": False, "reason": f"snapshot not found: {chosen}", "smart_logic": logic}
    logic = recovery_decision(cwd, True, True, "system")
    if str(logic.get("decision_action", "")).lower() in {"reject_or_hold", "block"}:
        autonomy_record(cwd, "zero ai recover", "blocked", float(logic.get("confidence", 0.0)), blast_radius="system", verification_passed=False, health_before=health_before, health_after=capture_health_snapshot(cwd))
        return {"ok": False, "reason": "smart logic gate", "smart_logic": logic}

    verification_before = dict(selected_snapshot.get("verification") or {})
    module_compatibility = dict(selected_snapshot.get("module_compatibility") or {})
    if not verification_before["snapshot_src"]["ok"] or not verification_before["snapshot_ai_from_scratch"]["ok"]:
        autonomy_record(cwd, "zero ai recover", "blocked", float(logic.get("confidence", 0.0)), blast_radius="system", verification_passed=False, health_before=health_before, health_after=capture_health_snapshot(cwd))
        return {"ok": False, "reason": "snapshot_verification_failed", "snapshot_used": chosen, "verification": verification_before, "smart_logic": logic}
    if not module_compatibility["ok"]:
        autonomy_record(cwd, "zero ai recover", "blocked", float(logic.get("confidence", 0.0)), blast_radius="system", verification_passed=False, health_before=health_before, health_after=capture_health_snapshot(cwd))
        return {
            "ok": False,
            "reason": "snapshot_module_set_incompatible",
            "snapshot_used": chosen,
            "verification": verification_before,
            "module_compatibility": module_compatibility,
            "smart_logic": logic,
        }

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
            "snapshot_used": chosen,
            "restored": restored,
            "sync_results": sync_results,
            "smart_logic": logic,
            "rollback_snapshot": rollback_snapshot["id"],
            "rollback": rollback,
            "verification": {"before": verification_before, "after": verification_after},
            "reason": "post_recovery_verification_failed",
        }
        (rt / "zero_ai_recovery_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        autonomy_record(cwd, "zero ai recover", "failed", float(logic.get("confidence", 0.0)), rollback_used=True, blast_radius="system", verification_passed=False, health_before=health_before, health_after=capture_health_snapshot(cwd))
        return report

    report = {
        "ok": True,
        "time_utc": _utc_now(),
        "recovery_mode": "controlled",
        "snapshot_used": chosen,
        "snapshot_selection": {"selected": selected_snapshot},
        "restored": restored,
        "sync_results": sync_results,
        "smart_logic": logic,
        "rollback_snapshot": rollback_snapshot["id"],
        "verification": {"before": verification_before, "after": verification_after},
        "module_compatibility": module_compatibility,
        "next_steps": [
            "run: python ai_from_scratch/daemon_ctl.py health",
            "run: python ai_from_scratch/daemon_ctl.py refresh-monitor",
            "if healthy, resume normal operations",
        ],
    }
    (rt / "zero_ai_recovery_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    autonomy_record(cwd, "zero ai recover", "success", float(logic.get("confidence", 0.0)), rollback_used=True, recovery_seconds=12.0, blast_radius="system", verification_passed=True, health_before=health_before, health_after=capture_health_snapshot(cwd))
    return report

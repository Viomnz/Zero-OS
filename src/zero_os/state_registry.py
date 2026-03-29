from __future__ import annotations

import json
import hashlib
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from zero_os.state_cache import load_json_state

_LOCK = threading.RLock()
_REGISTRY: dict[str, dict[str, dict[str, Any]]] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cwd_key(cwd: str) -> str:
    return str(Path(cwd).resolve())


def _transaction_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "runtime" / "state_registry_transaction.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _transaction_workspace(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "runtime" / "state_registry_transactions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _transaction_payload_dir(cwd: str, transaction_id: str) -> Path:
    path = _transaction_workspace(cwd) / str(transaction_id or "unknown")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _transaction_quarantine_dir(cwd: str, transaction_id: str) -> Path:
    path = _transaction_workspace(cwd) / "quarantine" / str(transaction_id or "unknown")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_specs(cwd: str) -> dict[str, dict[str, Any]]:
    base = Path(cwd).resolve()
    runtime = base / ".zero_os" / "runtime"
    assistant = base / ".zero_os" / "assistant"
    self_derivation = assistant / "self_derivation"
    pressure = assistant / "pressure_harness"
    return {
        "runtime_loop": {
            "path": runtime / "runtime_loop_state.json",
            "default": {},
            "hot": True,
        },
        "runtime_agent": {
            "path": runtime / "runtime_agent_state.json",
            "default": {},
            "hot": True,
        },
        "phase_runtime_status": {
            "path": runtime / "phase_runtime_status.json",
            "default": {},
            "hot": True,
        },
        "zero_engine_status": {
            "path": runtime / "zero_engine_status.json",
            "default": {},
            "hot": True,
        },
        "world_model_latest": {
            "path": runtime / "world_model_latest.json",
            "default": {},
            "hot": True,
        },
        "observation_stream": {
            "path": runtime / "observation_stream.json",
            "default": {},
            "hot": True,
        },
        "workspace_scan_snapshot": {
            "path": runtime / "workspace_scan_snapshot.json",
            "default": {},
            "hot": True,
        },
        "maintenance_state": {
            "path": assistant / "maintenance_orchestrator.json",
            "default": {},
            "hot": True,
        },
        "self_derivation_memory": {
            "path": self_derivation / "memory.json",
            "default": {},
            "hot": True,
        },
        "self_derivation_latest": {
            "path": self_derivation / "latest.json",
            "default": {},
            "hot": True,
        },
        "pressure_latest": {
            "path": pressure / "latest.json",
            "default": {},
            "hot": True,
        },
    }


def _revision_for_path(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "mtime_ns": 0, "size": 0, "content_sha256": ""}
    try:
        content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        content_sha256 = ""
    return {
        "exists": True,
        "mtime_ns": int(stat.st_mtime_ns),
        "size": int(stat.st_size),
        "content_sha256": content_sha256,
    }


def _clone_revision(revision: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(revision or {})
    return {
        "exists": bool(raw.get("exists", False)),
        "mtime_ns": int(raw.get("mtime_ns", 0) or 0),
        "size": int(raw.get("size", 0) or 0),
        "content_sha256": str(raw.get("content_sha256", "") or ""),
    }


def _revisions_equal(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    return _clone_revision(left) == _clone_revision(right)


def _write_json(path: Path, payload: Any) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2) + "\n"
    path.write_text(serialized, encoding="utf-8")
    return _revision_for_path(path)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return deepcopy(default)
    return raw if isinstance(raw, type(default)) else deepcopy(default)


def _entry_from_disk(spec: dict[str, Any]) -> dict[str, Any]:
    payload = load_json_state(spec["path"], spec["default"])
    revision = _revision_for_path(spec["path"])
    now = _utc_now()
    return {
        "path": str(spec["path"]),
        "payload": deepcopy(payload),
        "default": deepcopy(spec["default"]),
        "hot": bool(spec.get("hot", False)),
        "dirty": False,
        "conflict": False,
        "conflict_reason": "",
        "base_revision": revision,
        "disk_revision": revision,
        "last_loaded_utc": now,
        "last_updated_utc": now,
    }


def _apply_conflict_from_disk(entry: dict[str, Any], spec: dict[str, Any], reason: str) -> dict[str, Any]:
    local_payload = deepcopy(entry.get("payload", spec["default"]))
    disk_payload = load_json_state(spec["path"], spec["default"])
    revision = _revision_for_path(spec["path"])
    now = _utc_now()
    entry["conflicted_local_payload"] = local_payload
    entry["payload"] = deepcopy(disk_payload)
    entry["dirty"] = False
    entry["conflict"] = True
    entry["conflict_reason"] = str(reason)
    entry["base_revision"] = revision
    entry["disk_revision"] = revision
    entry["last_loaded_utc"] = now
    entry["last_updated_utc"] = now
    return entry


def _registry_for_cwd(cwd: str) -> dict[str, dict[str, Any]]:
    return _REGISTRY.setdefault(_cwd_key(cwd), {})


def _payload_path_for_store(cwd: str, transaction_id: str, name: str) -> Path:
    return _transaction_payload_dir(cwd, transaction_id) / f"{str(name)}.json"


def _cleanup_transaction_payloads(cwd: str, transaction_id: str) -> None:
    payload_dir = _transaction_workspace(cwd) / str(transaction_id or "unknown")
    if not payload_dir.exists():
        return
    for child in payload_dir.iterdir():
        try:
            if child.is_file():
                child.unlink()
        except OSError:
            continue
    try:
        payload_dir.rmdir()
    except OSError:
        pass


def _quarantine_transaction_locked(
    cwd: str,
    transaction: dict[str, Any],
    *,
    reason: str,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tx_id = str(transaction.get("transaction_id", "") or "unknown")
    journal_path = _transaction_path(cwd)
    quarantine_dir = _transaction_quarantine_dir(cwd, tx_id)
    payload_dir = _transaction_workspace(cwd) / tx_id
    quarantined = dict(transaction)
    quarantined["status"] = "quarantined"
    quarantined["quarantine_reason"] = str(reason)
    quarantined["quarantine_utc"] = _utc_now()
    quarantined["quarantine_path"] = str(quarantine_dir)
    quarantined["quarantine_details"] = list(details or [])
    if payload_dir.exists():
        target_payload_dir = quarantine_dir / "payloads"
        try:
            payload_dir.rename(target_payload_dir)
        except OSError:
            quarantined["quarantine_details"].append(
                {"reason": "payload_quarantine_move_failed", "source": str(payload_dir), "target": str(target_payload_dir)}
            )
    _write_json(quarantine_dir / "transaction.json", quarantined)
    _write_json(journal_path, quarantined)
    return {
        "ok": False,
        "recovered": False,
        "quarantined": True,
        "transaction_id": tx_id,
        "reason": str(reason),
        "quarantine_path": str(quarantine_dir),
        "status": "quarantined",
    }


def _ensure_entry_locked(cwd: str, name: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    specs = _store_specs(cwd)
    spec = specs.get(name)
    if spec is None:
        return None, None
    registry = _registry_for_cwd(cwd)
    entry = registry.get(name)
    if entry is None:
        entry = _entry_from_disk(spec)
        registry[name] = entry
        return entry, spec

    current_revision = _revision_for_path(spec["path"])
    if bool(entry.get("dirty", False)):
        if not _revisions_equal(current_revision, entry.get("base_revision")):
            entry = _apply_conflict_from_disk(entry, spec, "disk revision changed while local state was dirty")
            registry[name] = entry
        return entry, spec

    if _revisions_equal(current_revision, entry.get("disk_revision")):
        return entry, spec

    entry = _entry_from_disk(spec)
    registry[name] = entry
    return entry, spec


def recover_state_registry_transaction(cwd: str) -> dict[str, Any]:
    with _LOCK:
        return _recover_state_registry_transaction_locked(cwd)


def _recover_state_registry_transaction_locked(cwd: str) -> dict[str, Any]:
    journal_path = _transaction_path(cwd)
    transaction = _load_json(journal_path, {})
    if not isinstance(transaction, dict) or not transaction:
        return {"ok": True, "recovered": False, "quarantined": False, "status": "missing"}

    status = str(transaction.get("status", "") or "")
    tx_id = str(transaction.get("transaction_id", "") or "")
    if status in {"committed", "recovered", "quarantined", "conflict", "failed"}:
        if status in {"committed", "recovered"} and tx_id:
            _cleanup_transaction_payloads(cwd, tx_id)
        return {
            "ok": True,
            "recovered": False,
            "quarantined": False,
            "transaction_id": tx_id,
            "status": status or "unknown",
        }

    if status not in {"pending", "partial_failure"}:
        return {
            "ok": True,
            "recovered": False,
            "quarantined": False,
            "transaction_id": tx_id,
            "status": status or "unknown",
        }

    specs = _store_specs(cwd)
    store_names = [str(name) for name in list(transaction.get("store_names", [])) if str(name)]
    payload_paths = dict(transaction.get("payload_paths") or {})
    detected_live_commit_ids: list[dict[str, Any]] = []
    missing_payloads: list[dict[str, Any]] = []
    payloads: dict[str, Any] = {}

    for name in store_names:
        spec = specs.get(name)
        if spec is None:
            missing_payloads.append({"name": name, "reason": "unknown state store"})
            continue
        payload_path_text = str(payload_paths.get(name, "") or "")
        payload_path = Path(payload_path_text) if payload_path_text else _payload_path_for_store(cwd, tx_id, name)
        if not payload_path.exists():
            missing_payloads.append({"name": name, "path": str(payload_path), "reason": "missing staged payload"})
            continue
        payloads[name] = load_json_state(payload_path, spec["default"])
        current_payload = load_json_state(spec["path"], spec["default"])
        current_commit_id = ""
        if isinstance(current_payload, dict):
            current_commit_id = str(current_payload.get("control_plane_commit_id", "") or "")
        if current_commit_id and current_commit_id != tx_id:
            detected_live_commit_ids.append(
                {
                    "name": name,
                    "path": str(spec["path"]),
                    "current_commit_id": current_commit_id,
                }
            )

    if missing_payloads:
        return _quarantine_transaction_locked(
            cwd,
            transaction,
            reason="incomplete transaction missing staged payloads",
            details=missing_payloads,
        )

    if detected_live_commit_ids:
        return _quarantine_transaction_locked(
            cwd,
            transaction,
            reason="newer live control-plane truth already exists",
            details=detected_live_commit_ids,
        )

    registry = _registry_for_cwd(cwd)
    recovered_names: list[str] = []
    failures: list[dict[str, Any]] = []
    for name in store_names:
        spec = specs.get(name)
        if spec is None:
            failures.append({"name": name, "reason": "unknown state store"})
            continue
        payload = deepcopy(payloads.get(name, spec["default"]))
        try:
            next_revision = _write_json(spec["path"], payload)
        except Exception as exc:
            failures.append({"name": name, "path": str(spec["path"]), "reason": str(exc)})
            continue
        now = _utc_now()
        registry[name] = {
            "path": str(spec["path"]),
            "payload": deepcopy(payload),
            "default": deepcopy(spec["default"]),
            "hot": bool(spec.get("hot", False)),
            "dirty": False,
            "conflict": False,
            "conflict_reason": "",
            "base_revision": next_revision,
            "disk_revision": next_revision,
            "last_loaded_utc": now,
            "last_updated_utc": now,
        }
        recovered_names.append(name)

    if failures:
        transaction["written_names"] = list(recovered_names)
        transaction["failure_count"] = len(failures)
        transaction["failures"] = list(failures)
        transaction["status"] = "partial_failure"
        transaction["recovery_attempted_utc"] = _utc_now()
        _write_json(journal_path, transaction)
        return {
            "ok": False,
            "recovered": False,
            "quarantined": False,
            "transaction_id": tx_id,
            "status": "partial_failure",
            "failure_count": len(failures),
            "failures": failures,
        }

    transaction["written_names"] = list(recovered_names)
    transaction["status"] = "recovered"
    transaction["recovered_utc"] = _utc_now()
    transaction["recovered_names"] = list(recovered_names)
    _write_json(journal_path, transaction)
    _cleanup_transaction_payloads(cwd, tx_id)
    return {
        "ok": True,
        "recovered": True,
        "quarantined": False,
        "transaction_id": tx_id,
        "status": "recovered",
        "recovered_names": recovered_names,
    }


def boot_state_registry(cwd: str, *, names: list[str] | None = None) -> dict[str, Any]:
    specs = _store_specs(cwd)
    selected = names or [name for name, spec in specs.items() if bool(spec.get("hot", False))]
    loaded_names: list[str] = []
    with _LOCK:
        recovery = _recover_state_registry_transaction_locked(cwd)
        for name in selected:
            entry, _ = _ensure_entry_locked(cwd, name)
            if entry is not None:
                loaded_names.append(name)
    return {
        "ok": True,
        "cwd": _cwd_key(cwd),
        "loaded_count": len(loaded_names),
        "loaded_names": loaded_names,
        "transaction_recovery": recovery,
    }


def get_state_store(cwd: str, name: str, default: Any = None) -> Any:
    with _LOCK:
        entry, _ = _ensure_entry_locked(cwd, name)
        if entry is None:
            return deepcopy(default)
        return deepcopy(entry.get("payload", default))


def refresh_state_store(cwd: str, name: str) -> Any:
    specs = _store_specs(cwd)
    spec = specs.get(name)
    if spec is None:
        return {}
    with _LOCK:
        entry = _entry_from_disk(spec)
        _registry_for_cwd(cwd)[name] = entry
        return deepcopy(entry.get("payload", {}))


def put_state_store(
    cwd: str,
    name: str,
    payload: Any,
    *,
    flush: bool = False,
    expected_revision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with _LOCK:
        entry, spec = _ensure_entry_locked(cwd, name)
        if entry is None or spec is None:
            raise KeyError(f"unknown state store: {name}")
        current_revision = _revision_for_path(spec["path"])
        expected = _clone_revision(expected_revision if expected_revision is not None else entry.get("base_revision"))
        if not _revisions_equal(current_revision, expected):
            entry = _apply_conflict_from_disk(entry, spec, "disk revision changed before write")
            _registry_for_cwd(cwd)[name] = entry
            result = {
                "ok": False,
                "conflict": True,
                "name": name,
                "path": str(spec["path"]),
                "reason": entry["conflict_reason"],
                "expected_revision": expected,
                "current_revision": _clone_revision(entry.get("disk_revision")),
                "flush": {"ok": False, "flushed_count": 0},
            }
        else:
            now = _utc_now()
            entry["payload"] = deepcopy(payload)
            entry["dirty"] = True
            entry["conflict"] = False
            entry["conflict_reason"] = ""
            entry["base_revision"] = current_revision
            entry["disk_revision"] = current_revision
            entry["last_updated_utc"] = now
            result = {
                "ok": True,
                "conflict": False,
                "name": name,
                "path": str(spec["path"]),
                "revision": current_revision,
                "flush": {"ok": True, "flushed_count": 0},
            }
    if flush and bool(result.get("ok", False)):
        result["flush"] = flush_state_registry(cwd, names=[name])
    return result


def update_state_store(
    cwd: str,
    name: str,
    updater: Callable[[Any], Any],
    *,
    flush: bool = False,
) -> dict[str, Any]:
    with _LOCK:
        entry, spec = _ensure_entry_locked(cwd, name)
        if entry is None or spec is None:
            raise KeyError(f"unknown state store: {name}")
        if bool(entry.get("conflict", False)) or bool(entry.get("dirty", False)):
            entry = _entry_from_disk(spec)
            _registry_for_cwd(cwd)[name] = entry
        current_revision = _revision_for_path(spec["path"])
        if not _revisions_equal(current_revision, entry.get("disk_revision")):
            entry = _entry_from_disk(spec)
            _registry_for_cwd(cwd)[name] = entry
            current_revision = _clone_revision(entry.get("disk_revision"))
        current_payload = deepcopy(entry.get("payload", spec["default"]))
        next_payload = updater(deepcopy(current_payload))
        if next_payload is None:
            next_payload = current_payload
        now = _utc_now()
        entry["payload"] = deepcopy(next_payload)
        entry["dirty"] = True
        entry["conflict"] = False
        entry["conflict_reason"] = ""
        entry["base_revision"] = current_revision
        entry["disk_revision"] = current_revision
        entry["last_updated_utc"] = now
        result = {
            "ok": True,
            "conflict": False,
            "name": name,
            "path": str(spec["path"]),
            "revision": current_revision,
            "flush": {"ok": True, "flushed_count": 0},
        }
    if flush:
        result["flush"] = flush_state_registry(cwd, names=[name])
    return result


def flush_state_registry(cwd: str, *, names: list[str] | None = None) -> dict[str, Any]:
    specs = _store_specs(cwd)
    selected_names = names or list(specs.keys())
    flushed: list[str] = []
    failures: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    with _LOCK:
        for name in selected_names:
            entry, spec = _ensure_entry_locked(cwd, name)
            if entry is None or spec is None or not bool(entry.get("dirty", False)):
                continue
            current_revision = _revision_for_path(spec["path"])
            if not _revisions_equal(current_revision, entry.get("base_revision")):
                expected_revision = _clone_revision(entry.get("base_revision"))
                entry = _apply_conflict_from_disk(entry, spec, "disk revision changed before flush")
                conflicts.append(
                    {
                        "name": name,
                        "path": str(spec["path"]),
                        "reason": entry["conflict_reason"],
                        "expected_revision": expected_revision,
                        "current_revision": _clone_revision(entry.get("disk_revision")),
                    }
                )
                continue
            try:
                next_revision = _write_json(spec["path"], entry.get("payload"))
            except Exception as exc:
                failures.append({"name": name, "path": str(spec["path"]), "reason": str(exc)})
                continue
            entry["dirty"] = False
            entry["conflict"] = False
            entry["conflict_reason"] = ""
            entry["base_revision"] = next_revision
            entry["disk_revision"] = next_revision
            entry["last_loaded_utc"] = _utc_now()
            entry["last_updated_utc"] = entry["last_loaded_utc"]
            flushed.append(str(spec["path"]))
        pending_write_count = 0
        conflict_count = 0
        for store in _registry_for_cwd(cwd).values():
            if bool(store.get("dirty", False)):
                pending_write_count += 1
            if bool(store.get("conflict", False)):
                conflict_count += 1
    return {
        "ok": len(failures) == 0 and len(conflicts) == 0,
        "flushed_count": len(flushed),
        "flushed_paths": flushed,
        "failure_count": len(failures),
        "failures": failures,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "pending_write_count": pending_write_count,
        "pending_conflict_count": conflict_count,
    }


def transaction_status(cwd: str) -> dict[str, Any]:
    payload = _load_json(_transaction_path(cwd), {})
    if not isinstance(payload, dict) or not payload:
        return {"present": False, "path": str(_transaction_path(cwd))}
    status = dict(payload)
    status["present"] = True
    status["path"] = str(_transaction_path(cwd))
    return status


def commit_state_transaction(
    cwd: str,
    updates: dict[str, Any],
    *,
    label: str = "",
    transaction_id: str | None = None,
) -> dict[str, Any]:
    payloads = {str(name): deepcopy(payload) for name, payload in dict(updates or {}).items()}
    if not payloads:
        return {
            "ok": True,
            "transaction_id": "",
            "label": str(label or ""),
            "store_count": 0,
            "written_names": [],
            "failure_count": 0,
            "failures": [],
            "conflict_count": 0,
            "conflicts": [],
        }

    tx_id = str(transaction_id or uuid4())
    journal_path = _transaction_path(cwd)
    conflicts: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    written_names: list[str] = []

    with _LOCK:
        prepared: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any], Any]] = {}
        payload_paths: dict[str, str] = {}
        registry = _registry_for_cwd(cwd)
        for name, payload in payloads.items():
            entry, spec = _ensure_entry_locked(cwd, name)
            if entry is None or spec is None:
                failures.append({"name": name, "path": "", "reason": "unknown state store"})
                continue
            current_revision = _revision_for_path(spec["path"])
            expected_revision = _clone_revision(entry.get("base_revision") if bool(entry.get("dirty", False)) else entry.get("disk_revision"))
            if not _revisions_equal(current_revision, expected_revision):
                entry = _apply_conflict_from_disk(entry, spec, "disk revision changed before transaction commit")
                registry[name] = entry
                conflicts.append(
                    {
                        "name": name,
                        "path": str(spec["path"]),
                        "reason": entry.get("conflict_reason", ""),
                        "expected_revision": expected_revision,
                        "current_revision": _clone_revision(entry.get("disk_revision")),
                    }
                )
                continue
            prepared[name] = (entry, spec, current_revision, payload)
            payload_path = _payload_path_for_store(cwd, tx_id, name)
            try:
                _write_json(payload_path, payload)
            except Exception as exc:
                failures.append({"name": name, "path": str(payload_path), "reason": f"staged payload write failed: {exc}"})
                continue
            payload_paths[name] = str(payload_path)

        journal_payload = {
            "transaction_id": tx_id,
            "label": str(label or ""),
            "time_utc": _utc_now(),
            "store_names": sorted(payloads),
            "payload_paths": dict(payload_paths),
            "status": "pending",
            "written_names": [],
            "failure_count": len(failures),
            "failures": list(failures),
            "conflict_count": len(conflicts),
            "conflicts": list(conflicts),
        }
        _write_json(journal_path, journal_payload)

        if conflicts or failures:
            journal_payload["status"] = "conflict" if conflicts else "failed"
            _write_json(journal_path, journal_payload)
            _cleanup_transaction_payloads(cwd, tx_id)
            return {
                "ok": False,
                "transaction_id": tx_id,
                "label": str(label or ""),
                "store_count": len(payloads),
                "written_names": [],
                "failure_count": len(failures),
                "failures": failures,
                "conflict_count": len(conflicts),
                "conflicts": conflicts,
            }

        for name, (entry, spec, _expected_revision, payload) in prepared.items():
            try:
                next_revision = _write_json(spec["path"], payload)
            except Exception as exc:
                entry["payload"] = deepcopy(payload)
                entry["dirty"] = False
                entry["conflict"] = True
                entry["conflict_reason"] = f"transaction write failed: {exc}"
                entry["last_updated_utc"] = _utc_now()
                registry[name] = entry
                failures.append({"name": name, "path": str(spec["path"]), "reason": str(exc)})
                continue
            now = _utc_now()
            entry["payload"] = deepcopy(payload)
            entry["dirty"] = False
            entry["conflict"] = False
            entry["conflict_reason"] = ""
            entry["base_revision"] = next_revision
            entry["disk_revision"] = next_revision
            entry["last_loaded_utc"] = now
            entry["last_updated_utc"] = now
            registry[name] = entry
            written_names.append(name)
            journal_payload["written_names"] = list(written_names)
            _write_json(journal_path, journal_payload)

        journal_payload["written_names"] = list(written_names)
        journal_payload["failure_count"] = len(failures)
        journal_payload["failures"] = list(failures)
        journal_payload["status"] = "committed" if not failures else ("partial_failure" if written_names else "failed")
        journal_payload["committed_utc"] = _utc_now()
        _write_json(journal_path, journal_payload)
        if not failures:
            _cleanup_transaction_payloads(cwd, tx_id)

        return {
            "ok": len(failures) == 0,
            "transaction_id": tx_id,
            "label": str(label or ""),
            "store_count": len(payloads),
            "written_names": written_names,
            "failure_count": len(failures),
            "failures": failures,
            "conflict_count": 0,
            "conflicts": [],
        }


def state_registry_status(cwd: str) -> dict[str, Any]:
    specs = _store_specs(cwd)
    with _LOCK:
        registry = _registry_for_cwd(cwd)
        stores: dict[str, Any] = {}
        for name, spec in specs.items():
            entry = dict(registry.get(name) or {})
            stores[name] = {
                "path": str(spec["path"]),
                "loaded": bool(entry),
                "hot": bool(spec.get("hot", False)),
                "dirty": bool(entry.get("dirty", False)),
                "conflict": bool(entry.get("conflict", False)),
                "conflict_reason": str(entry.get("conflict_reason", "")),
                "conflicted_local_payload_type": type(entry.get("conflicted_local_payload")).__name__ if "conflicted_local_payload" in entry else "",
                "payload_type": type(entry.get("payload")).__name__ if entry else "",
                "disk_revision": _clone_revision(entry.get("disk_revision")),
                "base_revision": _clone_revision(entry.get("base_revision")),
            }
        return {
            "ok": True,
            "cwd": _cwd_key(cwd),
            "loaded_store_count": sum(1 for entry in stores.values() if bool(entry.get("loaded", False))),
            "dirty_store_count": sum(1 for entry in stores.values() if bool(entry.get("dirty", False))),
            "conflict_store_count": sum(1 for entry in stores.values() if bool(entry.get("conflict", False))),
            "stores": stores,
            "transaction": transaction_status(cwd),
        }

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".md",
    ".mjs",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SKIP_PARTS = {".git", ".zero_os", "__pycache__", "node_modules", "bin", "obj", "dist"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_root(cwd: str) -> Path:
    root = Path(cwd).resolve() / ".zero_os" / "index"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _registry_path(cwd: str) -> Path:
    return _state_root(cwd) / "workspace_registry.json"


def _workspace_root(cwd: str, name: str) -> Path:
    path = _state_root(cwd) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _workspace_meta_path(cwd: str, name: str) -> Path:
    return _workspace_root(cwd, name) / "meta.json"


def _symbols_path(cwd: str, name: str) -> Path:
    return _workspace_root(cwd, name) / "symbols.json"


def _watcher_path(cwd: str, name: str) -> Path:
    return _workspace_root(cwd, name) / "watcher.json"


def _shards_root(cwd: str, name: str) -> Path:
    root = _workspace_root(cwd, name) / "shards"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _workspace_key(name: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "_", name.strip().lower()).strip("_") or "workspace"


def _tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9_./:-]+", text.lower()) if token]


def register_workspace(cwd: str, path: str, name: str = "main") -> dict:
    workspace_path = Path(path).resolve()
    key = _workspace_key(name)
    registry = _load_json(_registry_path(cwd), {"workspaces": {}})
    registry["workspaces"][key] = {
        "name": key,
        "path": str(workspace_path),
        "registered_utc": _utc_now(),
    }
    _save_json(_registry_path(cwd), registry)
    return {"ok": True, "workspace": registry["workspaces"][key]}


def list_workspaces(cwd: str) -> dict:
    registry = _load_json(_registry_path(cwd), {"workspaces": {}})
    return {
        "ok": True,
        "count": len(registry.get("workspaces", {})),
        "workspaces": registry.get("workspaces", {}),
    }


def index_workspace(cwd: str, name: str = "main", max_files: int = 50000, shard_size: int = 1000, incremental: bool = True) -> dict:
    registry = _load_json(_registry_path(cwd), {"workspaces": {}})
    key = _workspace_key(name)
    workspace = registry.get("workspaces", {}).get(key)
    if not workspace:
        workspace = register_workspace(cwd, cwd, key)["workspace"]
        registry = _load_json(_registry_path(cwd), {"workspaces": {}})

    base = Path(workspace["path"]).resolve()
    cap = max(1, min(1_000_000, int(max_files)))
    shard_cap = max(100, min(10_000, int(shard_size)))

    rows: list[dict] = []
    symbol_rows: list[dict] = []
    changed = 0
    unchanged = 0
    text_files = 0
    indexed = 0
    meta_before = _load_json(_workspace_meta_path(cwd, key), {"files": {}})
    previous_files = meta_before.get("files", {})
    previous_rows = {row.get("path", ""): row for row in meta_before.get("row_cache", [])}
    previous_symbols_payload = _load_json(_symbols_path(cwd, key), {"symbol_files": []})
    previous_symbol_rows = {row.get("path", ""): row for row in previous_symbols_payload.get("symbol_files", [])}
    current_files: dict[str, dict] = {}

    for path in base.rglob("*"):
        if indexed >= cap:
            break
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue

        rel = str(path.relative_to(base)).replace("\\", "/")
        stat = path.stat()
        file_sig = {
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
        current_files[rel] = file_sig

        if incremental and previous_files.get(rel) == file_sig and rel in previous_rows:
            rows.append(previous_rows[rel])
            if path.suffix.lower() in TEXT_SUFFIXES:
                text_files += 1
            if rel in previous_symbol_rows:
                symbol_rows.append(previous_symbol_rows[rel])
            unchanged += 1
            indexed += 1
            continue

        snippet = ""
        symbol_hits: list[str] = []
        if path.suffix.lower() in TEXT_SUFFIXES:
            text_files += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                snippet = text[:320].replace("\n", " ").strip()
                symbol_hits = re.findall(r"\b(class|def|function|interface|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)", text)[:12]
            except Exception:
                snippet = ""
                symbol_hits = []

        rows.append(
            {
                "path": rel,
                "suffix": path.suffix.lower(),
                "size": int(stat.st_size),
                "snippet": snippet,
                "symbols": [name for _, name in symbol_hits],
                "token_sample": _tokenize(f"{rel} {snippet}")[:40],
            }
        )
        if symbol_hits:
            symbol_rows.append(
                {
                    "path": rel,
                    "symbols": [name for _, name in symbol_hits],
                    "suffix": path.suffix.lower(),
                }
            )
        indexed += 1
        if previous_files.get(rel) != file_sig:
            changed += 1

    shards_root = _shards_root(cwd, key)
    for existing in shards_root.glob("*.json"):
        existing.unlink(missing_ok=True)

    shard_paths: list[str] = []
    for shard_index in range(0, len(rows), shard_cap):
        shard_rows = rows[shard_index:shard_index + shard_cap]
        shard_name = f"shard_{(shard_index // shard_cap) + 1:04d}.json"
        shard_path = shards_root / shard_name
        _save_json(shard_path, {"workspace": key, "shard": shard_name, "files": shard_rows})
        shard_paths.append(str(shard_path))

    meta = {
        "workspace": key,
        "workspace_path": str(base),
        "indexed_utc": _utc_now(),
        "file_count": len(rows),
        "text_file_count": text_files,
        "changed_files": changed,
        "unchanged_files": unchanged,
        "shard_count": len(shard_paths),
        "shard_size": shard_cap,
        "files": current_files,
        "row_cache": rows,
    }
    _save_json(_workspace_meta_path(cwd, key), meta)
    _save_json(_symbols_path(cwd, key), {"workspace": key, "indexed_utc": meta["indexed_utc"], "symbol_files": symbol_rows})

    return {
        "ok": True,
        "workspace": key,
        "workspace_path": str(base),
        "indexed_utc": meta["indexed_utc"],
        "file_count": len(rows),
        "text_file_count": text_files,
        "changed_files": changed,
        "unchanged_files": unchanged,
        "incremental": incremental,
        "shard_count": len(shard_paths),
        "shard_root": str(shards_root),
        "symbol_file_count": len(symbol_rows),
    }


def index_status(cwd: str, name: str = "main") -> dict:
    key = _workspace_key(name)
    meta = _load_json(_workspace_meta_path(cwd, key), {})
    if not meta:
        return {"ok": False, "missing": True, "hint": "run: zero ai index workspace"}
    return {
        "ok": True,
        "workspace": key,
        "workspace_path": meta.get("workspace_path", ""),
        "indexed_utc": meta.get("indexed_utc", ""),
        "file_count": int(meta.get("file_count", 0)),
        "text_file_count": int(meta.get("text_file_count", 0)),
        "changed_files": int(meta.get("changed_files", 0)),
        "unchanged_files": int(meta.get("unchanged_files", 0)),
        "shard_count": int(meta.get("shard_count", 0)),
        "shard_size": int(meta.get("shard_size", 0)),
        "shard_root": str(_shards_root(cwd, key)),
    }


def search_code(cwd: str, query: str, name: str = "main", limit: int = 20) -> dict:
    key = _workspace_key(name)
    tokens = _tokenize(query)
    if not tokens:
        return {"ok": False, "reason": "query required"}

    meta = _load_json(_workspace_meta_path(cwd, key), {})
    if not meta:
        return {"ok": False, "missing": True, "hint": "run: zero ai index workspace"}

    hits: list[dict] = []
    for shard_path in sorted(_shards_root(cwd, key).glob("*.json")):
        shard = _load_json(shard_path, {"files": []})
        for row in shard.get("files", []):
            hay = " ".join(
                [
                    str(row.get("path", "")).lower(),
                    str(row.get("snippet", "")).lower(),
                    " ".join(str(item).lower() for item in row.get("symbols", [])),
                    " ".join(str(item).lower() for item in row.get("token_sample", [])),
                ]
            )
            matched = [token for token in tokens if token in hay]
            if not matched:
                continue
            score = round((len(matched) / len(tokens)) * 100, 2)
            hits.append(
                {
                    "path": row.get("path", ""),
                    "score": score,
                    "matched_tokens": matched,
                    "suffix": row.get("suffix", ""),
                    "size": row.get("size", 0),
                    "symbols": row.get("symbols", []),
                    "snippet": row.get("snippet", ""),
                }
            )

    hits.sort(key=lambda item: (item["score"], len(item["matched_tokens"]), len(item.get("symbols", []))), reverse=True)
    cap = max(1, min(200, int(limit)))
    return {
        "ok": True,
        "workspace": key,
        "query": query,
        "result_count": min(cap, len(hits)),
        "results": hits[:cap],
    }


def symbol_status(cwd: str, name: str = "main") -> dict:
    key = _workspace_key(name)
    payload = _load_json(_symbols_path(cwd, key), {})
    if not payload:
        return {"ok": False, "missing": True, "hint": "run: zero ai index workspace"}
    files = payload.get("symbol_files", [])
    symbol_count = sum(len(item.get("symbols", [])) for item in files)
    return {
        "ok": True,
        "workspace": key,
        "indexed_utc": payload.get("indexed_utc", ""),
        "symbol_file_count": len(files),
        "symbol_count": symbol_count,
        "symbols_path": str(_symbols_path(cwd, key)),
    }


def search_symbols(cwd: str, query: str, name: str = "main", limit: int = 20) -> dict:
    key = _workspace_key(name)
    tokens = _tokenize(query)
    if not tokens:
        return {"ok": False, "reason": "query required"}

    payload = _load_json(_symbols_path(cwd, key), {})
    if not payload:
        return {"ok": False, "missing": True, "hint": "run: zero ai index workspace"}

    hits: list[dict] = []
    for row in payload.get("symbol_files", []):
        symbols = [str(item) for item in row.get("symbols", [])]
        hay = " ".join([str(row.get("path", "")).lower(), " ".join(symbol.lower() for symbol in symbols)])
        matched = [token for token in tokens if token in hay]
        if not matched:
            continue
        score = round((len(matched) / len(tokens)) * 100, 2)
        hits.append(
            {
                "path": row.get("path", ""),
                "score": score,
                "matched_tokens": matched,
                "symbols": symbols,
                "suffix": row.get("suffix", ""),
            }
        )

    hits.sort(key=lambda item: (item["score"], len(item.get("symbols", []))), reverse=True)
    cap = max(1, min(200, int(limit)))
    return {
        "ok": True,
        "workspace": key,
        "query": query,
        "result_count": min(cap, len(hits)),
        "results": hits[:cap],
    }


def watcher_set(cwd: str, name: str = "main", enabled: bool = True, interval_seconds: int = 60) -> dict:
    key = _workspace_key(name)
    status = {
        "workspace": key,
        "enabled": bool(enabled),
        "interval_seconds": max(5, min(86400, int(interval_seconds))),
        "updated_utc": _utc_now(),
        "last_tick_utc": "",
        "last_change_count": 0,
        "pending_changes": 0,
    }
    current = _load_json(_watcher_path(cwd, key), {})
    if current:
        status["last_tick_utc"] = current.get("last_tick_utc", "")
        status["last_change_count"] = int(current.get("last_change_count", 0))
        status["pending_changes"] = int(current.get("pending_changes", 0))
    _save_json(_watcher_path(cwd, key), status)
    return {"ok": True, **status}


def watcher_status(cwd: str, name: str = "main") -> dict:
    key = _workspace_key(name)
    data = _load_json(_watcher_path(cwd, key), {})
    if not data:
        return {"ok": False, "missing": True, "hint": "run: zero ai index watch on"}
    return {"ok": True, **data}


def watcher_tick(cwd: str, name: str = "main", max_files: int = 50000, shard_size: int = 1000) -> dict:
    key = _workspace_key(name)
    watch = _load_json(_watcher_path(cwd, key), {})
    if not watch:
        watch = watcher_set(cwd, key, enabled=True)
    if not bool(watch.get("enabled", False)):
        return {"ok": True, "workspace": key, "ran": False, "reason": "watcher_disabled"}

    before = index_status(cwd, key)
    result = index_workspace(cwd, name=key, max_files=max_files, shard_size=shard_size, incremental=True)
    pending = int(result.get("changed_files", 0))
    watch["last_tick_utc"] = _utc_now()
    watch["last_change_count"] = pending
    watch["pending_changes"] = pending
    watch["updated_utc"] = _utc_now()
    _save_json(_watcher_path(cwd, key), watch)
    return {
        "ok": True,
        "workspace": key,
        "ran": True,
        "before": before,
        "after": result,
        "watcher": watch,
    }

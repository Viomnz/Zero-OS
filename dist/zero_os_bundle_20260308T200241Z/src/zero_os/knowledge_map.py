from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".ps1", ".html", ".js", ".css"}
SKIP_PARTS = {".git", "__pycache__"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_knowledge_index.json"


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9_./-]+", text.lower()) if t]


def build_knowledge_index(cwd: str, max_files: int = 12000) -> dict:
    base = Path(cwd).resolve()
    rows: list[dict] = []
    cap = max(1, min(50000, int(max_files)))
    for p in base.rglob("*"):
        if len(rows) >= cap:
            break
        if not p.is_file():
            continue
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        rel = str(p.relative_to(base)).replace("\\", "/")
        size = int(p.stat().st_size)
        snippet = ""
        if p.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                snippet = text[:280].replace("\n", " ").strip()
            except Exception:
                snippet = ""
        rows.append(
            {
                "path": rel,
                "suffix": p.suffix.lower(),
                "size": size,
                "snippet": snippet,
            }
        )
    payload = {
        "time_utc": _utc_now(),
        "file_count": len(rows),
        "files": rows,
    }
    _index_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "time_utc": payload["time_utc"], "file_count": len(rows), "index_path": str(_index_path(cwd))}


def knowledge_status(cwd: str) -> dict:
    p = _index_path(cwd)
    if not p.exists():
        return {"ok": False, "missing": True, "hint": "run: zero ai knowledge build"}
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "missing": True, "hint": "run: zero ai knowledge build"}
    return {
        "ok": True,
        "time_utc": data.get("time_utc", ""),
        "file_count": int(data.get("file_count", 0)),
        "index_path": str(p),
    }


def knowledge_find(cwd: str, query: str, limit: int = 20) -> dict:
    p = _index_path(cwd)
    if not p.exists():
        return {"ok": False, "missing": True, "hint": "run: zero ai knowledge build"}
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "missing": True, "hint": "run: zero ai knowledge build"}
    tokens = _tokenize(query)
    if not tokens:
        return {"ok": False, "reason": "query required"}
    hits = []
    cap = max(1, min(200, int(limit)))
    for row in data.get("files", []):
        hay = f"{row.get('path', '').lower()} {row.get('snippet', '').lower()}"
        matched = [t for t in tokens if t in hay]
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
                "snippet": row.get("snippet", ""),
            }
        )
    hits.sort(key=lambda x: (x["score"], len(x["matched_tokens"])), reverse=True)
    return {"ok": True, "query": query, "result_count": min(cap, len(hits)), "results": hits[:cap]}


from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_POLICY = {
    "max_pending_tasks": 200,
    "max_output_kb": 2048,
    "blocked_process_names": ["mimikatz.exe", "nc.exe", "ncat.exe", "netcat.exe"],
    "max_security_events_per_hour": 2000,
    "min_reputation_score": 60,
    "strict_reputation_mode": 0,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def policy_path(base: Path) -> Path:
    return _runtime(base) / "security_policy.json"


def events_path(base: Path) -> Path:
    return _runtime(base) / "security_events.jsonl"


def report_path(base: Path) -> Path:
    return _runtime(base) / "security_report.json"


def reputation_db_path(base: Path) -> Path:
    return _runtime(base) / "reputation_db.json"


def load_policy(base: Path) -> dict:
    p = policy_path(base)
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_POLICY, indent=2) + "\n", encoding="utf-8")
        return dict(DEFAULT_POLICY)
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        out = dict(DEFAULT_POLICY)
        out.update({k: v for k, v in data.items() if k in DEFAULT_POLICY})
        return out
    except Exception:
        return dict(DEFAULT_POLICY)


def save_policy(base: Path, updates: dict) -> dict:
    current = load_policy(base)
    current.update({k: v for k, v in updates.items() if k in DEFAULT_POLICY})
    policy_path(base).write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return current


def _reputation_key(base: Path) -> bytes:
    key_path = base / ".zero_os" / "keys" / "reputation.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        key_path.write_text(secrets.token_hex(32), encoding="utf-8")
    return key_path.read_text(encoding="utf-8").strip().encode("utf-8")


def _sign_dict(base: Path, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_reputation_key(base), canonical, hashlib.sha256).hexdigest()


def _verify_dict(base: Path, payload: dict, sig: str) -> bool:
    expected = _sign_dict(base, payload)
    return hmac.compare_digest(expected, sig)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _candidate_extensions() -> set[str]:
    return {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".ps1",
        ".py",
        ".js",
        ".ts",
        ".sh",
        ".vbs",
    }


def _load_reputation_db(base: Path) -> dict:
    p = reputation_db_path(base)
    if not p.exists():
        data = {"version": 1, "entries": []}
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except Exception:
        pass
    return {"version": 1, "entries": []}


def _save_reputation_db(base: Path, db: dict) -> None:
    reputation_db_path(base).write_text(json.dumps(db, indent=2) + "\n", encoding="utf-8")


def trust_file(base: Path, file_rel: str, score: int, level: str = "trusted", note: str = "") -> dict:
    score = max(0, min(100, int(score)))
    target = (base / file_rel).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        raise ValueError("path escapes workspace")
    if not target.exists() or not target.is_file():
        raise ValueError("file not found")

    entry_core = {
        "path": str(target.relative_to(base.resolve())).replace("\\", "/"),
        "sha256": _sha256_file(target),
        "score": score,
        "level": level,
        "note": note,
        "updated_utc": _utc_now(),
    }
    sig = _sign_dict(base, entry_core)
    entry = dict(entry_core)
    entry["signature"] = sig

    db = _load_reputation_db(base)
    entries = [e for e in db["entries"] if not (e.get("path") == entry["path"] and e.get("sha256") == entry["sha256"])]
    entries.append(entry)
    db["entries"] = entries
    _save_reputation_db(base, db)
    return entry


def scan_reputation(base: Path) -> dict:
    db = _load_reputation_db(base)
    policy = load_policy(base)
    min_score = int(policy.get("min_reputation_score", 60))
    indexed = {}
    tampered = []
    for e in db.get("entries", []):
        sig = str(e.get("signature", ""))
        core = dict(e)
        core.pop("signature", None)
        if not sig or not _verify_dict(base, core, sig):
            tampered.append({"path": e.get("path", ""), "sha256": e.get("sha256", ""), "reason": "invalid_signature"})
            continue
        indexed[(str(e.get("path", "")), str(e.get("sha256", "")))] = e

    unknown = []
    low_score = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _candidate_extensions():
            continue
        try:
            rel = str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
        except ValueError:
            continue
        sha = _sha256_file(path)
        key = (rel, sha)
        if key not in indexed:
            unknown.append({"path": rel, "sha256": sha})
            continue
        score = int(indexed[key].get("score", 0))
        if score < min_score:
            low_score.append({"path": rel, "sha256": sha, "score": score, "min_required": min_score})

    report = {
        "time_utc": _utc_now(),
        "unknown": unknown,
        "low_score": low_score,
        "tampered_entries": tampered,
        "min_reputation_score": min_score,
        "healthy": not unknown and not low_score and not tampered,
    }
    p = _runtime(base) / "reputation_report.json"
    p.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _last_hash(base: Path) -> str:
    p = events_path(base)
    if not p.exists():
        return "0" * 64
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return "0" * 64
    try:
        last = json.loads(lines[-1])
        return str(last.get("hash", "0" * 64))
    except Exception:
        return "0" * 64


def record_event(base: Path, level: str, event: str, details: dict) -> dict:
    prev = _last_hash(base)
    payload = {
        "time_utc": _utc_now(),
        "level": level,
        "event": event,
        "details": details,
        "prev_hash": prev,
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["hash"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    p = events_path(base)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")
    return payload


def _pending_tasks_count(base: Path, processed_lines: int) -> int:
    inbox = _runtime(base) / "zero_ai_tasks.txt"
    if not inbox.exists():
        return 0
    total = len(inbox.read_text(encoding="utf-8", errors="replace").splitlines())
    return max(0, total - processed_lines)


def _output_size_kb(base: Path) -> int:
    outbox = _runtime(base) / "zero_ai_output.txt"
    if not outbox.exists():
        return 0
    return int(outbox.stat().st_size / 1024)


def _running_process_names() -> set[str]:
    try:
        proc = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=False,
        )
        names = set()
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('"'):
                name = line.split('","', 1)[0].strip('"').lower()
                if name:
                    names.add(name)
        return names
    except Exception:
        return set()


def _recent_events_count(base: Path) -> int:
    p = events_path(base)
    if not p.exists():
        return 0
    return len(p.read_text(encoding="utf-8", errors="replace").splitlines())


def assess_security(base: Path, processed_lines: int) -> dict:
    policy = load_policy(base)
    alerts = []
    pending = _pending_tasks_count(base, processed_lines)
    if pending > int(policy["max_pending_tasks"]):
        alerts.append(
            {
                "type": "task_flood",
                "pending": pending,
                "limit": int(policy["max_pending_tasks"]),
                "severity": "high",
            }
        )

    out_kb = _output_size_kb(base)
    if out_kb > int(policy["max_output_kb"]):
        alerts.append(
            {
                "type": "output_growth",
                "output_kb": out_kb,
                "limit": int(policy["max_output_kb"]),
                "severity": "medium",
            }
        )

    running = _running_process_names()
    blocked = [p for p in policy["blocked_process_names"] if p.lower() in running]
    if blocked:
        alerts.append({"type": "blocked_process", "names": blocked, "severity": "critical"})

    events_count = _recent_events_count(base)
    if events_count > int(policy["max_security_events_per_hour"]):
        alerts.append(
            {
                "type": "event_storm",
                "events": events_count,
                "limit": int(policy["max_security_events_per_hour"]),
                "severity": "medium",
            }
        )

    rep = scan_reputation(base)
    if rep["unknown"]:
        alerts.append(
            {
                "type": "unknown_executables",
                "count": len(rep["unknown"]),
                "severity": "high" if int(policy.get("strict_reputation_mode", 0)) == 1 else "medium",
            }
        )
    if rep["low_score"]:
        alerts.append(
            {
                "type": "low_reputation",
                "count": len(rep["low_score"]),
                "severity": "high" if int(policy.get("strict_reputation_mode", 0)) == 1 else "medium",
            }
        )
    if rep["tampered_entries"]:
        alerts.append({"type": "reputation_db_tamper", "count": len(rep["tampered_entries"]), "severity": "critical"})

    healthy = not any(a["severity"] in ("high", "critical") for a in alerts)
    report = {
        "time_utc": _utc_now(),
        "healthy": healthy,
        "policy": policy,
        "alerts": alerts,
        "pending_tasks": pending,
        "output_kb": out_kb,
        "reputation_report": str(_runtime(base) / "reputation_report.json"),
    }
    report_path(base).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

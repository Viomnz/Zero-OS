from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha256_payload(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _dedupe_by_key(items: list[dict], key_fn) -> list[dict]:
    seen = set()
    out: list[dict] = []
    for item in reversed(items):
        key = key_fn(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.reverse()
    return out


def _critical_learning(entry: dict) -> bool:
    signal = str(entry.get("signal_type", "")).lower()
    score = float(entry.get("learning_score", 0.0))
    actions = entry.get("actions", {}) if isinstance(entry.get("actions"), dict) else {}
    return signal == "negative" or score >= 0.9 or bool(actions.get("refine_survival_evaluator"))


def _critical_trace(entry: dict) -> bool:
    safe = entry.get("safe_state", {}) if isinstance(entry.get("safe_state"), dict) else {}
    consensus = entry.get("consensus", {}) if isinstance(entry.get("consensus"), dict) else {}
    return bool(safe.get("enter_safe_state", False)) or not bool(consensus.get("accepted", True))


def run_compression(cwd: str, threshold_entries: int = 300) -> dict:
    rt = _runtime(cwd)
    lf_path = rt / "learning_feedback.json"
    dt_path = rt / "decision_trace.json"

    learning = _load_json(lf_path, {"history": [], "stats": {}})
    trace = _load_json(dt_path, {"history": []})

    lf_history = list(learning.get("history", []))
    dt_history = list(trace.get("history", []))

    before = {"learning_feedback": len(lf_history), "decision_trace": len(dt_history)}

    # Snapshot before compression for rollback.
    snapshot = {
        "learning_feedback": learning,
        "decision_trace": trace,
        "before_hash": {
            "learning_feedback": _sha256_payload(learning),
            "decision_trace": _sha256_payload(trace),
        },
    }
    _save_json(rt / "compression_snapshot_last.json", snapshot)

    compressed_lf = _dedupe_by_key(
        lf_history,
        lambda x: (
            str(x.get("prompt", "")).strip().lower(),
            bool(x.get("outcome_match", False)),
            round(float(x.get("learning_score", 0.0)), 2),
        ),
    )
    compressed_dt = _dedupe_by_key(
        dt_history,
        lambda x: (
            str(x.get("input", {}).get("prompt", "")).strip().lower(),
            bool(x.get("consensus", {}).get("accepted", False)),
            bool(x.get("final_action", {}).get("execute", False)),
        ),
    )

    if len(compressed_lf) > threshold_entries:
        critical = [x for x in compressed_lf if _critical_learning(x)]
        tail = compressed_lf[-threshold_entries:]
        merged = _dedupe_by_key(critical + tail, lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        compressed_lf = merged[-max(threshold_entries, min(len(merged), threshold_entries + 25)) :]
    if len(compressed_dt) > threshold_entries:
        critical = [x for x in compressed_dt if _critical_trace(x)]
        tail = compressed_dt[-threshold_entries:]
        merged = _dedupe_by_key(critical + tail, lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        compressed_dt = merged[-max(threshold_entries, min(len(merged), threshold_entries + 25)) :]

    learning["history"] = compressed_lf
    if compressed_lf:
        learning["last"] = compressed_lf[-1]
    trace["history"] = compressed_dt
    if compressed_dt:
        trace["last"] = compressed_dt[-1]

    # Integrity validation and guarded write.
    try:
        _save_json(lf_path, learning)
        _save_json(dt_path, trace)
        lf_check = _load_json(lf_path, {})
        dt_check = _load_json(dt_path, {})
        valid = isinstance(lf_check.get("history", []), list) and isinstance(dt_check.get("history", []), list)
    except Exception:
        valid = False
    if not valid:
        # Roll back to last snapshot.
        _save_json(lf_path, snapshot["learning_feedback"])
        _save_json(dt_path, snapshot["decision_trace"])
        report = {
            "ok": False,
            "rolled_back": True,
            "reason": "integrity validation failed",
            "threshold_entries": int(threshold_entries),
            "before": before,
            "after": before,
            "removed": {"learning_feedback": 0, "decision_trace": 0},
            "summary": {"top_learning_patterns": [], "top_decision_patterns": [], "essential_conclusions": {"dedupe_active": False}},
        }
        _save_json(rt / "compression_simplification.json", report)
        return report

    prompt_counter = Counter(str(x.get("prompt", "")).strip().lower() for x in compressed_lf if x.get("prompt"))
    decision_counter = Counter(str(x.get("input", {}).get("prompt", "")).strip().lower() for x in compressed_dt)
    summary = {
        "top_learning_patterns": [{"prompt": p, "count": c} for p, c in prompt_counter.most_common(5)],
        "top_decision_patterns": [{"prompt": p, "count": c} for p, c in decision_counter.most_common(5)],
        "essential_conclusions": {
            "learning_entries": len(compressed_lf),
            "decision_entries": len(compressed_dt),
            "dedupe_active": True,
        },
    }

    report = {
        "ok": True,
        "rolled_back": False,
        "threshold_entries": int(threshold_entries),
        "before": before,
        "after": {"learning_feedback": len(compressed_lf), "decision_trace": len(compressed_dt)},
        "removed": {
            "learning_feedback": before["learning_feedback"] - len(compressed_lf),
            "decision_trace": before["decision_trace"] - len(compressed_dt),
        },
        "integrity": {
            "before_hash": snapshot["before_hash"],
            "after_hash": {
                "learning_feedback": _sha256_payload(learning),
                "decision_trace": _sha256_payload(trace),
            },
            "snapshot_path": str(rt / "compression_snapshot_last.json"),
        },
        "summary": summary,
    }
    _save_json(rt / "compression_simplification.json", report)
    return report

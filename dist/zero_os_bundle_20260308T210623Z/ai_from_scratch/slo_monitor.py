from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SLO = {
    "max_pending_tasks": 150,
    "max_output_kb": 3072,
    "min_uptime_mode": "running",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _policy_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / "zero_os_config" / "slo_policy.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_policy(cwd: str) -> dict:
    p = _policy_path(cwd)
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_SLO, indent=2) + "\n", encoding="utf-8")
        return dict(DEFAULT_SLO)
    try:
        d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        out = dict(DEFAULT_SLO)
        if isinstance(d, dict):
            out.update(d)
        return out
    except Exception:
        return dict(DEFAULT_SLO)


def evaluate_slo(cwd: str) -> dict:
    rt = _runtime(cwd)
    policy = _load_policy(cwd)
    hb_path = rt / "zero_ai_heartbeat.json"
    inbox = rt / "zero_ai_tasks.txt"
    outbox = rt / "zero_ai_output.txt"

    hb = {}
    if hb_path.exists():
        try:
            hb = json.loads(hb_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            hb = {}

    pending = len(inbox.read_text(encoding="utf-8", errors="replace").splitlines()) if inbox.exists() else 0
    output_kb = int(outbox.stat().st_size / 1024) if outbox.exists() else 0
    running = str(hb.get("status", "")) == str(policy.get("min_uptime_mode", "running"))

    checks = {
        "uptime_mode_ok": running,
        "pending_tasks_ok": pending <= int(policy["max_pending_tasks"]),
        "output_size_ok": output_kb <= int(policy["max_output_kb"]),
    }
    violations = [k for k, v in checks.items() if not v]
    score = round((sum(1 for v in checks.values() if v) / len(checks)) * 100, 2)
    out = {
        "schema_version": 1,
        "time_utc": _utc_now(),
        "ok": len(violations) == 0,
        "score": score,
        "checks": checks,
        "violations": violations,
        "metrics": {"pending_tasks": pending, "output_kb": output_kb},
        "policy": policy,
    }
    (rt / "slo_report.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


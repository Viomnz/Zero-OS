from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def run_agents_monitor(cwd: str) -> dict:
    runtime = _runtime(cwd)
    heartbeat = _read_json(runtime / "zero_ai_heartbeat.json")
    health = _read_json(runtime / "agent_health.json")
    boot = _read_json(runtime / "boot_initialization.json")
    safe_state = _read_json(runtime / "safe_state_report.json")
    registry = _read_json(runtime / "agi_module_registry_status.json")
    advanced = _read_json(runtime / "agi_advanced_layers_status.json")

    checks = {
        "heartbeat_running": heartbeat.get("status") == "running",
        "boot_ok": bool(boot.get("ok", False)),
        "integrity_healthy": bool(health.get("healthy", False)),
        "safe_state_clear": not bool(safe_state.get("enter_safe_state", False)),
        "registry_ok": bool(registry.get("ok", False)) if registry else False,
        "advanced_layers_ok": bool(advanced.get("ok", False)) if advanced else False,
    }

    issues: list[str] = []
    if not checks["heartbeat_running"]:
        issues.append("daemon_not_running")
    if not checks["boot_ok"]:
        issues.append("boot_not_ok")
    if not checks["integrity_healthy"]:
        issues.append("integrity_not_healthy")
    if not checks["safe_state_clear"]:
        issues.append("safe_state_active")
    if not checks["registry_ok"]:
        issues.append("module_registry_invalid")
    if not checks["advanced_layers_ok"]:
        issues.append("advanced_layers_invalid")

    passed = sum(1 for v in checks.values() if v)
    score = round((passed / len(checks)) * 100, 2)
    smooth = score >= 85 and not issues

    payload = {
        "time_utc": _utc_now(),
        "smooth": smooth,
        "score": score,
        "checks": checks,
        "issues": issues,
        "auto_mode": True,
    }
    (runtime / "agents_monitor.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


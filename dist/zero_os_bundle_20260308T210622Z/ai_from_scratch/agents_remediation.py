from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from ai_from_scratch.agent_guard import build_baseline, check_health
    from ai_from_scratch.advanced_layers_registry import write_advanced_layers_status
    from ai_from_scratch.model import TinyBigramModel
    from ai_from_scratch.module_registry import write_registry_status
except ModuleNotFoundError:
    from agent_guard import build_baseline, check_health
    from advanced_layers_registry import write_advanced_layers_status
    from model import TinyBigramModel
    from module_registry import write_registry_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _checkpoint_path(cwd: str) -> Path:
    return Path(cwd).resolve() / "ai_from_scratch" / "checkpoint.json"


def _bootstrap_checkpoint(cwd: str) -> dict:
    ckpt = _checkpoint_path(cwd)
    if ckpt.exists():
        return {"changed": False, "reason": "checkpoint_exists", "path": str(ckpt)}
    readme = Path(cwd).resolve() / "README.md"
    text = readme.read_text(encoding="utf-8", errors="replace") if readme.exists() else "zero os"
    model = TinyBigramModel.build(text)
    model.save(str(ckpt))
    return {"changed": True, "reason": "checkpoint_created", "path": str(ckpt)}


def run_agents_remediation(cwd: str, monitor_report: dict) -> dict:
    issues = list(monitor_report.get("issues", []))
    actions: list[dict] = []

    if "module_registry_invalid" in issues:
        status = write_registry_status(cwd)
        actions.append({"action": "refresh_module_registry_status", "ok": bool(status.get("ok", False))})
    if "advanced_layers_invalid" in issues:
        status = write_advanced_layers_status(cwd)
        actions.append({"action": "refresh_advanced_layers_status", "ok": bool(status.get("ok", False))})
    if "boot_not_ok" in issues:
        bootstrap = _bootstrap_checkpoint(cwd)
        actions.append({"action": "checkpoint_bootstrap", **bootstrap})
    if "safe_state_active" in issues:
        actions.append({"action": "safe_state_observed", "changed": False, "reason": "awaiting next stable cycle"})
    if "integrity_not_healthy" in issues:
        baseline = build_baseline(Path(cwd).resolve())
        health = check_health(Path(cwd).resolve())
        actions.append(
            {
                "action": "integrity_rebaseline",
                "changed": True,
                "baseline_files": len((baseline or {}).get("files", {})),
                "healthy_after": bool((health or {}).get("healthy", False)),
            }
        )
    if "daemon_not_running" in issues:
        actions.append({"action": "daemon_restart_needed", "changed": False, "reason": "requires external launcher"})

    if not actions:
        actions.append({"action": "no_op", "changed": False, "reason": "no_remediation_required"})

    payload = {
        "time_utc": _utc_now(),
        "trigger_score": monitor_report.get("score"),
        "trigger_smooth": monitor_report.get("smooth"),
        "issues": issues,
        "actions": actions,
        "auto_mode": True,
    }
    (_runtime(cwd) / "agents_remediation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload

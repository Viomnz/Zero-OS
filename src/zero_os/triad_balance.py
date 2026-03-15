from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.antivirus import monitor_set, monitor_status, monitor_tick
from zero_os.cure_firewall_agent import run_cure_firewall_agent
from zero_os.readiness import os_readiness
from zero_os.score_system import score_from_checks


def _report_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "triad_balance.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _ops_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "triad_ops.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _alert_log_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "triad_alerts.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _alert_inbox_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "triad_inbox.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def triad_ops_status(cwd: str) -> dict:
    default = {
        "enabled": False,
        "interval_seconds": 60,
        "alert_sink": "log+inbox",
        "last_tick_utc": "",
        "last_balanced": None,
    }
    path = _ops_path(cwd)
    if not path.exists():
        path.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        data = dict(default)
    for k, v in default.items():
        data.setdefault(k, v)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def triad_ops_set(cwd: str, enabled: bool, interval_seconds: int | None = None, alert_sink: str | None = None) -> dict:
    ops = triad_ops_status(cwd)
    ops["enabled"] = bool(enabled)
    if interval_seconds is not None:
        ops["interval_seconds"] = max(30, min(3600, int(interval_seconds)))
    if alert_sink is not None:
        sink = alert_sink.strip().lower()
        if sink in {"log", "inbox", "log+inbox"}:
            ops["alert_sink"] = sink
    _ops_path(cwd).write_text(json.dumps(ops, indent=2) + "\n", encoding="utf-8")
    return ops


def _emit_alert(cwd: str, report: dict, message: str) -> None:
    ops = triad_ops_status(cwd)
    payload = {
        "time_utc": _utc_now(),
        "message": message,
        "triad_score": report.get("triad_score", 0),
        "balanced": report.get("balanced", False),
    }
    sink = str(ops.get("alert_sink", "log+inbox"))
    if sink in {"log", "log+inbox"}:
        with _alert_log_path(cwd).open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")
    if sink in {"inbox", "log+inbox"}:
        with _alert_inbox_path(cwd).open("a", encoding="utf-8") as f:
            f.write(f"[{payload['time_utc']}] {message}\n")


def _run_playbook(cwd: str, report: dict) -> dict:
    actions = []
    if report.get("zero_os", {}).get("readiness_score", 0) < 60:
        actions.append("run os missing fix")
    if report.get("cure_firewall_agent", {}).get("file_verified", 0) < max(1, report.get("cure_firewall_agent", {}).get("file_targets", 0)):
        actions.append("raise cure firewall pressure to 90 next cycle")
    if report.get("antivirus_monitor", {}).get("finding_count", 0) > 0:
        actions.append("run antivirus agent with auto quarantine")
    report["playbook_actions"] = actions
    return report


def run_triad_balance(cwd: str) -> dict:
    readiness = os_readiness(cwd)
    cure = run_cure_firewall_agent(cwd, pressure=80, verify=True)

    av_status = monitor_status(cwd)
    if not av_status.get("enabled", False):
        av_status = monitor_set(cwd, True, 120)
    av_tick = monitor_tick(cwd, ".")

    score = 0
    if readiness.get("score", 0) >= 60:
        score += 1
    if cure.get("file_survived", 0) >= 1 or cure.get("file_targets", 0) == 0:
        score += 1
    if bool(av_tick.get("ok")) and bool(av_tick.get("ran")):
        score += 1
    issues: list[str] = []
    if readiness.get("score", 0) < 100:
        issues.append("zero_os_not_perfect")
    if cure.get("issues"):
        issues.append("cure_firewall_issues")
    if int(av_tick.get("report", {}).get("finding_count", 0)) > 0:
        issues.append("antivirus_findings")
    triad_scoring = score_from_checks(
        {
            "readiness_perfect": readiness.get("score", 0) == 100,
            "cure_firewall_perfect": bool(cure.get("perfect", False)),
            "antivirus_clean": int(av_tick.get("report", {}).get("finding_count", 0)) == 0,
        },
        issues=issues,
    )

    report = {
        "ok": True,
        "triad_score": score,
        "triad_total": 3,
        "balanced": score == 3,
        "system_score": triad_scoring["score"],
        "perfect": triad_scoring["perfect"],
        "issues": triad_scoring["issues"],
        "root_issues": triad_scoring["root_issues"],
        "zero_os": {
            "readiness_score": readiness.get("score", 0),
            "missing": readiness.get("missing", []),
            "perfect": readiness.get("perfect", False),
        },
        "cure_firewall_agent": {
            "file_targets": cure.get("file_targets", 0),
            "file_survived": cure.get("file_survived", 0),
            "file_verified": cure.get("file_verified", 0),
            "system_score": cure.get("system_score", 0),
            "perfect": cure.get("perfect", False),
        },
        "antivirus_monitor": {
            "enabled": av_status.get("enabled", False),
            "last_change_count": av_tick.get("monitor", {}).get("last_change_count", 0),
            "finding_count": av_tick.get("report", {}).get("finding_count", 0),
        },
    }
    report = _run_playbook(cwd, report)
    if not report["balanced"]:
        _emit_alert(cwd, report, "TRIAD DEGRADED: one or more lanes are below target")
    _report_path(cwd).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def triad_balance_status(cwd: str) -> dict:
    p = _report_path(cwd)
    if not p.exists():
        return {"ok": False, "missing": True, "hint": "run: triad balance run"}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "missing": True, "hint": "run: triad balance run"}


def triad_ops_tick(cwd: str) -> dict:
    ops = triad_ops_status(cwd)
    if not ops.get("enabled", False):
        return {"ok": False, "ran": False, "reason": "triad ops disabled"}
    report = run_triad_balance(cwd)
    ops["last_tick_utc"] = _utc_now()
    ops["last_balanced"] = bool(report.get("balanced", False))
    _ops_path(cwd).write_text(json.dumps(ops, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "ran": True, "ops": ops, "report": report}

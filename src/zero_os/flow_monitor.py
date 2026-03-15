from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.antivirus import monitor_status as antivirus_monitor_status, quarantine_list as antivirus_quarantine_list, scan_target_readonly
from zero_os.antivirus_agent import antivirus_agent_status
from zero_os.autonomous_fix_gate import capture_health_snapshot
from zero_os.contradiction_engine import contradiction_engine_status
from zero_os.score_system import score_from_checks
from zero_os.task_memory import load_memory


_SIMULATED_SIGNATURE_IDS = {"EICAR-SIM", "QVIR-SIM", "PS-ENC", "CMD-DROP", "WGET-EXE"}
_SECURITY_FIXTURE_KEYWORDS = ("antivirus", "virus", "malware", "adversarial", "benchmark", "highway")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "flow_monitor.json"


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "last_scan_utc": "",
        "last_target": ".",
        "last_score": 0.0,
        "last_issue_count": 0,
        "last_highest_severity": "unknown",
        "last_report": {},
        "history": [],
    }


def _last_antivirus_scan(cwd: str) -> dict[str, Any]:
    path = Path(cwd).resolve() / ".zero_os" / "antivirus" / "last_scan.json"
    if not path.exists():
        return {"ok": False, "missing": True}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "missing": True}
    if not isinstance(raw, dict):
        return {"ok": False, "missing": True}
    return raw


def _resolve_target(cwd: str, target: str) -> Path:
    base = Path(cwd).resolve()
    requested = (base / target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
    try:
        requested.relative_to(base)
    except ValueError:
        return base
    return requested


def _iter_python_files(cwd: str, target: str, max_files: int = 1500) -> list[Path]:
    base = Path(cwd).resolve()
    target_path = _resolve_target(cwd, target)
    exclude_parts = {".git", ".zero_os", "__pycache__", ".venv", "venv", "node_modules", "build", "dist"}
    files: list[Path] = []
    candidates: list[Path]
    if target_path.is_file():
        candidates = [target_path] if target_path.suffix.lower() == ".py" else []
    elif target_path.is_dir():
        candidates = list(target_path.rglob("*.py"))
    else:
        candidates = []
    for path in candidates:
        try:
            rel_parts = set(path.resolve().relative_to(base).parts)
        except ValueError:
            continue
        if rel_parts & exclude_parts:
            continue
        files.append(path)
        if len(files) >= max_files:
            break
    return files


def _source_integrity_scan(cwd: str, target: str) -> dict[str, Any]:
    files = _iter_python_files(cwd, target)
    syntax_errors: list[dict[str, Any]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            syntax_errors.append(
                {
                    "path": str(path),
                    "line": int(exc.lineno or 0),
                    "column": int(exc.offset or 0),
                    "message": str(exc.msg or "syntax error"),
                }
            )
        except Exception as exc:
            syntax_errors.append(
                {
                    "path": str(path),
                    "line": 0,
                    "column": 0,
                    "message": f"parse_error: {exc}",
                }
            )
    highest_severity = "high" if syntax_errors else "low"
    return {
        "ok": True,
        "target": target,
        "scanned_files": len(files),
        "syntax_error_count": len(syntax_errors),
        "syntax_errors": syntax_errors[:100],
        "highest_severity": highest_severity,
    }


def _recent_execution_signals(cwd: str) -> dict[str, Any]:
    tasks = list(load_memory(cwd).get("tasks", []))[-12:]
    unguarded_failures: list[dict[str, Any]] = []
    guarded_stops: list[dict[str, Any]] = []
    for task in tasks:
        if bool(task.get("ok", False)):
            continue
        failed_results = [item for item in task.get("results", []) if not bool(item.get("ok", False))]
        reasons = {str(item.get("reason", "")).strip() for item in failed_results if str(item.get("reason", "")).strip()}
        record = {
            "time_utc": str(task.get("time_utc", "")),
            "request": str(task.get("request", "")),
            "reasons": sorted(reasons),
        }
        if reasons and reasons.issubset({"approval_required", "autonomy_gate"}):
            guarded_stops.append(record)
        else:
            unguarded_failures.append(record)
    return {
        "ok": True,
        "recent_task_count": len(tasks),
        "unguarded_failure_count": len(unguarded_failures),
        "guarded_stop_count": len(guarded_stops),
        "unguarded_failures": unguarded_failures[:5],
        "guarded_stops": guarded_stops[:5],
    }


def _severity_rank(value: str) -> int:
    return {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(str(value).lower(), 0)


def _highest_severity(*values: str) -> str:
    return max(values, key=_severity_rank, default="unknown")


def _normalize_rel(path: str) -> str:
    return str(path or "").replace("\\", "/").strip().lower()


def _finding_signature_ids(item: dict[str, Any]) -> set[str]:
    ids = {str(hit.get("id", "")).strip() for hit in item.get("signature_hits", []) if str(hit.get("id", "")).strip()}
    ids.update(str(hit.get("signature", "")).strip() for hit in item.get("archive_hits", []) if str(hit.get("signature", "")).strip())
    return ids


def _expected_file_noise_reason(item: dict[str, Any]) -> str:
    rel = _normalize_rel(str(item.get("path", "")))
    name = Path(rel).name
    signature_ids = _finding_signature_ids(item)

    if "/__pycache__/" in f"/{rel}/" or rel.endswith(".pyc"):
        return "generated_cache_artifact"
    if rel.startswith("dist/") and "zero_os_bundle_" in rel:
        return "bundle_artifact_copy"
    if rel == "src/zero_os/antivirus.py":
        return "self_referential_security_engine"
    if rel.startswith("tools/") and "benchmark_security_stack.py" in rel:
        return "security_benchmark_fixture"
    if rel.startswith("tests/"):
        if any(keyword in name for keyword in _SECURITY_FIXTURE_KEYWORDS):
            return "security_test_fixture"
        if signature_ids and signature_ids.issubset(_SIMULATED_SIGNATURE_IDS):
            return "simulated_test_fixture"
    return ""


def _expected_process_noise_reason(item: dict[str, Any]) -> str:
    process = _normalize_rel(str(item.get("process", "")))
    reason = str(item.get("reason", "")).strip().lower()
    if reason == "suspicious_process_name" and process in {"powershell.exe", "rundll32.exe"}:
        return "ambient_shell_process"
    return ""


def _filter_antivirus_noise(scan: dict[str, Any]) -> dict[str, Any]:
    findings = list(scan.get("findings", []))
    process_findings = list(scan.get("process_findings", []))
    active_findings: list[dict[str, Any]] = []
    active_process_findings: list[dict[str, Any]] = []
    suppressed_findings: list[dict[str, Any]] = []
    suppressed_process_findings: list[dict[str, Any]] = []
    suppressed_reason_counts: dict[str, int] = {}

    for item in findings:
        reason = _expected_file_noise_reason(item)
        if reason:
            tagged = dict(item)
            tagged["suppression_reason"] = reason
            suppressed_findings.append(tagged)
            suppressed_reason_counts[reason] = suppressed_reason_counts.get(reason, 0) + 1
            continue
        active_findings.append(item)

    for item in process_findings:
        reason = _expected_process_noise_reason(item)
        if reason:
            tagged = dict(item)
            tagged["suppression_reason"] = reason
            suppressed_process_findings.append(tagged)
            suppressed_reason_counts[reason] = suppressed_reason_counts.get(reason, 0) + 1
            continue
        active_process_findings.append(item)

    highest = "low"
    for item in active_findings:
        highest = _highest_severity(highest, str(item.get("severity", "low")))
    for item in active_process_findings:
        highest = _highest_severity(highest, str(item.get("severity", "low")))

    filtered = dict(scan)
    filtered["finding_count"] = len(active_findings)
    filtered["process_finding_count"] = len(active_process_findings)
    filtered["highest_severity"] = highest
    filtered["findings"] = active_findings[:500]
    filtered["process_findings"] = active_process_findings[:200]
    filtered["noise_control"] = {
        "raw_finding_count": len(findings),
        "raw_process_finding_count": len(process_findings),
        "suppressed_finding_count": len(suppressed_findings),
        "suppressed_process_finding_count": len(suppressed_process_findings),
        "suppressed_reason_counts": suppressed_reason_counts,
        "suppressed_findings": suppressed_findings[:100],
        "suppressed_process_findings": suppressed_process_findings[:100],
    }
    return filtered


def _issue_summary(report: dict[str, Any]) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    steps: list[str] = []
    contradiction = dict(report.get("contradiction") or {})
    source = dict(report.get("source_integrity") or {})
    antivirus = dict(report.get("antivirus_scan") or {})
    execution = dict(report.get("execution_errors") or {})
    health = dict(report.get("health") or {})
    if bool((contradiction.get("continuity") or {}).get("has_contradiction", False)):
        issues.append("self_contradiction_active")
        steps.append("Resolve self contradiction before trusting broader autonomous behavior.")
    if int(source.get("syntax_error_count", 0) or 0) > 0:
        issues.append("source_syntax_errors")
        steps.append("Fix syntax errors in the scanned Python source set.")
    antivirus_total = int(antivirus.get("finding_count", 0) or 0) + int(antivirus.get("process_finding_count", 0) or 0)
    if antivirus_total > 0:
        issues.append("antivirus_findings")
        steps.append("Review threat findings and quarantine or suppress only after verification.")
    if int(execution.get("unguarded_failure_count", 0) or 0) > 0:
        issues.append("recent_execution_failures")
        steps.append("Inspect recent unguarded failures and remove the root cause instead of retrying blindly.")
    if float(health.get("health_score", 0.0) or 0.0) < 60.0:
        issues.append("runtime_health_low")
        steps.append("Raise core runtime health above the minimum stability floor.")
    if not steps:
        steps.append("Maintain the smooth flow monitor and keep contradiction, source, execution, and threat lanes clean.")
    return issues, steps


def _score_report(report: dict[str, Any], *, source_scan_available: bool) -> dict[str, Any]:
    contradiction = dict(report.get("contradiction") or {})
    health = dict(report.get("health") or {})
    source = dict(report.get("source_integrity") or {})
    antivirus = dict(report.get("antivirus_scan") or {})
    execution = dict(report.get("execution_errors") or {})
    checks = {
        "contradiction_clear": not bool((contradiction.get("continuity") or {}).get("has_contradiction", False))
        and bool((contradiction.get("continuity") or {}).get("same_system", True)),
        "runtime_health_floor": float(health.get("health_score", 0.0) or 0.0) >= 60.0,
        "source_scan_available": bool(source_scan_available),
        "source_clean": int(source.get("syntax_error_count", 0) or 0) == 0,
        "antivirus_clean": (int(antivirus.get("finding_count", 0) or 0) + int(antivirus.get("process_finding_count", 0) or 0)) == 0,
        "recent_failures_clear": int(execution.get("unguarded_failure_count", 0) or 0) == 0,
    }
    issues, steps = _issue_summary(report)
    if not source_scan_available:
        issues.append("source_scan_missing")
        steps.insert(0, "Run `zero ai flow scan` to establish a full contradiction, bug/error, and threat baseline.")
    score = score_from_checks(checks, issues=issues)
    return {"checks": checks, "score": score, "highest_value_steps": steps}


def flow_scan(cwd: str, target: str = ".") -> dict[str, Any]:
    contradiction = contradiction_engine_status(cwd)
    health = capture_health_snapshot(cwd)
    source_integrity = _source_integrity_scan(cwd, target)
    antivirus_scan = _filter_antivirus_noise(scan_target_readonly(cwd, target))
    antivirus_monitor = antivirus_monitor_status(cwd)
    antivirus_agent = antivirus_agent_status(cwd)
    quarantine = antivirus_quarantine_list(cwd)
    execution_errors = _recent_execution_signals(cwd)

    report = {
        "ok": True,
        "time_utc": _utc_now(),
        "target": target,
        "contradiction": contradiction,
        "health": health,
        "source_integrity": source_integrity,
        "antivirus_scan": antivirus_scan,
        "antivirus_monitor": antivirus_monitor,
        "antivirus_agent": antivirus_agent,
        "quarantine": quarantine,
        "execution_errors": execution_errors,
    }
    scoring = _score_report(report, source_scan_available=True)
    highest_severity = _highest_severity(
        source_integrity.get("highest_severity", "unknown"),
        antivirus_scan.get("highest_severity", "unknown"),
        "critical" if bool((contradiction.get("continuity") or {}).get("has_contradiction", False)) else "low",
        "high" if int(execution_errors.get("unguarded_failure_count", 0) or 0) > 0 else "low",
        "medium" if float(health.get("health_score", 0.0) or 0.0) < 60.0 else "low",
    )
    issue_count = len(scoring["score"].get("issues", []))
    summary = {
        "flow_score": scoring["score"]["score"],
        "issue_count": issue_count,
        "highest_severity": highest_severity,
        "source_syntax_error_count": int(source_integrity.get("syntax_error_count", 0) or 0),
        "antivirus_finding_count": int(antivirus_scan.get("finding_count", 0) or 0) + int(antivirus_scan.get("process_finding_count", 0) or 0),
        "unguarded_failure_count": int(execution_errors.get("unguarded_failure_count", 0) or 0),
        "health_score": float(health.get("health_score", 0.0) or 0.0),
    }
    out = {
        "ok": True,
        "time_utc": report["time_utc"],
        "path": str(_path(cwd)),
        "target": target,
        "summary": summary,
        "checks": scoring["checks"],
        "score": scoring["score"],
        "highest_value_steps": scoring["highest_value_steps"],
        "report": report,
    }
    state = _load(_path(cwd), _default_state())
    state["last_scan_utc"] = report["time_utc"]
    state["last_target"] = target
    state["last_score"] = summary["flow_score"]
    state["last_issue_count"] = issue_count
    state["last_highest_severity"] = highest_severity
    state["last_report"] = out
    history = list(state.get("history", []))
    history.append(
        {
            "time_utc": report["time_utc"],
            "target": target,
            "flow_score": summary["flow_score"],
            "issue_count": issue_count,
            "highest_severity": highest_severity,
        }
    )
    state["history"] = history[-20:]
    _save(_path(cwd), state)
    return out


def flow_status(cwd: str) -> dict[str, Any]:
    path = _path(cwd)
    state = _load(path, _default_state())
    contradiction = contradiction_engine_status(cwd)
    health = capture_health_snapshot(cwd)
    antivirus_monitor = antivirus_monitor_status(cwd)
    antivirus_agent = antivirus_agent_status(cwd)
    quarantine = antivirus_quarantine_list(cwd)
    execution_errors = _recent_execution_signals(cwd)
    last_report = dict(state.get("last_report") or {})
    source_integrity = dict((((last_report.get("report") or {}).get("source_integrity")) or {}))
    last_antivirus_scan = dict((((last_report.get("report") or {}).get("antivirus_scan")) or {}))
    antivirus_scan = last_antivirus_scan or _filter_antivirus_noise(_last_antivirus_scan(cwd))

    report = {
        "contradiction": contradiction,
        "health": health,
        "source_integrity": source_integrity,
        "antivirus_scan": antivirus_scan,
        "antivirus_monitor": antivirus_monitor,
        "antivirus_agent": antivirus_agent,
        "quarantine": quarantine,
        "execution_errors": execution_errors,
    }
    source_scan_available = bool(source_integrity)
    scoring = _score_report(report, source_scan_available=source_scan_available)
    highest_severity = _highest_severity(
        str(state.get("last_highest_severity", "unknown")),
        "critical" if bool((contradiction.get("continuity") or {}).get("has_contradiction", False)) else "low",
        str(antivirus_scan.get("highest_severity", "unknown")),
        "high" if int(execution_errors.get("unguarded_failure_count", 0) or 0) > 0 else "low",
        "medium" if float(health.get("health_score", 0.0) or 0.0) < 60.0 else "low",
    )
    return {
        "ok": True,
        "path": str(path),
        "active": True,
        "ready": True,
        "last_scan_utc": str(state.get("last_scan_utc", "")),
        "last_target": str(state.get("last_target", ".")),
        "summary": {
            "flow_score": float(state.get("last_score", scoring["score"]["score"]) or scoring["score"]["score"]),
            "issue_count": int(
                (state.get("last_issue_count") if state.get("last_scan_utc") else len(scoring["score"].get("issues", []))) or 0
            ),
            "highest_severity": highest_severity,
            "source_scan_available": source_scan_available,
            "antivirus_scan_available": bool(last_antivirus_scan) or not bool(antivirus_scan.get("missing", False)),
        },
        "checks": scoring["checks"],
        "contradiction": contradiction,
        "health": health,
        "antivirus_monitor": antivirus_monitor,
        "antivirus_agent": antivirus_agent,
        "quarantine": quarantine,
        "execution_errors": execution_errors,
        "source_integrity": source_integrity,
        "antivirus_scan": antivirus_scan,
        "history_count": len(list(state.get("history", []))),
        "highest_value_steps": scoring["highest_value_steps"],
    }


def flow_refresh(cwd: str) -> dict[str, Any]:
    return flow_status(cwd)

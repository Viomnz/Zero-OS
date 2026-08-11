from __future__ import annotations

import json
from pathlib import Path

from zero_os.pure_logic_security_api import quarantine_file, scan_target
from zero_os.score_system import score_from_checks


def _runtime_report_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "antivirus_agent_report.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def run_antivirus_agent(
    cwd: str,
    target: str = ".",
    auto_quarantine: bool = False,
    *,
    scan_snapshot: dict | None = None,
) -> dict:
    scan = scan_target(cwd, target, scan_snapshot=scan_snapshot)
    quarantined = []
    if auto_quarantine:
        for finding in scan.get("findings", [])[:100]:
            q = quarantine_file(cwd, str(finding.get("path", "")), reason="antivirus_agent")
            if q.get("ok"):
                quarantined.append({"id": q.get("id"), "path": finding.get("path")})

    checks = {
        "scan_ok": bool(scan.get("ok", False)),
        "no_findings": int(scan.get("finding_count", 0)) == 0,
        "no_process_findings": int(scan.get("process_finding_count", 0)) == 0,
        "control_plane_bound": bool(scan.get("pure_logic_control_revision")),
    }
    issues = []
    if not checks["scan_ok"]:
        issues.append("scan_not_ok")
    if not checks["no_findings"]:
        issues.append("findings_present")
    if not checks["no_process_findings"]:
        issues.append("process_findings_present")
    if not checks["control_plane_bound"]:
        issues.append("security_control_plane_binding_missing")
    scoring = score_from_checks(checks, issues=issues)

    report = {
        "ok": bool(scan.get("ok", False)) and checks["control_plane_bound"],
        "target": target,
        "auto_quarantine": bool(auto_quarantine),
        "scan_snapshot_reused": bool(scan_snapshot),
        "finding_count": int(scan.get("finding_count", 0)),
        "highest_severity": scan.get("highest_severity", "low"),
        "incident_actions": scan.get("incident_actions", []),
        "quarantined_count": len(quarantined),
        "quarantined": quarantined,
        "scan_report": scan,
        "pure_logic_control_revision": scan.get("pure_logic_control_revision"),
        "pure_logic_control_digest": scan.get("pure_logic_control_digest"),
        "system_score": scoring["score"],
        "perfect": scoring["perfect"],
        "issues": scoring["issues"],
        "root_issues": scoring["root_issues"],
    }
    _runtime_report_path(cwd).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def antivirus_agent_status(cwd: str) -> dict:
    p = _runtime_report_path(cwd)
    if not p.exists():
        return {"ok": False, "missing": True, "hint": "run: antivirus agent run"}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "missing": True, "hint": "run: antivirus agent run"}

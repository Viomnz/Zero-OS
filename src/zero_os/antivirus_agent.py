from __future__ import annotations

import json
from pathlib import Path

from zero_os.antivirus import quarantine_file, scan_target


def _runtime_report_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "antivirus_agent_report.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def run_antivirus_agent(cwd: str, target: str = ".", auto_quarantine: bool = False) -> dict:
    scan = scan_target(cwd, target)
    quarantined = []
    if auto_quarantine:
        for finding in scan.get("findings", [])[:100]:
            q = quarantine_file(cwd, str(finding.get("path", "")), reason="antivirus_agent")
            if q.get("ok"):
                quarantined.append({"id": q.get("id"), "path": finding.get("path")})

    report = {
        "ok": True,
        "target": target,
        "auto_quarantine": bool(auto_quarantine),
        "finding_count": int(scan.get("finding_count", 0)),
        "highest_severity": scan.get("highest_severity", "low"),
        "incident_actions": scan.get("incident_actions", []),
        "quarantined_count": len(quarantined),
        "quarantined": quarantined,
        "scan_report": scan,
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

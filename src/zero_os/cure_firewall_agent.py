from __future__ import annotations

import json
from pathlib import Path

from zero_os.cure_firewall import run_cure_firewall, run_cure_firewall_net, verify_beacon, verify_beacon_net
from zero_os.score_system import score_from_checks


DEFAULT_FILE_SUFFIXES = {".py", ".ps1", ".json", ".yaml", ".yml", ".toml", ".md", ".txt"}


def _runtime_report_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "cure_firewall_agent_report.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _eligible_targets(base: Path) -> list[str]:
    out: list[str] = []
    skip_roots = {base / ".git", base / ".zero_os", base / "__pycache__"}
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in DEFAULT_FILE_SUFFIXES:
            continue
        if any(str(p).startswith(str(r)) for r in skip_roots):
            continue
        try:
            out.append(str(p.resolve().relative_to(base)).replace("\\", "/"))
        except ValueError:
            continue
    return out


def _discover_targets(base: Path, limit: int = 25) -> tuple[list[str], int]:
    eligible = _eligible_targets(base)
    cap = max(1, int(limit))
    return eligible[:cap], len(eligible)


def run_cure_firewall_agent(cwd: str, pressure: int = 80, targets: list[str] | None = None, urls: list[str] | None = None, verify: bool = True, *, scan_snapshot: dict | None = None) -> dict:
    base = Path(cwd).resolve()
    pressure = max(0, min(100, int(pressure)))
    discovery_mode = "explicit"
    eligible_count = 0
    if targets:
        file_targets = list(targets)
        eligible_count = len(file_targets)
    elif scan_snapshot and list(scan_snapshot.get("preferred_firewall_targets") or []):
        file_targets = list(scan_snapshot.get("preferred_firewall_targets") or [])
        eligible_count = int(scan_snapshot.get("eligible_file_count", len(file_targets)) or len(file_targets))
        discovery_mode = "snapshot"
    else:
        file_targets, eligible_count = _discover_targets(base)
        discovery_mode = "bounded_discovery"
    net_targets = list(urls or [])

    file_runs = []
    for rel in file_targets:
        result = run_cure_firewall(cwd, rel, pressure)
        record = {
            "target": rel,
            "activated": result.activated,
            "survived": result.survived,
            "score": result.score,
            "notes": result.notes,
            "smart_logic": result.smart_logic or {},
            "beacon": result.beacon_path,
            "backup": result.backup_path,
        }
        if verify and result.survived:
            ok, reason = verify_beacon(cwd, rel)
            record["verify_ok"] = ok
            record["verify_reason"] = reason
        file_runs.append(record)

    net_runs = []
    for url in net_targets:
        result = run_cure_firewall_net(cwd, url, pressure)
        record = {
            "target": url,
            "activated": result.activated,
            "survived": result.survived,
            "score": result.score,
            "notes": result.notes,
            "smart_logic": result.smart_logic or {},
            "beacon": result.beacon_path,
        }
        if verify and result.survived:
            ok, reason = verify_beacon_net(cwd, url)
            record["verify_ok"] = ok
            record["verify_reason"] = reason
        net_runs.append(record)

    file_ok = sum(1 for r in file_runs if r.get("survived") is True)
    file_verified = sum(1 for r in file_runs if r.get("verify_ok") is True)
    net_ok = sum(1 for r in net_runs if r.get("survived") is True)
    net_verified = sum(1 for r in net_runs if r.get("verify_ok") is True)
    issues = [f"file_failed:{r.get('target')}" for r in file_runs if not bool(r.get("survived", False))]
    issues += [f"file_verify_failed:{r.get('target')}" for r in file_runs if verify and bool(r.get("survived", False)) and not bool(r.get("verify_ok", False))]
    issues += [f"net_failed:{r.get('target')}" for r in net_runs if not bool(r.get("survived", False))]
    issues += [f"net_verify_failed:{r.get('target')}" for r in net_runs if verify and bool(r.get("survived", False)) and not bool(r.get("verify_ok", False))]

    scanned_count = len(file_runs)
    coverage_ratio = 1.0 if eligible_count <= 0 else min(1.0, scanned_count / eligible_count)
    scope_complete = discovery_mode == "explicit" or (eligible_count > 0 and scanned_count >= eligible_count)
    if not scope_complete:
        issues.append(f"scope_incomplete:{scanned_count}/{eligible_count}")

    scoring = score_from_checks(
        {
            "files_survived_all": file_ok == len(file_runs) if file_runs else True,
            "files_verified_all": file_verified == len(file_runs) if verify and file_runs else True,
            "net_survived_all": net_ok == len(net_runs) if net_runs else True,
            "net_verified_all": net_verified == len(net_runs) if verify and net_runs else True,
            "scope_complete": scope_complete,
        },
        issues=issues,
    )
    mechanism_ok = not any(str(x).startswith(("file_failed:", "file_verify_failed:", "net_failed:", "net_verify_failed:")) for x in issues)
    ok = mechanism_ok and scope_complete and not scoring["issues"]
    report = {
        "ok": ok,
        "mechanism_ok": mechanism_ok,
        "pressure": pressure,
        "scan_snapshot_reused": bool(scan_snapshot and not targets),
        "discovery_mode": discovery_mode,
        "eligible_file_targets": eligible_count,
        "file_targets": scanned_count,
        "coverage_ratio": round(coverage_ratio, 6),
        "scope_complete": scope_complete,
        "demonstrated_scope": list(file_targets),
        "unresolved_target_count": max(0, eligible_count - scanned_count),
        "file_survived": file_ok,
        "file_verified": file_verified,
        "net_targets": len(net_runs),
        "net_survived": net_ok,
        "net_verified": net_verified,
        "system_score": scoring["score"],
        "perfect": bool(scoring["perfect"] and scope_complete and mechanism_ok),
        "issues": scoring["issues"],
        "root_issues": scoring["root_issues"],
        "files": file_runs,
        "net": net_runs,
        "pure_logic_status": "SURVIVED_IN_DEMONSTRATED_SCOPE" if ok else ("MECHANISM_PASSED_SCOPE_INCOMPLETE" if mechanism_ok else "CONTESTED"),
    }
    _runtime_report_path(cwd).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def cure_firewall_agent_status(cwd: str) -> dict:
    path = _runtime_report_path(cwd)
    if not path.exists():
        return {"ok": False, "missing": True, "hint": "run: cure firewall agent run"}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "missing": True, "hint": "run: cure firewall agent run"}

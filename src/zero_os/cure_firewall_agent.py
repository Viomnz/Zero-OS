from __future__ import annotations

import json
from pathlib import Path

from zero_os.cure_firewall import (
    run_cure_firewall,
    run_cure_firewall_net,
    verify_beacon,
    verify_beacon_net,
)


DEFAULT_FILE_SUFFIXES = {
    ".py",
    ".ps1",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
}


def _runtime_report_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "cure_firewall_agent_report.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _discover_targets(base: Path, limit: int = 25) -> list[str]:
    out: list[str] = []
    skip_roots = {base / ".git", base / ".zero_os", base / "__pycache__"}
    for p in base.rglob("*"):
        if len(out) >= limit:
            break
        if not p.is_file():
            continue
        if p.suffix.lower() not in DEFAULT_FILE_SUFFIXES:
            continue
        if any(str(p).startswith(str(r)) for r in skip_roots):
            continue
        try:
            rel = str(p.resolve().relative_to(base)).replace("\\", "/")
        except ValueError:
            continue
        out.append(rel)
    return out


def run_cure_firewall_agent(
    cwd: str,
    pressure: int = 80,
    targets: list[str] | None = None,
    urls: list[str] | None = None,
    verify: bool = True,
) -> dict:
    base = Path(cwd).resolve()
    pressure = max(0, min(100, int(pressure)))
    file_targets = targets or _discover_targets(base)
    net_targets = urls or []

    file_runs = []
    for rel in file_targets:
        result = run_cure_firewall(cwd, rel, pressure)
        record = {
            "target": rel,
            "activated": result.activated,
            "survived": result.survived,
            "score": result.score,
            "notes": result.notes,
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

    report = {
        "ok": True,
        "pressure": pressure,
        "file_targets": len(file_runs),
        "file_survived": file_ok,
        "file_verified": file_verified,
        "net_targets": len(net_runs),
        "net_survived": net_ok,
        "net_verified": net_verified,
        "files": file_runs,
        "net": net_runs,
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

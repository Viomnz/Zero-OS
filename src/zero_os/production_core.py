from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from zero_os.cure_firewall import run_cure_firewall_net, verify_beacon_net

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "production"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _zero_state_path(cwd: str) -> Path:
    return Path(cwd).resolve() / ".zero_os" / "state.json"


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_state(cwd: str) -> dict:
    p = _zero_state_path(cwd)
    return _load(p, {})


def _save_state(cwd: str, payload: dict) -> None:
    _save(_zero_state_path(cwd), payload)


def _key(cwd: str, name: str) -> bytes:
    p = Path(cwd).resolve() / ".zero_os" / "keys" / f"{name}.key"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(secrets.token_hex(32), encoding="utf-8")
    return p.read_text(encoding="utf-8").strip().encode("utf-8")


def sandbox_status(cwd: str) -> dict:
    path = _state_root(cwd) / "sandbox_policy.json"
    policy = _load(path, {"allow_prefix": [], "deny_prefix": []})
    _save(path, policy)
    return policy


def sandbox_update(cwd: str, mode: str, prefix: str) -> dict:
    policy = sandbox_status(cwd)
    allow = set(policy.get("allow_prefix", []))
    deny = set(policy.get("deny_prefix", []))
    p = prefix.strip().lower()
    if mode == "allow":
        allow.add(p)
        deny.discard(p)
    else:
        deny.add(p)
        allow.discard(p)
    out = {"allow_prefix": sorted(allow), "deny_prefix": sorted(deny)}
    _save(_state_root(cwd) / "sandbox_policy.json", out)
    return out


def sandbox_check(cwd: str, command_text: str) -> tuple[bool, str]:
    policy = sandbox_status(cwd)
    cmd = command_text.strip().lower()
    for d in policy.get("deny_prefix", []):
        if cmd.startswith(d):
            return (False, f"blocked by deny prefix: {d}")
    allow = policy.get("allow_prefix", [])
    if allow and not any(cmd.startswith(a) for a in allow):
        return (False, "blocked: command not in allow prefixes")
    return (True, "allowed")


def freedom_status(cwd: str) -> dict:
    p = _state_root(cwd) / "freedom_policy.json"
    default = {
        "mode": "guarded",
        "updated_utc": _utc_now(),
        "features": {
            "ui_customization": True,
            "plugin_freedom": True,
            "codex_route_freedom": True,
            "safety_rails": True,
        },
    }
    data = _load(p, default)
    _save(p, data)
    return data


def freedom_mode_set(cwd: str, mode: str) -> dict:
    m = mode.strip().lower()
    if m not in {"open", "guarded"}:
        return {"ok": False, "reason": "mode must be open or guarded"}

    data = freedom_status(cwd)
    data["mode"] = m
    data["updated_utc"] = _utc_now()
    _save(_state_root(cwd) / "freedom_policy.json", data)

    # Apply runtime rails.
    st = _load_state(cwd)
    st.setdefault("user_mode", "casual")
    st.setdefault("performance_profile", "auto")
    if m == "open":
        st["mark_strict"] = False
        st["net_strict"] = False
        sandbox = {"allow_prefix": [], "deny_prefix": []}
    else:
        st["mark_strict"] = True
        st["net_strict"] = True
        sandbox = {
            "allow_prefix": [
                "python ",
                "mode ",
                "profile ",
                "search ",
                "fetch ",
                "znet ",
                "cure firewall ",
            ],
            "deny_prefix": [
                "format ",
                "diskpart ",
                "del c:\\",
                "rm -rf /",
            ],
        }
    _save_state(cwd, st)
    _save(_state_root(cwd) / "sandbox_policy.json", sandbox)
    return {"ok": True, "mode": m, "state": st, "sandbox": sandbox}


def freedom_reset(cwd: str) -> dict:
    # Reset to balanced defaults with guarded rails.
    _save(
        _state_root(cwd) / "freedom_policy.json",
        {
            "mode": "guarded",
            "updated_utc": _utc_now(),
            "features": {
                "ui_customization": True,
                "plugin_freedom": True,
                "codex_route_freedom": True,
                "safety_rails": True,
            },
        },
    )
    st = _load_state(cwd)
    st["user_mode"] = "casual"
    st["performance_profile"] = "auto"
    st["mark_strict"] = True
    st["net_strict"] = True
    _save_state(cwd, st)
    _save(
        _state_root(cwd) / "sandbox_policy.json",
        {
            "allow_prefix": [
                "python ",
                "mode ",
                "profile ",
                "search ",
                "fetch ",
                "znet ",
                "cure firewall ",
            ],
            "deny_prefix": [
                "format ",
                "diskpart ",
                "del c:\\",
                "rm -rf /",
            ],
        },
    )
    return {"ok": True, "mode": "guarded", "state": st}


def update_create(cwd: str, version: str) -> dict:
    root = _state_root(cwd)
    pkg = root / "updates" / version
    pkg.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": version,
        "created_utc": _utc_now(),
        "files": ["src/", "ai_from_scratch/", "zero_os_launcher.ps1", "README.md"],
    }
    sig = hmac.new(_key(cwd, "updater"), json.dumps(manifest, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()
    manifest["signature"] = sig
    _save(pkg / "manifest.json", manifest)
    return manifest


def update_apply(cwd: str, version: str) -> dict:
    root = _state_root(cwd)
    pkg = root / "updates" / version / "manifest.json"
    if not pkg.exists():
        return {"ok": False, "reason": "update package missing"}
    manifest = _load(pkg, {})
    sig = manifest.pop("signature", "")
    exp = hmac.new(_key(cwd, "updater"), json.dumps(manifest, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, exp):
        return {"ok": False, "reason": "invalid update signature"}
    snap = snapshot_create(cwd)
    history = _load(root / "update_history.json", [])
    history.append({"time_utc": _utc_now(), "version": version, "snapshot": snap["id"]})
    _save(root / "update_history.json", history)
    return {"ok": True, "version": version, "snapshot": snap["id"]}


def update_rollback(cwd: str) -> dict:
    history = _load(_state_root(cwd) / "update_history.json", [])
    if not history:
        return {"ok": False, "reason": "no update history"}
    last = history[-1]
    restored = snapshot_restore(cwd, last["snapshot"])
    return {"ok": restored["ok"], "restored_snapshot": last["snapshot"]}


def deps_add(cwd: str, name: str, version: str) -> dict:
    path = _state_root(cwd) / "deps_registry.json"
    data = _load(path, {"deps": []})
    deps = [d for d in data["deps"] if d.get("name") != name]
    deps.append({"name": name, "version": version, "updated_utc": _utc_now()})
    data["deps"] = sorted(deps, key=lambda x: x["name"])
    _save(path, data)
    return data


def deps_list(cwd: str) -> dict:
    return _load(_state_root(cwd) / "deps_registry.json", {"deps": []})


def jobs_add(cwd: str, priority: int, task: str) -> dict:
    path = _state_root(cwd) / "jobs.json"
    data = _load(path, {"jobs": []})
    data["jobs"].append({"id": int(time.time() * 1000), "priority": int(priority), "task": task, "status": "queued"})
    data["jobs"] = sorted(data["jobs"], key=lambda x: (-x["priority"], x["id"]))
    _save(path, data)
    return data


def jobs_list(cwd: str) -> dict:
    return _load(_state_root(cwd) / "jobs.json", {"jobs": []})


def jobs_run_one(cwd: str) -> dict:
    data = jobs_list(cwd)
    if not data["jobs"]:
        return {"ok": False, "reason": "empty queue"}
    job = data["jobs"][0]
    job["status"] = "done"
    job["done_utc"] = _utc_now()
    _save(_state_root(cwd) / "jobs.json", data)
    return {"ok": True, "job": job}


def isolation_set(cwd: str, name: str, cpu: int, mem_mb: int) -> dict:
    path = _state_root(cwd) / "agent_isolation.json"
    data = _load(path, {"agents": {}})
    data["agents"][name] = {"cpu_limit": int(cpu), "mem_mb_limit": int(mem_mb), "updated_utc": _utc_now()}
    _save(path, data)
    return data


def isolation_list(cwd: str) -> dict:
    return _load(_state_root(cwd) / "agent_isolation.json", {"agents": {}})


def observability_report(cwd: str) -> dict:
    base = Path(cwd).resolve()
    rt = base / ".zero_os" / "runtime"
    report = {
        "time_utc": _utc_now(),
        "heartbeat_exists": (rt / "zero_ai_heartbeat.json").exists(),
        "security_report_exists": (rt / "security_report.json").exists(),
        "agent_health_exists": (rt / "agent_health.json").exists(),
        "queue_size": len((rt / "zero_ai_tasks.txt").read_text(encoding="utf-8", errors="replace").splitlines()) if (rt / "zero_ai_tasks.txt").exists() else 0,
        "output_kb": int((rt / "zero_ai_output.txt").stat().st_size / 1024) if (rt / "zero_ai_output.txt").exists() else 0,
    }
    _save(_state_root(cwd) / "observability.json", report)
    return report


def snapshot_create(cwd: str) -> dict:
    base = Path(cwd).resolve()
    sid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = _state_root(cwd) / "snapshots" / sid
    root.mkdir(parents=True, exist_ok=True)
    targets = ["src", "ai_from_scratch", "zero_os_launcher.ps1", "README.md", "security", "drivers", "apps", "services"]
    copied = []
    for t in targets:
        p = base / t
        if not p.exists():
            continue
        dst = root / t
        if p.is_dir():
            shutil.copytree(p, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
        copied.append(t)
    meta = {"id": sid, "created_utc": _utc_now(), "copied": copied}
    _save(root / "snapshot.json", meta)
    return meta


def snapshot_list(cwd: str) -> dict:
    root = _state_root(cwd) / "snapshots"
    if not root.exists():
        return {"snapshots": []}
    items = []
    for p in sorted(root.iterdir()):
        meta = _load(p / "snapshot.json", {})
        if meta:
            items.append(meta)
    return {"snapshots": items}


def snapshot_restore(cwd: str, snapshot_id: str) -> dict:
    base = Path(cwd).resolve()
    src = _state_root(cwd) / "snapshots" / snapshot_id
    if not src.exists():
        return {"ok": False, "reason": "snapshot not found"}
    meta = _load(src / "snapshot.json", {})
    for t in meta.get("copied", []):
        from_p = src / t
        to_p = base / t
        if from_p.is_dir():
            shutil.copytree(from_p, to_p, dirs_exist_ok=True)
        elif from_p.is_file():
            to_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(from_p, to_p)
    return {"ok": True, "snapshot": snapshot_id}


def plugin_sign(cwd: str, name: str) -> dict:
    p = Path(cwd).resolve() / "plugins" / f"{name}.py"
    if not p.exists():
        return {"ok": False, "reason": "plugin missing"}
    data = p.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    sig = hmac.new(_key(cwd, "plugin_sign"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    rec = {"plugin": name, "sha256": digest, "signature": sig, "signed_utc": _utc_now()}
    db = _state_root(cwd) / "plugin_signatures.json"
    records = _load(db, {"plugins": {}})
    records["plugins"][name] = rec
    _save(db, records)
    return {"ok": True, **rec}


def plugin_verify(cwd: str, name: str) -> dict:
    db = _load(_state_root(cwd) / "plugin_signatures.json", {"plugins": {}})
    rec = db.get("plugins", {}).get(name)
    if not rec:
        return {"ok": False, "reason": "no signature"}
    p = Path(cwd).resolve() / "plugins" / f"{name}.py"
    if not p.exists():
        return {"ok": False, "reason": "plugin missing"}
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    sig = hmac.new(_key(cwd, "plugin_sign"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"ok": hmac.compare_digest(sig, rec.get("signature", "")), "plugin": name}


def api_token_create(cwd: str) -> dict:
    token = secrets.token_urlsafe(24)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    _save(_state_root(cwd) / "api_auth.json", {"token_sha256": digest, "updated_utc": _utc_now()})
    return {"token": token}


def api_token_verify(cwd: str, token: str) -> dict:
    rec = _load(_state_root(cwd) / "api_auth.json", {})
    got = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return {"ok": bool(rec) and hmac.compare_digest(got, rec.get("token_sha256", ""))}


def benchmark_run(cwd: str) -> dict:
    base = Path(cwd).resolve()
    t0 = time.perf_counter()
    count = len(list(base.rglob("*.py")))
    t1 = time.perf_counter()
    data = b"x" * 200000
    h = hashlib.sha256(data).hexdigest()
    t2 = time.perf_counter()
    out = {
        "time_utc": _utc_now(),
        "file_scan_ms": int((t1 - t0) * 1000),
        "hash_200kb_ms": int((t2 - t1) * 1000),
        "py_file_count": count,
        "hash_sample": h[:16],
    }
    _save(_state_root(cwd) / "benchmarks.json", out)
    return out


def playbook_init(cwd: str) -> dict:
    p = Path(cwd).resolve() / "security" / "error_playbooks.json"
    payload = {
        "version": 1,
        "taxonomy": ["integrity_failure", "security_policy_violation", "network_untrusted", "plugin_signature_invalid"],
        "playbooks": {
            "integrity_failure": ["quarantine", "restore", "replace_or_eliminate"],
            "security_policy_violation": ["contain", "report", "operator_review"],
            "network_untrusted": ["deny_request", "add_net_policy_or_beacon"],
            "plugin_signature_invalid": ["block_plugin", "verify_signature", "resign_if_trusted"],
        },
    }
    _save(p, payload)
    return payload


def playbook_show(cwd: str) -> dict:
    return _load(Path(cwd).resolve() / "security" / "error_playbooks.json", {"missing": True})


def release_init(cwd: str) -> dict:
    p = Path(cwd).resolve() / "zero_os_config" / "release.json"
    payload = {"version": "0.1.0", "changelog": [], "updated_utc": _utc_now()}
    _save(p, payload)
    return payload


def release_bump(cwd: str, version: str) -> dict:
    p = Path(cwd).resolve() / "zero_os_config" / "release.json"
    data = _load(p, {"version": "0.1.0", "changelog": []})
    prev = data.get("version", "0.1.0")
    data["version"] = version
    data.setdefault("changelog", []).append({"from": prev, "to": version, "time_utc": _utc_now()})
    data["updated_utc"] = _utc_now()
    _save(p, data)
    return data


def _znet_path(cwd: str) -> Path:
    return _state_root(cwd) / "znet_registry.json"


def znet_init(cwd: str, name: str) -> dict:
    data = {
        "network": name,
        "created_utc": _utc_now(),
        "nodes": {},
        "services": {},
    }
    _save(_znet_path(cwd), data)
    return data


def znet_status(cwd: str) -> dict:
    return _load(
        _znet_path(cwd),
        {"missing": True, "hint": "run: znet init <name>"},
    )


def znet_add_node(cwd: str, node: str, endpoint: str) -> dict:
    data = znet_status(cwd)
    if data.get("missing"):
        return data
    data.setdefault("nodes", {})[node] = {"endpoint": endpoint, "updated_utc": _utc_now()}
    _save(_znet_path(cwd), data)
    return data


def znet_add_service(cwd: str, service: str, node: str, path: str) -> dict:
    data = znet_status(cwd)
    if data.get("missing"):
        return data
    if node not in data.get("nodes", {}):
        return {"ok": False, "reason": f"node not found: {node}"}
    endpoint = data["nodes"][node]["endpoint"].rstrip("/")
    p = "/" + path.lstrip("/")
    data.setdefault("services", {})[service] = {
        "node": node,
        "path": p,
        "url": endpoint + p,
        "updated_utc": _utc_now(),
    }
    _save(_znet_path(cwd), data)
    return data


def znet_resolve(cwd: str, target: str) -> dict:
    data = znet_status(cwd)
    if data.get("missing"):
        return data
    if target in data.get("services", {}):
        svc = dict(data["services"][target])
        ok, reason = verify_beacon_net(cwd, svc.get("url", ""))
        svc["cure_verified"] = ok
        svc["cure_reason"] = reason
        return {"type": "service", "name": target, **svc}
    if target in data.get("nodes", {}):
        return {"type": "node", "name": target, **data["nodes"][target]}
    return {"ok": False, "reason": f"target not found: {target}"}


def znet_topology(cwd: str) -> dict:
    data = znet_status(cwd)
    if data.get("missing"):
        return data
    edges = []
    for svc, meta in data.get("services", {}).items():
        edges.append({"from": svc, "to": meta.get("node", ""), "url": meta.get("url", "")})
    return {
        "network": data.get("network", ""),
        "nodes": data.get("nodes", {}),
        "services": data.get("services", {}),
        "edges": edges,
    }


def znet_cure_apply(cwd: str, pressure: int) -> dict:
    data = znet_status(cwd)
    if data.get("missing"):
        return data
    services = data.get("services", {})
    results = []
    for name, meta in services.items():
        url = str(meta.get("url", ""))
        if not url:
            results.append({"service": name, "url": "", "activated": False, "survived": False, "notes": "missing url"})
            continue
        run = run_cure_firewall_net(cwd, url, pressure)
        valid, reason = verify_beacon_net(cwd, url) if run.survived else (False, run.notes)
        results.append(
            {
                "service": name,
                "url": url,
                "activated": run.activated,
                "survived": run.survived,
                "score": run.score,
                "beacon_path": run.beacon_path,
                "verified": valid,
                "verify_reason": reason,
            }
        )
    passed = sum(1 for r in results if r.get("verified"))
    report = {
        "time_utc": _utc_now(),
        "network": data.get("network", ""),
        "pressure": pressure,
        "service_count": len(results),
        "verified_count": passed,
        "all_verified": passed == len(results) if results else True,
        "results": results,
    }
    _save(_state_root(cwd) / "znet_cure_report.json", report)
    return report


def znet_cure_status(cwd: str) -> dict:
    return _load(
        _state_root(cwd) / "znet_cure_report.json",
        {"missing": True, "hint": "run: znet cure apply pressure <0-100>"},
    )


def process_list(limit: int = 20) -> dict:
    out = subprocess.run(
        ["tasklist", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=False,
    )
    items = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line.startswith('"'):
            continue
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) < 2:
            continue
        items.append({"name": parts[0], "pid": parts[1]})
        if len(items) >= max(1, min(200, limit)):
            break
    return {"count": len(items), "items": items}


def process_start(command: str, cwd: str) -> dict:
    if not command.strip():
        return {"ok": False, "reason": "empty command"}
    p = subprocess.Popen(command, cwd=cwd, shell=True)
    return {"ok": True, "pid": p.pid, "command": command}


def unified_shell_run(command: str, cwd: str, timeout_sec: int = 30) -> dict:
    cmd = command.strip()
    if not cmd:
        return {"ok": False, "reason": "empty command"}
    try:
        if os.name == "nt":
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_sec)),
                check=False,
            )
            engine = "powershell"
        else:
            proc = subprocess.run(
                ["/bin/sh", "-lc", cmd],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_sec)),
                check=False,
            )
            engine = "shell"
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout", "command": cmd, "timeout_sec": max(1, int(timeout_sec))}
    return {
        "ok": proc.returncode == 0,
        "engine": engine,
        "returncode": int(proc.returncode),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "command": cmd,
    }


def process_kill(target: str) -> dict:
    t = target.strip()
    if not t:
        return {"ok": False, "reason": "missing target"}
    if t.isdigit():
        out = subprocess.run(["taskkill", "/PID", t, "/F"], capture_output=True, text=True, check=False)
    else:
        out = subprocess.run(["taskkill", "/IM", t, "/F"], capture_output=True, text=True, check=False)
    ok = out.returncode == 0
    return {"ok": ok, "target": t, "stdout": out.stdout.strip(), "stderr": out.stderr.strip()}


def memory_status() -> dict:
    # Windows memory telemetry via wmic fallback.
    cmd = ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/Value"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    free_kb = None
    total_kb = None
    for line in out.stdout.splitlines():
        if line.startswith("FreePhysicalMemory="):
            free_kb = int(line.split("=", 1)[1] or "0")
        if line.startswith("TotalVisibleMemorySize="):
            total_kb = int(line.split("=", 1)[1] or "0")
    if free_kb is None or total_kb is None or total_kb == 0:
        return {"ok": False, "reason": "memory telemetry unavailable"}
    used_kb = total_kb - free_kb
    return {
        "ok": True,
        "total_mb": int(total_kb / 1024),
        "free_mb": int(free_kb / 1024),
        "used_mb": int(used_kb / 1024),
        "used_percent": round((used_kb / total_kb) * 100, 2),
    }


def _memory_telemetry_path(cwd: str) -> Path:
    return _state_root(cwd) / "memory_telemetry.json"


def memory_smart_status(cwd: str) -> dict:
    snap = memory_status()
    if not snap.get("ok", False):
        return {"ok": False, "reason": "memory telemetry unavailable"}

    path = _memory_telemetry_path(cwd)
    data = _load(path, {"samples": []})
    samples = data.get("samples", [])
    samples.append(
        {
            "time_utc": _utc_now(),
            "used_mb": snap["used_mb"],
            "free_mb": snap["free_mb"],
            "used_percent": snap["used_percent"],
            "total_mb": snap["total_mb"],
        }
    )
    samples = samples[-120:]
    data["samples"] = samples
    _save(path, data)

    avg_used = round(sum(s["used_percent"] for s in samples) / max(1, len(samples)), 2)
    peak_used = round(max(s["used_percent"] for s in samples), 2)
    pressure = "low"
    if peak_used >= 85 or avg_used >= 75:
        pressure = "high"
    elif peak_used >= 70 or avg_used >= 60:
        pressure = "medium"

    recommend_profile = "balanced"
    if pressure == "high":
        recommend_profile = "low"
    elif pressure == "low":
        recommend_profile = "high"

    return {
        "ok": True,
        "current": snap,
        "sample_count": len(samples),
        "avg_used_percent": avg_used,
        "peak_used_percent": peak_used,
        "pressure_level": pressure,
        "recommended_profile": recommend_profile,
        "recommendation": (
            "reduce background tasks and lower workload"
            if pressure == "high"
            else "keep balanced workload"
            if pressure == "medium"
            else "increase throughput safely"
        ),
    }


def memory_smart_optimize(cwd: str) -> dict:
    status = memory_smart_status(cwd)
    if not status.get("ok", False):
        return status

    pressure = status["pressure_level"]
    actions = []
    if pressure == "high":
        actions = [
            "set profile low",
            "reduce parallel tasks",
            "truncate large output buffers",
        ]
    elif pressure == "medium":
        actions = [
            "keep profile balanced",
            "monitor queue growth",
        ]
    else:
        actions = [
            "set profile high",
            "allow larger chained execution",
        ]
    plan = {
        "time_utc": _utc_now(),
        "pressure_level": pressure,
        "recommended_profile": status["recommended_profile"],
        "actions": actions,
    }
    _save(_state_root(cwd) / "memory_optimize_plan.json", plan)
    return {"ok": True, **plan}


def filesystem_status(cwd: str) -> dict:
    root = Path(cwd).resolve()
    usage = shutil.disk_usage(root)
    files = 0
    dirs = 0
    for p in root.rglob("*"):
        if p.is_file():
            files += 1
        elif p.is_dir():
            dirs += 1
    return {
        "path": str(root),
        "total_gb": round(usage.total / (1024**3), 2),
        "used_gb": round(usage.used / (1024**3), 2),
        "free_gb": round(usage.free / (1024**3), 2),
        "file_count": files,
        "dir_count": dirs,
    }


def device_status() -> dict:
    hostname = socket.gethostname()
    ip = ""
    try:
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = ""
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": hostname,
        "primary_ip": ip,
        "gpu_hint": os.environ.get("GPU", "unknown"),
    }


def security_overview(cwd: str) -> dict:
    freedom = freedom_status(cwd)
    sandbox = sandbox_status(cwd)
    state = _load_state(cwd)
    return {
        "freedom_mode": freedom.get("mode", "guarded"),
        "mark_strict": bool(state.get("mark_strict", False)),
        "net_strict": bool(state.get("net_strict", False)),
        "sandbox_allow_count": len(sandbox.get("allow_prefix", [])),
        "sandbox_deny_count": len(sandbox.get("deny_prefix", [])),
    }


def _zerofs_path(cwd: str) -> Path:
    return _state_root(cwd) / "zerofs.json"


def zerofs_init(cwd: str) -> dict:
    payload = {
        "version": 1,
        "name": "ZeroFS",
        "created_utc": _utc_now(),
        "objects": {},
        "paths": {},
    }
    _save(_zerofs_path(cwd), payload)
    return payload


def zerofs_status(cwd: str) -> dict:
    return _load(
        _zerofs_path(cwd),
        {"missing": True, "hint": "run: zerofs init"},
    )


def zerofs_put(cwd: str, rel_path: str) -> dict:
    base = Path(cwd).resolve()
    data = zerofs_status(cwd)
    if data.get("missing"):
        return data
    target = (base / rel_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return {"ok": False, "reason": "path escapes workspace"}
    if not target.exists() or not target.is_file():
        return {"ok": False, "reason": "file not found"}
    raw = target.read_bytes()
    oid = hashlib.sha256(raw).hexdigest()
    norm = str(target.relative_to(base)).replace("\\", "/")
    data.setdefault("objects", {})[oid] = {
        "sha256": oid,
        "size": len(raw),
        "source_path": norm,
        "stored_utc": _utc_now(),
    }
    data.setdefault("paths", {})[norm] = oid
    _save(_zerofs_path(cwd), data)
    return {"ok": True, "object_id": oid, "path": norm, "size": len(raw)}


def zerofs_get(cwd: str, target: str) -> dict:
    data = zerofs_status(cwd)
    if data.get("missing"):
        return data
    norm = target.replace("\\", "/").strip()
    oid = data.get("paths", {}).get(norm, norm)
    obj = data.get("objects", {}).get(oid)
    if not obj:
        return {"ok": False, "reason": f"not found: {target}"}
    return {"ok": True, "object_id": oid, **obj}


def zerofs_list(cwd: str) -> dict:
    data = zerofs_status(cwd)
    if data.get("missing"):
        return data
    paths = [{"path": p, "object_id": oid} for p, oid in sorted(data.get("paths", {}).items())]
    return {
        "name": data.get("name", "ZeroFS"),
        "object_count": len(data.get("objects", {})),
        "path_count": len(paths),
        "paths": paths[:300],
    }


def zerofs_delete(cwd: str, target: str) -> dict:
    data = zerofs_status(cwd)
    if data.get("missing"):
        return data
    norm = target.replace("\\", "/").strip()
    oid = data.get("paths", {}).pop(norm, None)
    if oid is None:
        oid = norm
    # Remove object only if no path references it.
    still_refs = any(v == oid for v in data.get("paths", {}).values())
    removed_obj = False
    if not still_refs and oid in data.get("objects", {}):
        data["objects"].pop(oid, None)
        removed_obj = True
    _save(_zerofs_path(cwd), data)
    return {"ok": True, "target": target, "removed_object": removed_obj}


def _is_cleanup_candidate(path: Path) -> bool:
    name = path.name.lower()
    if name in {"thumbs.db", ".ds_store"}:
        return True
    if name.endswith((".tmp", ".temp", ".bak", ".old", ".log")):
        return True
    if "__pycache__" in path.parts:
        return True
    if name.endswith((".pyc", ".pyo")):
        return True
    return False


def _protected_prefixes(base: Path) -> tuple[Path, ...]:
    return (
        (base / ".git").resolve(),
        (base / ".zero_os").resolve(),
        (base / "src").resolve(),
        (base / "ai_from_scratch").resolve(),
        (base / "laws").resolve(),
    )


def _is_protected_path(path: Path, protected: Iterable[Path]) -> bool:
    rp = path.resolve()
    for pref in protected:
        try:
            rp.relative_to(pref)
            return True
        except ValueError:
            continue
    return False


def _has_dependency_reference(base: Path, rel: str) -> bool:
    # Lightweight dependency check: search references in source-like files.
    needles = {rel.replace("\\", "/"), Path(rel).name}
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".py", ".json", ".md", ".txt", ".yml", ".yaml", ".toml"}:
            continue
        if _is_protected_path(p, ((base / ".zero_os").resolve(),)):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if any(n in text for n in needles):
            return True
    return False


def cleanup_status(cwd: str, stale_days: int = 30) -> dict:
    base = Path(cwd).resolve()
    protected = _protected_prefixes(base)
    now = datetime.now(timezone.utc).timestamp()
    stale_seconds = max(1, int(stale_days)) * 86400
    candidates = []
    skipped = []
    for p in base.rglob("*"):
        if not p.exists():
            continue
        if not (p.is_file() or p.is_dir()):
            continue
        if _is_protected_path(p, protected):
            continue
        if not _is_cleanup_candidate(p):
            continue
        rel = str(p.resolve().relative_to(base)).replace("\\", "/")
        mtime = p.stat().st_mtime
        is_stale = (now - mtime) >= stale_seconds
        if not is_stale:
            skipped.append({"path": rel, "reason": "not_stale"})
            continue
        if _has_dependency_reference(base, rel):
            skipped.append({"path": rel, "reason": "dependency_reference"})
            continue
        candidates.append(
            {
                "path": rel,
                "kind": "dir" if p.is_dir() else "file",
                "last_modified_utc": datetime.fromtimestamp(mtime, timezone.utc).isoformat(),
            }
        )
    report = {
        "time_utc": _utc_now(),
        "stale_days": stale_days,
        "candidate_count": len(candidates),
        "candidates": candidates[:500],
        "skipped_count": len(skipped),
        "skipped": skipped[:500],
    }
    _save(_state_root(cwd) / "useless_cleanup.json", report)
    return report


def cleanup_apply(cwd: str, stale_days: int = 30, quarantine_days: int = 7) -> dict:
    base = Path(cwd).resolve()
    report = cleanup_status(cwd, stale_days=stale_days)
    if report["candidate_count"] == 0:
        return {"ok": True, "moved_count": 0, "snapshot": None, "quarantine_dir": "", "report": report}

    snap = snapshot_create(cwd)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    qroot = base / ".zero_os" / "quarantine" / "useless" / stamp
    moved = []
    for item in report["candidates"]:
        rel = item["path"]
        src = (base / rel).resolve()
        if not src.exists():
            continue
        dst = qroot / "files" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved.append(rel)
    manifest = {
        "time_utc": _utc_now(),
        "snapshot_id": snap["id"],
        "quarantine_days": int(quarantine_days),
        "purge_after_utc": (datetime.now(timezone.utc).timestamp() + int(quarantine_days) * 86400),
        "moved_count": len(moved),
        "moved": moved,
    }
    _save(qroot / "manifest.json", manifest)
    return {
        "ok": True,
        "moved_count": len(moved),
        "snapshot": snap["id"],
        "quarantine_dir": str(qroot),
        "manifest": str(qroot / "manifest.json"),
    }


def _storage_pack_dir(cwd: str) -> Path:
    p = _state_root(cwd) / "storage_packs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _storage_index_path(cwd: str) -> Path:
    return _state_root(cwd) / "storage_index.json"


def storage_smart_status(cwd: str) -> dict:
    idx = _load(_storage_index_path(cwd), {"packs": []})
    packs = idx.get("packs", [])
    total_original = sum(int(p.get("original_bytes", 0)) for p in packs)
    total_packed = sum(int(p.get("packed_bytes", 0)) for p in packs)
    saved = max(0, total_original - total_packed)
    ratio = 0.0 if total_original == 0 else round(saved / total_original, 4)
    return {
        "pack_count": len(packs),
        "original_bytes": total_original,
        "packed_bytes": total_packed,
        "saved_bytes": saved,
        "saved_ratio": ratio,
        "packs": packs[-50:],
    }


def storage_smart_optimize(cwd: str, min_kb: int = 64) -> dict:
    base = Path(cwd).resolve()
    min_bytes = max(1, int(min_kb)) * 1024
    skip_roots = {
        (base / ".git").resolve(),
        (base / ".zero_os").resolve(),
    }
    candidates = []
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        rp = p.resolve()
        blocked = False
        for s in skip_roots:
            try:
                rp.relative_to(s)
                blocked = True
                break
            except ValueError:
                pass
        if blocked:
            continue
        if p.suffix.lower() in {".zip", ".7z", ".rar", ".gz", ".png", ".jpg", ".jpeg", ".mp4", ".mp3"}:
            continue
        size = p.stat().st_size
        if size < min_bytes:
            continue
        rel = str(rp.relative_to(base)).replace("\\", "/")
        candidates.append((p, rel, size))

    if not candidates:
        return {"ok": True, "optimized": 0, "reason": "no candidates", "status": storage_smart_status(cwd)}

    snap = snapshot_create(cwd)
    pack_dir = _storage_pack_dir(cwd)
    idx = _load(_storage_index_path(cwd), {"packs": []})
    moved = []
    for src, rel, size in candidates[:200]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        pack_name = rel.replace("/", "__") + f"__{stamp}.zip"
        pack_path = pack_dir / pack_name
        with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.write(src, arcname=rel)
        packed = pack_path.stat().st_size
        # Keep only effective packs.
        if packed >= size:
            pack_path.unlink(missing_ok=True)
            continue
        src.unlink(missing_ok=True)
        rec = {
            "path": rel,
            "pack": str(pack_path),
            "original_bytes": size,
            "packed_bytes": packed,
            "saved_bytes": size - packed,
            "snapshot": snap["id"],
            "time_utc": _utc_now(),
        }
        idx["packs"].append(rec)
        moved.append(rec)

    idx["packs"] = idx["packs"][-2000:]
    _save(_storage_index_path(cwd), idx)
    status = storage_smart_status(cwd)
    return {"ok": True, "optimized": len(moved), "snapshot": snap["id"], "items": moved[:100], "status": status}


def storage_smart_restore(cwd: str, rel_path: str) -> dict:
    base = Path(cwd).resolve()
    rel = rel_path.replace("\\", "/").strip()
    idx = _load(_storage_index_path(cwd), {"packs": []})
    pack = None
    for p in reversed(idx.get("packs", [])):
        if p.get("path") == rel:
            pack = p
            break
    if not pack:
        return {"ok": False, "reason": "pack not found for path"}
    zip_path = Path(pack["pack"])
    if not zip_path.exists():
        return {"ok": False, "reason": "pack file missing"}
    dst = (base / rel).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        try:
            zf.extract(rel, path=base)
        except KeyError:
            # fallback: first member
            members = zf.namelist()
            if not members:
                return {"ok": False, "reason": "empty pack"}
            zf.extract(members[0], path=base)
    return {"ok": True, "path": rel, "restored": str(dst)}


def system_optimize_all(cwd: str) -> dict:
    # Apply broad practical optimizations for constrained or powerful PCs.
    mem = memory_smart_optimize(cwd)
    storage = storage_smart_optimize(cwd, min_kb=64)
    cleanup = cleanup_apply(cwd, stale_days=30, quarantine_days=7)
    bench = benchmark_run(cwd)
    fs = filesystem_status(cwd)
    dev = device_status()
    sec = security_overview(cwd)
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "memory": mem,
        "storage": storage,
        "cleanup": cleanup,
        "benchmark": bench,
        "filesystem": fs,
        "device": dev,
        "security": sec,
    }


def _auto_optimize_path(cwd: str) -> Path:
    return _state_root(cwd) / "auto_optimize.json"


def auto_optimize_status(cwd: str) -> dict:
    default = {
        "enabled": False,
        "interval_minutes": 60,
        "last_run_utc": "",
        "last_result_ok": None,
    }
    data = _load(_auto_optimize_path(cwd), default)
    _save(_auto_optimize_path(cwd), data)
    return data


def auto_optimize_set(cwd: str, enabled: bool, interval_minutes: int | None = None) -> dict:
    data = auto_optimize_status(cwd)
    data["enabled"] = bool(enabled)
    if interval_minutes is not None:
        data["interval_minutes"] = max(5, min(1440, int(interval_minutes)))
    _save(_auto_optimize_path(cwd), data)
    return data


def auto_optimize_tick(cwd: str) -> dict:
    cfg = auto_optimize_status(cwd)
    if not cfg.get("enabled", False):
        return {"ran": False, "reason": "disabled"}
    now = datetime.now(timezone.utc)
    last = str(cfg.get("last_run_utc", "")).strip()
    if last:
        try:
            prev = datetime.fromisoformat(last)
        except ValueError:
            prev = now
        delta_min = (now - prev).total_seconds() / 60.0
        if delta_min < float(cfg.get("interval_minutes", 60)):
            return {"ran": False, "reason": "interval_not_reached", "minutes_remaining": round(float(cfg.get("interval_minutes", 60)) - delta_min, 2)}
    out = system_optimize_all(cwd)
    cfg["last_run_utc"] = now.isoformat()
    cfg["last_result_ok"] = bool(out.get("ok", False))
    _save(_auto_optimize_path(cwd), cfg)
    return {"ran": True, "result": out, "config": cfg}


def _auto_merge_path(cwd: str) -> Path:
    return _state_root(cwd) / "auto_merge.json"


def auto_merge_status(cwd: str) -> dict:
    default = {
        "enabled": True,
        "threshold": 0.82,
        "last_run_utc": "",
        "last_merged_count": 0,
    }
    data = _load(_auto_merge_path(cwd), default)
    _save(_auto_merge_path(cwd), data)
    return data


def auto_merge_set(cwd: str, enabled: bool, threshold: float | None = None) -> dict:
    data = auto_merge_status(cwd)
    data["enabled"] = bool(enabled)
    if threshold is not None:
        data["threshold"] = max(0.5, min(0.99, float(threshold)))
    _save(_auto_merge_path(cwd), data)
    return data


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower()))


def _similarity(a: str, b: str) -> float:
    ta = _token_set(a)
    tb = _token_set(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta.intersection(tb)) / len(ta.union(tb))


def auto_merge_queue_run(cwd: str) -> dict:
    cfg = auto_merge_status(cwd)
    if not cfg.get("enabled", True):
        return {"ran": False, "reason": "disabled", "merged_count": 0}

    runtime = Path(cwd).resolve() / ".zero_os" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    inbox = runtime / "zero_ai_tasks.txt"
    if not inbox.exists():
        inbox.write_text("", encoding="utf-8")
        return {"ran": True, "reason": "empty", "merged_count": 0, "before": 0, "after": 0}

    lines = [ln.strip() for ln in inbox.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if not lines:
        return {"ran": True, "reason": "empty", "merged_count": 0, "before": 0, "after": 0}

    keep: list[str] = []
    dropped = 0
    threshold = float(cfg.get("threshold", 0.82))
    for line in lines:
        found_similar = False
        for k in keep:
            if _similarity(line, k) >= threshold:
                found_similar = True
                dropped += 1
                break
        if not found_similar:
            keep.append(line)

    inbox.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
    cfg["last_run_utc"] = _utc_now()
    cfg["last_merged_count"] = int(dropped)
    _save(_auto_merge_path(cwd), cfg)
    return {
        "ran": True,
        "threshold": threshold,
        "before": len(lines),
        "after": len(keep),
        "merged_count": int(dropped),
        "config": cfg,
    }


def _ai_files_smart_path(cwd: str) -> Path:
    return _state_root(cwd) / "ai_files_smart.json"


def ai_files_smart_status(cwd: str) -> dict:
    cfg = _load(
        _ai_files_smart_path(cwd),
        {
            "enabled": False,
            "interval_minutes": 15,
            "last_run_utc": "",
            "last_result_ok": None,
        },
    )
    base = Path(cwd).resolve()
    runtime = base / ".zero_os" / "runtime"
    outbox = runtime / "zero_ai_output.txt"
    tasks = runtime / "zero_ai_tasks.txt"
    events = runtime / "security_events.jsonl"
    data = {
        "enabled": bool(cfg.get("enabled", False)),
        "interval_minutes": int(cfg.get("interval_minutes", 15)),
        "last_run_utc": str(cfg.get("last_run_utc", "")),
        "last_result_ok": cfg.get("last_result_ok"),
        "runtime_output_kb": int(outbox.stat().st_size / 1024) if outbox.exists() else 0,
        "runtime_tasks_lines": len(tasks.read_text(encoding="utf-8", errors="replace").splitlines()) if tasks.exists() else 0,
        "security_events_lines": len(events.read_text(encoding="utf-8", errors="replace").splitlines()) if events.exists() else 0,
    }
    _save(_ai_files_smart_path(cwd), {**cfg, **{k: data[k] for k in ("enabled", "interval_minutes", "last_run_utc", "last_result_ok")}})
    return data


def ai_files_smart_set(cwd: str, enabled: bool, interval_minutes: int | None = None) -> dict:
    cfg = _load(
        _ai_files_smart_path(cwd),
        {"enabled": False, "interval_minutes": 15, "last_run_utc": "", "last_result_ok": None},
    )
    cfg["enabled"] = bool(enabled)
    if interval_minutes is not None:
        cfg["interval_minutes"] = max(5, min(1440, int(interval_minutes)))
    _save(_ai_files_smart_path(cwd), cfg)
    return cfg


def _trim_file_lines(path: Path, keep_last: int) -> dict:
    if not path.exists():
        return {"trimmed": False, "reason": "missing", "before": 0, "after": 0}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    before = len(lines)
    if before <= keep_last:
        return {"trimmed": False, "reason": "within_limit", "before": before, "after": before}
    kept = lines[-keep_last:]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return {"trimmed": True, "before": before, "after": len(kept)}


def ai_files_smart_optimize(cwd: str, max_output_kb: int = 512, max_event_lines: int = 5000, max_task_lines: int = 3000) -> dict:
    base = Path(cwd).resolve()
    runtime = base / ".zero_os" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    outbox = runtime / "zero_ai_output.txt"
    events = runtime / "security_events.jsonl"
    tasks = runtime / "zero_ai_tasks.txt"
    actions = []

    if outbox.exists() and int(outbox.stat().st_size / 1024) > int(max_output_kb):
        # keep recent output for monitoring while controlling growth
        trim = _trim_file_lines(outbox, keep_last=2200)
        actions.append({"target": "zero_ai_output.txt", **trim})

    actions.append({"target": "security_events.jsonl", **_trim_file_lines(events, keep_last=max_event_lines)})
    actions.append({"target": "zero_ai_tasks.txt", **_trim_file_lines(tasks, keep_last=max_task_lines)})

    purged = 0
    for pyc in (base / "ai_from_scratch").rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
        purged += 1
    for cache in (base / "ai_from_scratch").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
        purged += 1
    actions.append({"target": "ai_cache", "purged_items": purged})

    return {
        "ok": True,
        "time_utc": _utc_now(),
        "actions": actions,
        "status": ai_files_smart_status(cwd),
    }


def ai_files_smart_tick(cwd: str) -> dict:
    cfg = _load(
        _ai_files_smart_path(cwd),
        {"enabled": False, "interval_minutes": 15, "last_run_utc": "", "last_result_ok": None},
    )
    if not cfg.get("enabled", False):
        return {"ran": False, "reason": "disabled"}
    now = datetime.now(timezone.utc)
    last = str(cfg.get("last_run_utc", "")).strip()
    if last:
        try:
            prev = datetime.fromisoformat(last)
        except ValueError:
            prev = now
        delta_min = (now - prev).total_seconds() / 60.0
        if delta_min < float(cfg.get("interval_minutes", 15)):
            return {"ran": False, "reason": "interval_not_reached"}
    result = ai_files_smart_optimize(cwd)
    cfg["last_run_utc"] = now.isoformat()
    cfg["last_result_ok"] = bool(result.get("ok", False))
    _save(_ai_files_smart_path(cwd), cfg)
    return {"ran": True, "result": result, "config": cfg}

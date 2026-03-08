from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from zero_os.phase_runtime import zero_ai_runtime_run, zero_ai_runtime_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def telemetry_ingest(cwd: str, source: str = "runtime") -> dict:
    runtime = zero_ai_runtime_status(cwd)
    if not runtime.get("ok", False):
        runtime = zero_ai_runtime_run(cwd)
    rec = {
        "time_utc": _utc_now(),
        "source": source,
        "runtime_score": runtime.get("runtime_score", 0),
        "law_allowed": runtime.get("universe_law_gate", {}).get("allowed", False),
        "consensus_health": runtime.get("distributed_consensus", {}).get("consensus", {}).get("global_health", 0),
    }
    p = _runtime(cwd) / "telemetry_stream.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"ok": True, "telemetry_path": str(p), "record": rec}


def node_bus_publish(cwd: str, node: str, payload: dict) -> dict:
    rec = {"time_utc": _utc_now(), "node": node, "payload": payload}
    p = _runtime(cwd) / "node_bus.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"ok": True, "bus_path": str(p), "record": rec}


def node_bus_consensus(cwd: str) -> dict:
    p = _runtime(cwd) / "node_bus.jsonl"
    if not p.exists():
        return {"ok": False, "missing": True, "hint": "run: runtime node publish <node> <json_payload>"}
    lines = [x for x in p.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
    rows = [json.loads(x) for x in lines[-200:]]
    nodes = sorted({r.get("node", "") for r in rows if r.get("node", "")})
    return {"ok": True, "node_count": len(nodes), "nodes": nodes, "message_count": len(rows), "quorum": len(nodes) >= 3}


def crypto_sign(cwd: str, payload: dict) -> dict:
    # KMS/HSM bridge placeholder: if env key exists, use it; else local fallback.
    key = os.getenv("ZERO_OS_SIGNING_KEY", "")
    source = "env_kms" if key else "local_fallback"
    if not key:
        key_path = Path(cwd).resolve() / ".zero_os" / "keys" / "runtime_signing.key"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            key_path.write_text(hashlib.sha256(str(_utc_now()).encode("utf-8")).hexdigest(), encoding="utf-8")
        key = key_path.read_text(encoding="utf-8", errors="replace").strip()
    msg = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return {"ok": True, "signature": sig, "source": source}


def runtime_preexec_gate(cwd: str, command: str) -> tuple[bool, str]:
    runtime = zero_ai_runtime_status(cwd)
    if not runtime.get("ok", False):
        runtime = zero_ai_runtime_run(cwd)
    high_impact = any(command.lower().startswith(p) for p in ("shell run ", "powershell run ", "terminal run ", "process kill "))
    if high_impact and not bool(runtime.get("runtime_ready", False)):
        return (False, "blocked by runtime gate: runtime not ready")
    if high_impact and not bool(runtime.get("universe_law_gate", {}).get("allowed", False)):
        return (False, "blocked by runtime gate: universe-law check failed")
    return (True, "runtime gate passed")


def adversarial_runtime_validate(cwd: str) -> dict:
    runtime = zero_ai_runtime_run(cwd)
    tests = {
        "proof_present": bool(runtime.get("universe_law_proof", {}).get("proof", "")),
        "replay_safe": bool(runtime.get("identity_quorum", {}).get("replay_safe", False)),
        "shard_sync": bool(runtime.get("self_model_shards", {}).get("synchronized", False)),
        "law_gate": bool(runtime.get("universe_law_gate", {}).get("allowed", False)),
    }
    out = {"ok": all(tests.values()), "time_utc": _utc_now(), "tests": tests}
    _save(_runtime(cwd) / "adversarial_runtime_validation.json", out)
    return out


def benchmark_dashboard_export(cwd: str) -> dict:
    runtime = zero_ai_runtime_status(cwd)
    if not runtime.get("ok", False):
        runtime = zero_ai_runtime_run(cwd)
    dash = {
        "time_utc": _utc_now(),
        "runtime_score": runtime.get("runtime_score", 0),
        "law_allowed": runtime.get("universe_law_gate", {}).get("allowed", False),
        "consensus_health": runtime.get("distributed_consensus", {}).get("consensus", {}).get("global_health", 0),
        "prediction_lift": runtime.get("benchmark", {}).get("prediction_lift", 0),
    }
    out = Path(cwd).resolve() / "security" / "benchmarks" / "runtime_dashboard.json"
    _save(out, dash)
    return {"ok": True, "path": str(out), "dashboard": dash}


def slo_monitor(cwd: str, min_runtime_score: float = 95.0) -> dict:
    runtime = zero_ai_runtime_status(cwd)
    if not runtime.get("ok", False):
        runtime = zero_ai_runtime_run(cwd)
    score = float(runtime.get("runtime_score", 0))
    ok = score >= float(min_runtime_score)
    rec = {"time_utc": _utc_now(), "runtime_score": score, "threshold": min_runtime_score, "ok": ok}
    p = _runtime(cwd) / "slo_events.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"ok": True, "slo_ok": ok, "event": rec, "path": str(p)}


def independent_validate(cwd: str) -> dict:
    runtime = zero_ai_runtime_run(cwd)
    checks = {
        "runtime_ready": bool(runtime.get("runtime_ready", False)),
        "law_proof": bool(runtime.get("universe_law_proof", {}).get("proof", "")),
        "quorum": bool(runtime.get("identity_quorum", {}).get("quorum_met", False)),
        "consensus": bool(runtime.get("distributed_consensus", {}).get("consensus", {}).get("quorum", False)),
        "observability": bool(runtime.get("observability", {}).get("enforced", False)),
    }
    out = {"ok": all(checks.values()), "checks": checks, "time_utc": _utc_now()}
    _save(_runtime(cwd) / "independent_runtime_validation.json", out)
    return out

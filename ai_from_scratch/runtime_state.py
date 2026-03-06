from __future__ import annotations

import json
from pathlib import Path


SCHEMAS = {
    "agents_monitor.json": {"schema_version": 1, "smooth": False, "score": 0.0, "checks": {}, "issues": [], "auto_mode": True},
    "agents_remediation.json": {"schema_version": 1, "trigger_score": 0.0, "trigger_smooth": False, "issues": [], "actions": [], "auto_mode": True},
    "agi_module_registry_status.json": {"schema_version": 1, "ok": False, "summary": {}, "errors": [], "warnings": []},
    "agi_advanced_layers_status.json": {"schema_version": 1, "ok": False, "summary": {}, "errors": [], "warnings": []},
    "reality_world_model.json": {
        "schema_version": 1,
        "entity_registry": [],
        "relationship_graph": [],
        "state_tracker": {"last_channel": "", "last_prompt": "", "updates": 0},
        "causal_engine": {"rules": [], "last_inference": ""},
        "history": [],
    },
    "slo_report.json": {"schema_version": 1, "ok": True, "score": 100.0, "checks": {}, "violations": []},
    "compute_runtime.json": {
        "schema_version": 1,
        "tier": "tier1",
        "profile": "low",
        "hardware": {
            "cpu_cores": 1,
            "memory_gb": 4.0,
            "gpu_count": 0,
            "distributed_ready": False,
            "quantum_ready": False,
        },
        "profiles": {},
        "scheduler": {},
    },
}


def ensure_runtime_schemas(cwd: str) -> dict:
    runtime = Path(cwd).resolve() / ".zero_os" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    updated = []
    for name, default in SCHEMAS.items():
        p = runtime / name
        if not p.exists():
            p.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
            updated.append(name)
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            p.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
            updated.append(name)
            continue
        if not isinstance(data, dict) or int(data.get("schema_version", 0)) != int(default["schema_version"]):
            merged = dict(default)
            if isinstance(data, dict):
                merged.update(data)
            merged["schema_version"] = default["schema_version"]
            p.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
            updated.append(name)
    return {"ok": True, "updated": updated}

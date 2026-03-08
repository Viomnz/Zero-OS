from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_STATUS = {"planned", "stub", "active", "tested"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _registry_path(cwd: str) -> Path:
    return Path(cwd).resolve() / "zero_os_config" / "agi_advanced_layers.json"


def load_advanced_layers(cwd: str) -> dict:
    return json.loads(_registry_path(cwd).read_text(encoding="utf-8", errors="replace"))


def validate_advanced_layers(data: dict) -> dict:
    layers = data.get("layers", [])
    expected = int(data.get("total_layers_expected", 0))
    errors: list[str] = []
    warnings: list[str] = []
    status_count: Counter[str] = Counter()
    ids: set[str] = set()

    if not isinstance(layers, list):
        return {"ok": False, "errors": ["layers must be a list"], "warnings": [], "summary": {}}

    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            errors.append(f"layers[{i}] must be object")
            continue
        lid = str(layer.get("id", "")).strip()
        name = str(layer.get("name", "")).strip()
        status = str(layer.get("status", "")).strip()
        capabilities = layer.get("capabilities", [])
        if not lid:
            errors.append(f"layers[{i}] missing id")
        elif lid in ids:
            errors.append(f"duplicate id: {lid}")
        else:
            ids.add(lid)
        if not name:
            errors.append(f"layers[{i}] missing name")
        if status not in ALLOWED_STATUS:
            errors.append(f"layers[{i}] invalid status: {status}")
        if not isinstance(capabilities, list) or len(capabilities) == 0:
            errors.append(f"{lid or f'layers[{i}]'} capabilities must be non-empty list")
        status_count[status] += 1

    if expected and len(layers) != expected:
        errors.append(f"total layer count mismatch: expected {expected}, got {len(layers)}")

    summary = {
        "total_layers": len(layers),
        "expected_layers": expected,
        "status_counts": dict(status_count),
        "coverage_percent": round(((status_count.get("active", 0) + status_count.get("tested", 0)) / max(1, len(layers))) * 100, 2),
    }
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "summary": summary}


def write_advanced_layers_status(cwd: str) -> dict:
    result = validate_advanced_layers(load_advanced_layers(cwd))
    payload = {
        "time_utc": _utc_now(),
        "ok": result["ok"],
        "summary": result["summary"],
        "errors": result["errors"],
        "warnings": result["warnings"],
    }
    (_runtime(cwd) / "agi_advanced_layers_status.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


from __future__ import annotations

import json
from collections import Counter, defaultdict
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
    return Path(cwd).resolve() / "zero_os_config" / "agi_module_registry.json"


def load_registry(cwd: str) -> dict:
    path = _registry_path(cwd)
    raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(raw, dict):
        raise ValueError("registry must be a JSON object")
    return raw


def validate_registry(data: dict) -> dict:
    modules = data.get("modules", [])
    domains = data.get("domains", [])
    expected = int(data.get("total_modules_expected", 0))

    errors: list[str] = []
    warnings: list[str] = []
    ids: set[str] = set()
    domain_expected = {d.get("key"): int(d.get("module_count_expected", 0)) for d in domains if isinstance(d, dict)}
    domain_count: dict[str, int] = defaultdict(int)
    status_count: Counter[str] = Counter()
    bindings = data.get("bindings", {})
    if not isinstance(bindings, dict):
        bindings = {}

    if not isinstance(modules, list):
        return {"ok": False, "errors": ["modules must be a list"], "warnings": [], "summary": {}}

    for i, m in enumerate(modules):
        if not isinstance(m, dict):
            errors.append(f"module[{i}] must be an object")
            continue
        mid = str(m.get("id", "")).strip()
        name = str(m.get("name", "")).strip()
        domain = str(m.get("domain", "")).strip()
        status = str(m.get("status", "")).strip()
        if not mid:
            errors.append(f"module[{i}] missing id")
        elif mid in ids:
            errors.append(f"duplicate id: {mid}")
        else:
            ids.add(mid)
        if not name:
            errors.append(f"module[{i}] missing name")
        if not domain:
            errors.append(f"module[{i}] missing domain")
        if status not in ALLOWED_STATUS:
            errors.append(f"module[{i}] invalid status: {status}")
        if domain:
            domain_count[domain] += 1
        if status:
            status_count[status] += 1
        hc = m.get("health_contract", {})
        if not isinstance(hc, dict):
            errors.append(f"{mid or f'module[{i}]'} health_contract must be object")
        else:
            for k in ("inputs", "outputs", "fail_state", "safe_state_action"):
                if k not in hc:
                    errors.append(f"{mid or f'module[{i}]'} missing health_contract.{k}")
        if status in {"active", "tested"}:
            b = bindings.get(mid)
            if not isinstance(b, dict):
                errors.append(f"{mid} missing bindings entry for active/tested module")
            else:
                if not str(b.get("impl_file", "")).strip():
                    errors.append(f"{mid} missing bindings.impl_file")
                if not str(b.get("test_file", "")).strip():
                    errors.append(f"{mid} missing bindings.test_file")

    if expected and len(modules) != expected:
        errors.append(f"total module count mismatch: expected {expected}, got {len(modules)}")

    for d, exp in domain_expected.items():
        got = domain_count.get(d, 0)
        if got != exp:
            errors.append(f"domain count mismatch for {d}: expected {exp}, got {got}")

    for d in domain_count:
        if d not in domain_expected:
            warnings.append(f"module uses undeclared domain: {d}")

    summary = {
        "total_modules": len(modules),
        "expected_modules": expected,
        "status_counts": dict(status_count),
        "domain_counts": dict(domain_count),
        "coverage_percent": round(((status_count.get("active", 0) + status_count.get("tested", 0)) / max(1, len(modules))) * 100, 2),
    }
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "summary": summary}


def write_registry_status(cwd: str) -> dict:
    data = load_registry(cwd)
    result = validate_registry(data)
    root = Path(cwd).resolve()
    bindings = data.get("bindings", {})
    impl_missing = []
    test_missing = []
    if isinstance(bindings, dict):
        for mid, b in bindings.items():
            if not isinstance(b, dict):
                continue
            impl = str(b.get("impl_file", "")).strip()
            test = str(b.get("test_file", "")).strip()
            if impl and not (root / impl).exists():
                impl_missing.append({"module_id": mid, "path": impl})
            if test and not (root / test).exists():
                test_missing.append({"module_id": mid, "path": test})
    payload = {
        "time_utc": _utc_now(),
        "ok": result["ok"] and not impl_missing and not test_missing,
        "summary": result["summary"],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "binding_checks": {
            "impl_missing_count": len(impl_missing),
            "test_missing_count": len(test_missing),
            "impl_missing": impl_missing[:200],
            "test_missing": test_missing[:200],
        },
    }
    (_runtime(cwd) / "agi_module_registry_status.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload

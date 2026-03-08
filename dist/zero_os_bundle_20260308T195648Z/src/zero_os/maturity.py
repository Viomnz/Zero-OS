from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exists(base: Path, rel: str) -> bool:
    return (base / rel).exists()


def _find_any(base: Path, patterns: list[str]) -> str:
    for pattern in patterns:
        for match in base.glob(pattern):
            if match.exists():
                return str(match)
    return ""


def maturity_status(cwd: str) -> dict:
    base = Path(cwd).resolve()
    detected_paths = {
        "threat_intel_pipeline": _find_any(base, ["security/*threat*intel*.json", "security/*feed*.json"]),
        "trust_signing_policy": _find_any(base, ["zero_os_config/*trust*policy*.json"]),
        "incident_runbooks": _find_any(base, ["docs/*SECURITY*RUNBOOK*.md"]),
        "ci_security_gates": _find_any(base, [".github/workflows/*security*.yml"]),
        "false_positive_lifecycle": _find_any(base, [".zero_os/runtime/*smart*logic*policy*.json"]),
        "performance_hardening": _find_any(base, ["tools/*benchmark*security*.py"]),
        "compatibility_matrix": _find_any(base, ["docs/*COMPATIBILITY*MATRIX*.md"]),
        "adversarial_pack": _find_any(base, ["tests/*smart_logic_governance*.py", "tests/*adversarial*.py"]),
        "release_discipline": _find_any(base, ["zero_os_config/*release*contracts*.json"]),
        "dashboard_security_views": _find_any(
            base,
            [
                "zero_os_dashboard.html",
                "zero_os_shell.html",
                "index.html",
                "ai_from_scratch/dashboard_server.py",
                "src/zero_os/native_shell_bridge.py",
            ],
        ),
    }
    checks = {
        "threat_intel_pipeline": _exists(base, "security/threat_intel_feed.json") or bool(detected_paths["threat_intel_pipeline"]),
        "trust_signing_policy": _exists(base, "zero_os_config/trust_policy.json") or bool(detected_paths["trust_signing_policy"]),
        "incident_runbooks": _exists(base, "docs/SECURITY_RUNBOOKS.md") or bool(detected_paths["incident_runbooks"]),
        "ci_security_gates": _exists(base, ".github/workflows/security-maturity.yml") or bool(detected_paths["ci_security_gates"]),
        "false_positive_lifecycle": _exists(base, ".zero_os/runtime/smart_logic_policy.json") or bool(detected_paths["false_positive_lifecycle"]),
        "performance_hardening": _exists(base, "tools/benchmark_security_stack.py") or bool(detected_paths["performance_hardening"]),
        "compatibility_matrix": _exists(base, "docs/COMPATIBILITY_MATRIX.md") or bool(detected_paths["compatibility_matrix"]),
        "adversarial_pack": _exists(base, "tests/test_smart_logic_governance.py") or bool(detected_paths["adversarial_pack"]),
        "release_discipline": _exists(base, "zero_os_config/release_contracts.json") or bool(detected_paths["release_discipline"]),
        "dashboard_security_views": (
            _exists(base, "zero_os_dashboard.html")
            or _exists(base, "zero_os_shell.html")
            or _exists(base, "ai_from_scratch/dashboard_server.py")
            or _exists(base, "src/zero_os/native_shell_bridge.py")
            or bool(detected_paths["dashboard_security_views"])
        ),
    }
    total = len(checks)
    passed = sum(1 for v in checks.values() if v)
    score = round((passed / max(1, total)) * 100, 2)
    missing = [k for k, v in checks.items() if not v]
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "score": score,
        "perfect": score == 100.0 and not missing,
        "checks": checks,
        "missing": missing,
        "next_priority": [f"create: {item}" for item in missing],
        "detected_paths": detected_paths,
        "passed": passed,
        "total": total,
    }


def maturity_scaffold_all(cwd: str) -> dict:
    base = Path(cwd).resolve()
    created: list[str] = []
    files = {
        "security/threat_intel_feed.json": {
            "version": 1,
            "updated_utc": _utc_now(),
            "providers": ["local-bootstrap"],
            "ioc_count": 0,
            "notes": "Replace with signed external provider sync.",
        },
        "zero_os_config/trust_policy.json": {
            "version": 1,
            "critical_actions_require_signature": True,
            "key_rotation_days": 30,
            "allowed_signers": ["owner"],
        },
        "docs/COMPATIBILITY_MATRIX.md": (
            "# Compatibility Matrix\n\n"
            "- Windows: supported\n"
            "- Linux: planned validation\n"
            "- macOS: planned validation\n"
            "- CPU: x64 baseline\n"
            "- Runtime: Python 3.11+\n"
        ),
        "docs/SECURITY_RUNBOOKS.md": (
            "# Security Runbooks\n\n"
            "## Critical Incident\n"
            "1. Isolate runtime\n"
            "2. Run zero ai recover\n"
            "3. Verify integrity and monitor score\n\n"
            "## False Positive Review\n"
            "1. List review queue\n"
            "2. Decide confirmed vs false_positive\n"
            "3. Update thresholds/policy if needed\n"
        ),
        ".github/workflows/security-maturity.yml": (
            "name: security-maturity\n"
            "on:\n"
            "  push:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  security:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - uses: actions/setup-python@v5\n"
            "        with:\n"
            "          python-version: '3.11'\n"
            "      - run: python -m unittest -q tests.test_smart_logic_governance tests.test_internal_zero_reasoner tests.test_zero_ai_gate\n"
        ),
        ".zero_os/runtime/smart_logic_policy.json": {
            "global": {"review_enabled": True},
            "engines": {
                "zero_ai_gate_smart_logic_v1": {"min_confidence": 0.5},
                "zero_ai_internal_smart_logic_v1": {"min_confidence": 0.55},
                "cure_firewall_smart_logic_v1": {"min_confidence": 0.6},
                "antivirus_smart_logic_v1": {"min_confidence": 0.65},
            },
        },
        "zero_os_config/release_contracts.json": {
            "version": 1,
            "contracts": [
                {"name": "smart_logic", "required_fields": ["engine", "decision_action", "decision_reason", "confidence", "root_issues"]},
                {"name": "scoring", "required_fields": ["score", "perfect", "issues"]},
            ],
        },
    }
    for rel, payload in files.items():
        p = base / rel
        if p.exists():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, str):
            p.write_text(payload, encoding="utf-8")
        else:
            p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        created.append(rel)
    return {"ok": True, "created": created, "created_count": len(created), "status": maturity_status(cwd)}

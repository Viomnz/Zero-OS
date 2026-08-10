from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from zero_os.security_pressure_cases import SecurityPressureResult


def summarize_security_survival(results: Iterable[SecurityPressureResult]) -> dict[str, Any]:
    rows = list(results)
    passed = [row for row in rows if row.mechanism_passed]
    scope_certified = [row for row in rows if row.scope_certified]
    unresolved = sorted({scope for row in rows for scope in row.unresolved_scope})
    failed_controls = sorted({control for row in rows for control in row.missing_controls})
    demonstrated = sorted({scope for row in passed for scope in row.demonstrated_scope})

    return {
        "case_count": len(rows),
        "mechanism_pass_count": len(passed),
        "mechanism_pass_rate": (len(passed) / len(rows)) if rows else 0.0,
        "scope_certified_count": len(scope_certified),
        "general_security_claim_permitted": False,
        "demonstrated_scope": demonstrated,
        "unresolved_scope": unresolved,
        "missing_controls": failed_controls,
        "results": [asdict(row) for row in rows],
        "pure_logic_note": (
            "Passing known cases is evidence only for their demonstrated scope; "
            "it does not certify the attack family or cybersecurity in general."
        ),
    }

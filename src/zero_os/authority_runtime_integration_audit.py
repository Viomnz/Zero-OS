from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class IntegrationRequirement:
    requirement_id: str
    path: str
    required_symbols: tuple[str, ...]
    satisfied: bool
    missing_symbols: tuple[str, ...]
    consequence: str

    def to_dict(self) -> dict:
        return asdict(self)


_REQUIREMENTS = (
    (
        "mutation_ticket_requires_constitution",
        "src/zero_os/final_action_authority.py",
        ("constitutional_decide", "constitutional_request", "objective_ledger", "verification_budget"),
        "critical",
    ),
    (
        "main_executor_uses_constitution",
        "src/zero_os/unified_action_engine.py",
        ("pure_logic_authority_kernel", "ConstitutionalRequest"),
        "critical",
    ),
    (
        "self_repair_uses_correction_plane",
        "src/zero_os/self_repair.py",
        ("protected_correction_plane", "independent_outcome_verifier"),
        "critical",
    ),
    (
        "source_evolution_uses_architecture_promotion",
        "src/zero_os/zero_ai_source_evolution.py",
        ("architecture_promotion_authority", "protected_correction_plane"),
        "critical",
    ),
    (
        "world_model_projects_to_reality_ledger",
        "src/zero_os/world_model.py",
        ("reality_ledger",),
        "high",
    ),
    (
        "memory_declares_non_authority",
        "src/zero_os/memory_tier_filter.py",
        ("memory_is_not_authority",),
        "high",
    ),
)


def _normalized_source(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        ast.parse(text)
    except (OSError, SyntaxError):
        return ""
    return text


def audit_authority_runtime_integration(root: str | Path) -> dict:
    base = Path(root).resolve()
    results: list[IntegrationRequirement] = []
    for requirement_id, relative_path, required_symbols, consequence in _REQUIREMENTS:
        source = _normalized_source(base / relative_path)
        missing = tuple(symbol for symbol in required_symbols if symbol not in source)
        results.append(
            IntegrationRequirement(
                requirement_id=requirement_id,
                path=relative_path,
                required_symbols=tuple(required_symbols),
                satisfied=bool(source) and not missing,
                missing_symbols=missing,
                consequence=consequence,
            )
        )

    critical_failures = [item for item in results if not item.satisfied and item.consequence == "critical"]
    high_failures = [item for item in results if not item.satisfied and item.consequence == "high"]
    satisfied = [item for item in results if item.satisfied]
    total = len(results)
    coverage = len(satisfied) / total if total else 0.0
    return {
        "status": "INTEGRATED_IN_IDENTIFIED_STATIC_SCOPE" if not critical_failures and not high_failures else "BLOCK_PROMOTION",
        "requirement_count": total,
        "satisfied_count": len(satisfied),
        "integration_coverage": coverage,
        "critical_failure_count": len(critical_failures),
        "high_failure_count": len(high_failures),
        "promotion_permitted": not critical_failures and not high_failures,
        "requirements": [item.to_dict() for item in results],
        "limitations": [
            "symbol_presence_is_not_runtime_reachability_proof",
            "dynamic_dispatch_not_certified",
            "native_code_not_certified",
            "test_execution_required",
            "fresh_adversarial_audit_required",
        ],
    }

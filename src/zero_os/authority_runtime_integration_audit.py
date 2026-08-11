from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class IntegrationRequirement:
    requirement_id: str
    path: str
    required_calls: tuple[str, ...]
    required_assignments: tuple[str, ...]
    satisfied: bool
    missing_calls: tuple[str, ...]
    missing_assignments: tuple[str, ...]
    consequence: str

    def to_dict(self) -> dict:
        return asdict(self)


_REQUIREMENTS = (
    ("mutation_ticket_requires_constitution_and_issuer", "src/zero_os/final_action_authority.py", ("constitutional_decide", "issue_attestation", "ticket_from_attestation"), (), "critical"),
    ("main_executor_calls_authority_policy", "src/zero_os/unified_action_engine.py", ("classify_action",), (), "critical"),
    ("authority_policy_checks_runtime_authority", "src/zero_os/agent_permission_policy.py", ("authorize_runtime_mutation", "current_capability_lease"), (), "critical"),
    ("capability_gateway_requires_constitution_and_issuer", "src/zero_os/capability_execution_gateway.py", ("constitutional_decide", "issue_attestation", "lease_from_attestation"), (), "critical"),
    ("self_repair_requires_ticket_handoff_and_outcome", "src/zero_os/self_repair.py", ("acknowledge_consumed_execution_ticket", "verify_outcome"), (), "critical"),
    ("source_evolution_requires_correction_and_promotion", "src/zero_os/zero_ai_source_evolution.py", ("acknowledge_consumed_execution_ticket", "evaluate_architecture_promotion", "verify_outcome"), (), "critical"),
    ("governor_projects_world_model_to_reality_ledger", "src/zero_os/decision_governor.py", ("project_world_model_to_reality_ledger",), (), "high"),
    ("memory_declares_non_authority", "src/zero_os/memory_tier_filter.py", (), ("memory_is_not_authority",), "high"),
)


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _analyze(path: Path) -> tuple[set[str], set[str], bool]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return set(), set(), False
    calls: set[str] = set()
    assignments: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name:
                calls.add(name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assignments.add(target.id)
    return calls, assignments, True


def audit_authority_runtime_integration(root: str | Path) -> dict:
    base = Path(root).resolve()
    results: list[IntegrationRequirement] = []
    for requirement_id, relative_path, required_calls, required_assignments, consequence in _REQUIREMENTS:
        calls, assignments, parsed = _analyze(base / relative_path)
        missing_calls = tuple(name for name in required_calls if name not in calls)
        missing_assignments = tuple(name for name in required_assignments if name not in assignments)
        results.append(
            IntegrationRequirement(
                requirement_id=requirement_id,
                path=relative_path,
                required_calls=tuple(required_calls),
                required_assignments=tuple(required_assignments),
                satisfied=parsed and not missing_calls and not missing_assignments,
                missing_calls=missing_calls,
                missing_assignments=missing_assignments,
                consequence=consequence,
            )
        )
    critical_failures = [item for item in results if not item.satisfied and item.consequence == "critical"]
    high_failures = [item for item in results if not item.satisfied and item.consequence == "high"]
    satisfied = [item for item in results if item.satisfied]
    total = len(results)
    return {
        "status": "CAUSAL_CALLS_PRESENT_IN_IDENTIFIED_STATIC_SCOPE" if not critical_failures and not high_failures else "BLOCK_PROMOTION",
        "requirement_count": total,
        "satisfied_count": len(satisfied),
        "integration_coverage": (len(satisfied) / total) if total else 0.0,
        "critical_failure_count": len(critical_failures),
        "high_failure_count": len(high_failures),
        "promotion_permitted": not critical_failures and not high_failures,
        "requirements": [item.to_dict() for item in results],
        "evidence_kind": "AST_CALL_EDGE_PRESENCE",
        "limitations": [
            "call_presence_is_stronger_than_symbol_presence_but_not_full_reachability_proof",
            "branch_conditions_and_dynamic_dispatch_not_certified",
            "native_and_non_python_paths_not_certified",
            "runtime_trace_attestation_still_required",
            "test_execution_required",
            "fresh_adversarial_audit_required",
        ],
    }

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
    ("mutation_ticket_requires_constitution_and_root_issuer", "src/zero_os/final_action_authority.py", ("constitutional_decide", "issue_attestation_from_constitution", "ticket_from_attestation"), (), "critical"),
    ("main_executor_calls_authority_policy", "src/zero_os/unified_action_engine.py", ("classify_action",), (), "critical"),
    ("authority_policy_checks_runtime_and_attestation", "src/zero_os/agent_permission_policy.py", ("authorize_runtime_mutation", "current_capability_lease", "verify_attestation"), (), "critical"),
    ("capability_gateway_requires_constitution_and_root_issuer", "src/zero_os/capability_execution_gateway.py", ("constitutional_decide", "issue_attestation_from_constitution", "lease_from_attestation"), (), "critical"),
    ("ticket_consumer_verifies_root_attestation", "src/zero_os/execution_authority_ticket.py", ("verify_attestation",), (), "critical"),
    ("security_control_mutation_requires_ticket_handoff", "src/zero_os/security_control_plane.py", ("acknowledge_consumed_execution_ticket",), (), "critical"),
    ("security_feed_signing_uses_control_plane_key", "src/zero_os/security_signing.py", ("control_key", "load_state"), (), "critical"),
    ("authority_runtime_trace_has_chain_and_scope_certifier", "src/zero_os/authority_runtime_trace.py", ("record_event", "verify_trace_chain", "certify_authority_trace"), (), "critical"),
    ("self_repair_requires_ticket_handoff_and_outcome", "src/zero_os/self_repair.py", ("acknowledge_consumed_execution_ticket", "verify_outcome"), (), "critical"),
    ("source_evolution_requires_correction_and_promotion", "src/zero_os/zero_ai_source_evolution.py", ("acknowledge_consumed_execution_ticket", "evaluate_architecture_promotion", "verify_outcome"), (), "critical"),
    ("governor_projects_world_model_to_reality_ledger", "src/zero_os/decision_governor.py", ("project_world_model_to_reality_ledger",), (), "high"),
    ("memory_declares_non_authority", "src/zero_os/memory_tier_filter.py", (), ("memory_is_not_authority",), "high"),
)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _analyze(path: Path) -> tuple[set[str], set[str], bool]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
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
        missing_calls = tuple(x for x in required_calls if x not in calls)
        missing_assignments = tuple(x for x in required_assignments if x not in assignments)
        results.append(
            IntegrationRequirement(
                requirement_id,
                relative_path,
                tuple(required_calls),
                tuple(required_assignments),
                parsed and not missing_calls and not missing_assignments,
                missing_calls,
                missing_assignments,
                consequence,
            )
        )
    critical = [x for x in results if not x.satisfied and x.consequence == "critical"]
    high = [x for x in results if not x.satisfied and x.consequence == "high"]
    satisfied = [x for x in results if x.satisfied]
    total = len(results)
    return {
        "status": "CAUSAL_CALLS_PRESENT_IN_IDENTIFIED_STATIC_SCOPE" if not critical and not high else "BLOCK_PROMOTION",
        "requirement_count": total,
        "satisfied_count": len(satisfied),
        "integration_coverage": len(satisfied) / total if total else 0.0,
        "critical_failure_count": len(critical),
        "high_failure_count": len(high),
        "promotion_permitted": not critical and not high,
        "requirements": [x.to_dict() for x in results],
        "evidence_kind": "AST_CALL_EDGE_PRESENCE",
        "limitations": [
            "call_presence_is_not_full_reachability_proof",
            "security_control_plane_not_yet_all_legacy_call_sites",
            "branch_conditions_and_dynamic_dispatch_not_certified",
            "native_and_non_python_paths_not_certified",
            "runtime_trace_attestation_required_for_promotion",
            "test_execution_required",
            "fresh_adversarial_audit_required",
        ],
    }

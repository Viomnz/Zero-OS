from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoopIntegrationFinding:
    path: str
    line: int
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


_REQUIRED_SURFACES = (
    "src/zero_os/autonomous_runtime_ecosystem.py",
    "src/zero_os/self_repair.py",
    "src/zero_os/zero_ai_source_evolution.py",
    "src/zero_os/zero_ai_autonomy.py",
    "src/zero_os/general_agent_orchestrator.py",
    "src/zero_os/zero_ai_control_workflows.py",
)

_LOOP_AUTHORITY_CALLS = {"authorize_control_step", "observe_control_outcome"}
_AUTHORITY_MINTING_CALLS = {
    "issue_attestation_from_constitution",
    "ticket_from_attestation",
    "lease_from_attestation",
    "issue_execution_ticket",
    "issue_capability_lease",
}


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _calls(tree: ast.AST) -> set[str]:
    return {_call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}


def _source_contains_assign_true(tree: ast.AST, names: set[str]) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Constant) or value.value is not True:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ""
            if name in names:
                findings.append((int(getattr(node, "lineno", 0)), name))
    return findings


def audit_control_loop_integration(root: str | Path) -> dict:
    base = Path(root).resolve()
    findings: list[LoopIntegrationFinding] = []
    integrated: list[str] = []
    missing: list[str] = []

    for rel in _REQUIRED_SURFACES:
        path = base / rel
        if not path.exists():
            missing.append(rel)
            findings.append(LoopIntegrationFinding(rel, 0, "required_autonomous_surface_missing_from_audit_scope"))
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            findings.append(LoopIntegrationFinding(rel, 0, "autonomous_surface_unparseable"))
            continue
        calls = _calls(tree)
        if not _LOOP_AUTHORITY_CALLS.intersection(calls):
            findings.append(LoopIntegrationFinding(rel, 0, "autonomous_surface_not_control_loop_authority_integrated"))
        else:
            integrated.append(rel)

    kernel = base / "src/zero_os/pure_logic_control_loop.py"
    if not kernel.exists():
        findings.append(LoopIntegrationFinding(str(kernel.relative_to(base)), 0, "control_loop_authority_contract_missing"))
    else:
        try:
            tree = ast.parse(kernel.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node) in _AUTHORITY_MINTING_CALLS:
                    findings.append(LoopIntegrationFinding(
                        str(kernel.relative_to(base)),
                        int(getattr(node, "lineno", 0)),
                        "control_loop_kernel_must_not_mint_final_authority",
                    ))
        except (OSError, SyntaxError):
            findings.append(LoopIntegrationFinding(str(kernel.relative_to(base)), 0, "control_loop_kernel_unparseable"))

    # Constitutional authority must recompute controller eligibility from raw
    # evidence. Caller-supplied booleans are prohibited because they are forgeable.
    constitution = base / "src/zero_os/pure_logic_authority_kernel.py"
    if not constitution.exists():
        findings.append(LoopIntegrationFinding(str(constitution.relative_to(base)), 0, "constitutional_authority_kernel_missing"))
    else:
        try:
            tree = ast.parse(constitution.read_text(encoding="utf-8", errors="replace"))
            text = constitution.read_text(encoding="utf-8", errors="replace")
            if "ControllerEvidence" not in text or "authorize_control_step" not in _calls(tree):
                findings.append(LoopIntegrationFinding(str(constitution.relative_to(base)), 0, "constitutional_layer_not_recomputing_controller_evidence"))
            for forbidden in ("controller_eligible", "execution_authority_granted"):
                if forbidden in text:
                    findings.append(LoopIntegrationFinding(str(constitution.relative_to(base)), 0, f"self_asserted_controller_authority_field_present:{forbidden}"))
        except (OSError, SyntaxError):
            findings.append(LoopIntegrationFinding(str(constitution.relative_to(base)), 0, "constitutional_authority_kernel_unparseable"))

    # Conflict arbitration may veto/serialize/escalate, never grant or select
    # final authority between competing controllers.
    arbiter = base / "src/zero_os/control_loop_conflict_arbiter.py"
    if not arbiter.exists():
        findings.append(LoopIntegrationFinding(str(arbiter.relative_to(base)), 0, "controller_conflict_arbiter_missing"))
    else:
        try:
            tree = ast.parse(arbiter.read_text(encoding="utf-8", errors="replace"))
            for line, name in _source_contains_assign_true(tree, {"authority_granted"}):
                findings.append(LoopIntegrationFinding(str(arbiter.relative_to(base)), line, f"conflict_arbiter_attempted_authority_grant:{name}"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node) in _AUTHORITY_MINTING_CALLS:
                    findings.append(LoopIntegrationFinding(str(arbiter.relative_to(base)), int(getattr(node, "lineno", 0)), "conflict_arbiter_must_not_mint_authority"))
        except (OSError, SyntaxError):
            findings.append(LoopIntegrationFinding(str(arbiter.relative_to(base)), 0, "controller_conflict_arbiter_unparseable"))

    return {
        "ok": not findings,
        "promotion_permitted": not findings,
        "status": "CONTROL_LOOP_AUTHORITY_INTEGRATED_IN_IDENTIFIED_SCOPE" if not findings else "BLOCK_PROMOTION",
        "required_surface_count": len(_REQUIRED_SURFACES),
        "integrated_surface_count": len(integrated),
        "integrated_surfaces": integrated,
        "missing_surfaces": missing,
        "finding_count": len(findings),
        "findings": [item.to_dict() for item in findings],
        "invariants": [
            "command_is_not_outcome",
            "feedback_source_is_not_truth",
            "controller_authority_is_revocable",
            "oscillation_requires_investigation",
            "latency_window_prevents_premature_recorrection",
            "requested_executed_observed_are_separate_claims",
            "controller_cannot_self_verify_outcome",
            "uncertainty_cannot_expand_irreversible_authority",
            "path_logic_does_not_mint_authority",
            "controller_eligibility_is_recomputed_by_final_authority",
            "conflict_arbiter_can_only_block_serialize_or_escalate",
        ],
        "limitations": [
            "static_surface_inventory_is_not_complete_runtime_reachability_proof",
            "native_and_non_python_controllers_require_separate_integration",
            "real_sensor_independence_requires_deployment_evidence",
            "conflict_arbiter_requires_runtime_scheduler_integration_before_system_claim",
        ],
    }

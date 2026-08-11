from __future__ import annotations

from zero_os.composition_pressure_gate import AuthorizedPart, CompositionRequest, evaluate_composition
from zero_os.relational_authority import (
    RelationAuthorityContract,
    RelationAuthorityState,
    RelationEvidence,
    RelationSubject,
)


_DOMAINS = (
    "science",
    "control",
    "cybersecurity",
    "software",
    "autonomous_agents",
    "self_improvement",
)


def _relation(domain: str, *, joint_ok: bool = True, contradicted: bool = False) -> RelationAuthorityContract:
    joint = f"{domain}:joint_state"
    return RelationAuthorityContract(
        relation=RelationSubject(
            relation_id=f"{domain}:composition",
            member_ids=(f"{domain}:A", f"{domain}:B"),
            relation_kind="interaction",
            state_revision="r1",
            requested_joint_state=joint,
        ),
        state=RelationAuthorityState.PROVISIONAL,
        demonstrated_joint_scope=(joint,),
        evidence=(
            RelationEvidence(
                evidence_id=f"{domain}:sim",
                provenance="independent_simulation",
                method_family="simulation",
                lineage="sim-lineage",
                demonstrated_joint_states=(joint,),
                joint_invariants_passed=joint_ok,
                interaction_model_available=True,
                independently_generated=True,
                contradicted=contradicted,
            ),
            RelationEvidence(
                evidence_id=f"{domain}:probe",
                provenance="independent_probe",
                method_family="empirical_probe",
                lineage="probe-lineage",
                demonstrated_joint_states=(joint,),
                joint_invariants_passed=joint_ok,
                interaction_model_available=True,
                independently_generated=True,
                contradicted=False,
            ),
        ),
        revocation_conditions=("joint_invariant_failure", "relation_evidence_contradicted"),
        parent_authority_ids=(f"{domain}:authA", f"{domain}:authB"),
    )


def _request(domain: str, relation: RelationAuthorityContract | None) -> CompositionRequest:
    joint = f"{domain}:joint_state"
    return CompositionRequest(
        composition_id=f"{domain}:composition",
        parts=(
            AuthorizedPart(f"{domain}:A", f"{domain}:authA", (f"{domain}:localA",), True, "r1"),
            AuthorizedPart(f"{domain}:B", f"{domain}:authB", (f"{domain}:localB",), True, "r1"),
        ),
        requested_joint_state=joint,
        certified_joint_states=(joint,),
        joint_invariants_passed=True,
        interaction_model_available=True,
        reversible=True,
        uncertainty=0.1,
        relation_authority=relation,
    )


def run_relational_generality_pressure() -> dict:
    results: list[dict] = []
    for domain in _DOMAINS:
        missing = evaluate_composition(_request(domain, None))
        survived = evaluate_composition(_request(domain, _relation(domain)))
        contradicted = evaluate_composition(_request(domain, _relation(domain, contradicted=True)))
        results.append({
            "domain": domain,
            "local_parts_alone_clear": missing.eligible_to_continue_authority_evaluation,
            "relational_authority_clear": survived.eligible_to_continue_authority_evaluation,
            "contradicted_relation_clear": contradicted.eligible_to_continue_authority_evaluation,
            "missing_relation_reasons": missing.reasons,
            "contradicted_relation_reasons": contradicted.reasons,
        })

    all_require_relation = all(not row["local_parts_alone_clear"] for row in results)
    all_survive_with_relation = all(row["relational_authority_clear"] for row in results)
    all_revoke_on_contradiction = all(not row["contradicted_relation_clear"] for row in results)
    derived = all_require_relation and all_survive_with_relation and all_revoke_on_contradiction

    return {
        "domains": tuple(_DOMAINS),
        "results": tuple(results),
        "relation_as_first_class_subject_repeated_across_domains": derived,
        "composition_requires_seventh_master_law": False if derived else None,
        "candidate_interpretation": (
            "composition pressure is currently explained by a representation gap: relations and joint states were not first-class authority subjects"
            if derived else
            "relational-authority derivation incomplete; preserve composition as unresolved candidate"
        ),
        "master_law_change_justified": False,
        "external_validation_required": True,
        "pure_logic_self_certification_permitted": False,
    }

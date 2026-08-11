from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RelationAuthorityState(str, Enum):
    UNTESTED = "UNTESTED"
    PROVISIONAL = "PROVISIONAL"
    SURVIVED_IN_SCOPE = "SURVIVED_IN_SCOPE"
    RESTRICTED = "RESTRICTED"
    CONTESTED = "CONTESTED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    HISTORICAL = "HISTORICAL"


@dataclass(frozen=True)
class RelationSubject:
    relation_id: str
    member_ids: tuple[str, ...]
    relation_kind: str
    state_revision: str
    requested_joint_state: str


@dataclass(frozen=True)
class RelationEvidence:
    evidence_id: str
    provenance: str
    method_family: str
    lineage: str
    demonstrated_joint_states: tuple[str, ...]
    joint_invariants_passed: bool
    interaction_model_available: bool
    independently_generated: bool
    contradicted: bool = False


@dataclass(frozen=True)
class RelationAuthorityContract:
    relation: RelationSubject
    state: RelationAuthorityState
    demonstrated_joint_scope: tuple[str, ...]
    evidence: tuple[RelationEvidence, ...] = field(default_factory=tuple)
    expires_at_utc: str = ""
    revocation_conditions: tuple[str, ...] = field(default_factory=tuple)
    parent_authority_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RelationAuthorityDecision:
    survived: bool
    state: RelationAuthorityState
    reasons: tuple[str, ...]
    independent_evidence_groups: int
    demonstrated_joint_scope: tuple[str, ...]
    final_authority_granted: bool = False
    path_logic_final_authority: bool = False


def evaluate_relation_authority(contract: RelationAuthorityContract) -> RelationAuthorityDecision:
    reasons: list[str] = []
    relation = contract.relation

    if len(set(relation.member_ids)) < 2:
        reasons.append("relation_requires_multiple_distinct_members")
    if not relation.relation_id:
        reasons.append("relation_identity_missing")
    if not relation.state_revision:
        reasons.append("relation_state_revision_missing")
    if not relation.requested_joint_state:
        reasons.append("requested_joint_state_missing")
    if contract.state in {RelationAuthorityState.REVOKED, RelationAuthorityState.SUPERSEDED, RelationAuthorityState.HISTORICAL}:
        reasons.append("relation_authority_not_active")

    usable = [row for row in contract.evidence if not row.contradicted]
    if not usable:
        reasons.append("relation_evidence_missing")

    if usable and not all(row.interaction_model_available for row in usable):
        reasons.append("interaction_model_missing")
    if usable and not all(row.joint_invariants_passed for row in usable):
        reasons.append("joint_invariants_not_survived")

    demonstrated = set(contract.demonstrated_joint_scope)
    if relation.requested_joint_state not in demonstrated:
        reasons.append("requested_joint_state_outside_relation_scope")

    groups = {
        (row.method_family, row.lineage)
        for row in usable
        if row.independently_generated and row.method_family and row.lineage
    }
    if len(groups) < 2:
        reasons.append("insufficient_independent_relation_evidence")

    if any(row.contradicted for row in contract.evidence):
        reasons.append("relation_evidence_contradicted")

    if reasons:
        if "joint_invariants_not_survived" in reasons or "relation_evidence_contradicted" in reasons:
            state = RelationAuthorityState.CONTESTED
        else:
            state = RelationAuthorityState.RESTRICTED
    else:
        state = RelationAuthorityState.SURVIVED_IN_SCOPE

    return RelationAuthorityDecision(
        survived=not reasons,
        state=state,
        reasons=tuple(reasons),
        independent_evidence_groups=len(groups),
        demonstrated_joint_scope=tuple(contract.demonstrated_joint_scope),
        final_authority_granted=False,
        path_logic_final_authority=False,
    )


def relational_authority_invariants() -> tuple[str, ...]:
    return (
        "relations_and_joint_states_are_first_class_authority_subjects",
        "authority_over_members_does_not_imply_authority_over_relation",
        "relation_authority_is_scoped_revocable_and_non_final",
        "joint_scope_requires_independent_interaction_evidence",
        "path_logic_cannot_create_relation_authority",
        "composition_pressure_is_tested_before_final_execution_authority",
    )

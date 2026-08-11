from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class GraphAuthorityState(str, Enum):
    UNTESTED = "UNTESTED"
    PROVISIONAL = "PROVISIONAL"
    SURVIVED_IN_SCOPE = "SURVIVED_IN_SCOPE"
    RESTRICTED = "RESTRICTED"
    CONTESTED = "CONTESTED"
    REVOKED = "REVOKED"
    HISTORICAL = "HISTORICAL"


@dataclass(frozen=True)
class AuthorityNode:
    node_id: str
    subject_type: str
    authority_id: str
    state: GraphAuthorityState
    demonstrated_scope: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    contradiction_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthorityHyperedge:
    edge_id: str
    member_node_ids: tuple[str, ...]
    relation_kind: str
    authority_id: str
    state: GraphAuthorityState
    demonstrated_joint_scope: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    parent_authority_ids: tuple[str, ...] = ()
    contradiction_ids: tuple[str, ...] = ()
    revocation_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class JointState:
    joint_state_id: str
    member_node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    requested_scope: tuple[str, ...]
    invariants_passed: bool
    independent_evidence_groups: tuple[str, ...]
    uncertainty: float = 1.0
    reversible: bool = True


@dataclass(frozen=True)
class GraphDecision:
    eligible_to_continue_authority_evaluation: bool
    state: GraphAuthorityState
    reasons: tuple[str, ...]
    affected_authority_ids: tuple[str, ...]
    final_authority_granted: bool = False
    path_logic_final_authority: bool = False


def _active(state: GraphAuthorityState) -> bool:
    return state in {
        GraphAuthorityState.PROVISIONAL,
        GraphAuthorityState.SURVIVED_IN_SCOPE,
        GraphAuthorityState.RESTRICTED,
    }


def evaluate_joint_state(
    nodes: Iterable[AuthorityNode],
    edges: Iterable[AuthorityHyperedge],
    joint: JointState,
) -> GraphDecision:
    node_map = {node.node_id: node for node in nodes}
    edge_map = {edge.edge_id: edge for edge in edges}
    reasons: list[str] = []
    affected: set[str] = set()

    for node_id in joint.member_node_ids:
        node = node_map.get(node_id)
        if node is None:
            reasons.append(f"joint_member_missing:{node_id}")
            continue
        affected.add(node.authority_id)
        if not _active(node.state):
            reasons.append(f"joint_member_authority_not_active:{node_id}")
        if node.contradiction_ids:
            reasons.append(f"joint_member_contested:{node_id}")

    for edge_id in joint.edge_ids:
        edge = edge_map.get(edge_id)
        if edge is None:
            reasons.append(f"joint_edge_missing:{edge_id}")
            continue
        affected.add(edge.authority_id)
        if not _active(edge.state):
            reasons.append(f"relation_authority_not_active:{edge_id}")
        if edge.contradiction_ids:
            reasons.append(f"relation_contested:{edge_id}")
        if not set(joint.requested_scope).issubset(set(edge.demonstrated_joint_scope)):
            reasons.append(f"joint_scope_not_demonstrated:{edge_id}")

    if not joint.edge_ids and len(joint.member_node_ids) > 1:
        reasons.append("multi_subject_joint_state_without_relational_authority")
    if not joint.invariants_passed:
        reasons.append("joint_invariants_failed")
    if len(set(joint.independent_evidence_groups)) < 2:
        reasons.append("joint_independent_evidence_insufficient")
    if not joint.reversible and float(joint.uncertainty) > 0.2:
        reasons.append("irreversible_joint_state_under_excess_uncertainty")

    if any("failed" in reason or "irreversible" in reason for reason in reasons):
        state = GraphAuthorityState.REVOKED
    elif reasons:
        state = GraphAuthorityState.CONTESTED
    else:
        state = GraphAuthorityState.SURVIVED_IN_SCOPE

    return GraphDecision(
        eligible_to_continue_authority_evaluation=not reasons,
        state=state,
        reasons=tuple(reasons),
        affected_authority_ids=tuple(sorted(affected)),
        final_authority_granted=False,
        path_logic_final_authority=False,
    )


def propagate_revocation(
    edges: Iterable[AuthorityHyperedge],
    revoked_authority_ids: Iterable[str],
) -> tuple[str, ...]:
    revoked = set(revoked_authority_ids)
    changed = True
    while changed:
        changed = False
        for edge in edges:
            if edge.authority_id in revoked:
                continue
            if revoked.intersection(edge.parent_authority_ids):
                revoked.add(edge.authority_id)
                changed = True
    return tuple(sorted(revoked))


def graph_invariants() -> tuple[str, ...]:
    return (
        "objects_relations_and_joint_states_are_distinct_authority_subjects",
        "local_authority_never_implies_relational_or_joint_authority",
        "parent_revocation_propagates_through_relational_authority",
        "contradicted_edges_contest_joint_states_even_when_nodes_survive",
        "joint_scope_must_be_demonstrated_not_inferred_from_member_scope",
        "graph_analysis_may_block_but_never_grant_final_authority",
        "path_logic_remains_downstream_of_graph_authority",
    )

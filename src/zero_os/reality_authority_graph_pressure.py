from __future__ import annotations

from zero_os.reality_authority_graph import (
    AuthorityHyperedge,
    AuthorityNode,
    GraphAuthorityState,
    JointState,
    evaluate_joint_state,
    propagate_revocation,
)


def _node(node_id: str, authority_id: str) -> AuthorityNode:
    return AuthorityNode(
        node_id=node_id,
        subject_type="component",
        authority_id=authority_id,
        state=GraphAuthorityState.SURVIVED_IN_SCOPE,
        demonstrated_scope=("local",),
        provenance=("independent-test",),
    )


def run_graph_pressure() -> dict:
    a = _node("a", "auth:a")
    b = _node("b", "auth:b")
    relation = AuthorityHyperedge(
        edge_id="a-b",
        member_node_ids=("a", "b"),
        relation_kind="composition",
        authority_id="auth:rel:a-b",
        state=GraphAuthorityState.SURVIVED_IN_SCOPE,
        demonstrated_joint_scope=("joint:read",),
        provenance=("interaction-test",),
        parent_authority_ids=("auth:a", "auth:b"),
    )

    cases: dict[str, dict] = {}

    missing_relation = evaluate_joint_state(
        (a, b),
        (),
        JointState("missing-relation", ("a", "b"), (), ("joint:read",), True, ("v1", "v2"), 0.1, True),
    )
    cases["local_parts_without_relation"] = {
        "passed": not missing_relation.eligible_to_continue_authority_evaluation,
        "reasons": missing_relation.reasons,
    }

    valid = evaluate_joint_state(
        (a, b),
        (relation,),
        JointState("valid", ("a", "b"), ("a-b",), ("joint:read",), True, ("v1", "v2"), 0.1, True),
    )
    cases["relational_authority_survives"] = {
        "passed": valid.eligible_to_continue_authority_evaluation,
        "reasons": valid.reasons,
    }

    bad_scope = evaluate_joint_state(
        (a, b),
        (relation,),
        JointState("bad-scope", ("a", "b"), ("a-b",), ("joint:write",), True, ("v1", "v2"), 0.1, True),
    )
    cases["member_scope_cannot_expand_joint_scope"] = {
        "passed": not bad_scope.eligible_to_continue_authority_evaluation,
        "reasons": bad_scope.reasons,
    }

    contradicted_relation = AuthorityHyperedge(
        **{**relation.__dict__, "contradiction_ids": ("c1",)}
    )
    contested = evaluate_joint_state(
        (a, b),
        (contradicted_relation,),
        JointState("contested", ("a", "b"), ("a-b",), ("joint:read",), True, ("v1", "v2"), 0.1, True),
    )
    cases["edge_contradiction_defeats_local_success"] = {
        "passed": not contested.eligible_to_continue_authority_evaluation,
        "reasons": contested.reasons,
    }

    propagated = propagate_revocation((relation,), ("auth:a",))
    cases["parent_revocation_propagates"] = {
        "passed": "auth:rel:a-b" in propagated,
        "revoked": propagated,
    }

    irreversible = evaluate_joint_state(
        (a, b),
        (relation,),
        JointState("irreversible", ("a", "b"), ("a-b",), ("joint:read",), True, ("v1", "v2"), 0.8, False),
    )
    cases["uncertainty_limits_irreversible_joint_authority"] = {
        "passed": not irreversible.eligible_to_continue_authority_evaluation,
        "reasons": irreversible.reasons,
    }

    return {
        "case_count": len(cases),
        "cases": cases,
        "passed_count": sum(1 for case in cases.values() if case["passed"]),
        "all_passed": all(case["passed"] for case in cases.values()),
        "final_authority_granted": False,
        "interpretation": "graph pressure tests whether relation-first authority catches joint failures without adding a Master Law",
    }

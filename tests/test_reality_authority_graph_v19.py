from zero_os.reality_authority_graph import (
    AuthorityHyperedge,
    AuthorityNode,
    GraphAuthorityState,
    JointState,
    evaluate_joint_state,
    propagate_revocation,
)
from zero_os.reality_authority_graph_pressure import run_graph_pressure


def test_graph_pressure_suite_passes():
    report = run_graph_pressure()
    assert report["all_passed"] is True
    assert report["final_authority_granted"] is False


def test_three_party_hyperedge_is_first_class():
    nodes = tuple(
        AuthorityNode(
            node_id=name,
            subject_type="agent",
            authority_id=f"auth:{name}",
            state=GraphAuthorityState.SURVIVED_IN_SCOPE,
            demonstrated_scope=("local",),
            provenance=("test",),
        )
        for name in ("a", "b", "c")
    )
    edge = AuthorityHyperedge(
        edge_id="abc",
        member_node_ids=("a", "b", "c"),
        relation_kind="three_party_joint_action",
        authority_id="auth:abc",
        state=GraphAuthorityState.SURVIVED_IN_SCOPE,
        demonstrated_joint_scope=("joint:commit",),
        provenance=("three-party-pressure",),
        parent_authority_ids=("auth:a", "auth:b", "auth:c"),
    )
    decision = evaluate_joint_state(
        nodes,
        (edge,),
        JointState(
            joint_state_id="abc-state",
            member_node_ids=("a", "b", "c"),
            edge_ids=("abc",),
            requested_scope=("joint:commit",),
            invariants_passed=True,
            independent_evidence_groups=("v1", "v2"),
            uncertainty=0.1,
            reversible=True,
        ),
    )
    assert decision.eligible_to_continue_authority_evaluation is True
    assert decision.final_authority_granted is False


def test_relation_revocation_propagates_from_parent():
    edge = AuthorityHyperedge(
        edge_id="ab",
        member_node_ids=("a", "b"),
        relation_kind="composition",
        authority_id="auth:ab",
        state=GraphAuthorityState.SURVIVED_IN_SCOPE,
        demonstrated_joint_scope=("joint",),
        parent_authority_ids=("auth:a", "auth:b"),
    )
    revoked = propagate_revocation((edge,), ("auth:a",))
    assert "auth:ab" in revoked

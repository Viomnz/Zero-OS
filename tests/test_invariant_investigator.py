from zero_os.code_reality_graph import CodeEdge, CodeNode, CodeRealityGraph
from zero_os.invariant_investigator import Invariant, investigate_invariant


def _graph() -> CodeRealityGraph:
    graph = CodeRealityGraph()
    for node_id, kind in (
        ("request", "input"),
        ("auth", "function"),
        ("delete_account", "privileged_sink"),
    ):
        graph.add_node(CodeNode(node_id=node_id, kind=kind))
    graph.add_edge(CodeEdge("request", "auth", "calls"))
    graph.add_edge(CodeEdge("auth", "delete_account", "calls"))
    return graph


def test_violation_path_does_not_self_certify_authority():
    result = investigate_invariant(
        _graph(),
        Invariant(
            invariant_id="unauthorized_delete",
            statement="unauthorized input must never reach delete_account",
            protected_scope=frozenset({"security:delete_account"}),
            source_nodes=frozenset({"request"}),
            sink_nodes=frozenset({"delete_account"}),
        ),
        analyzed_relations={"calls"},
    )
    assert result.violation_paths
    assert result.finding_claim["authority"] == 0.0
    assert result.finding_claim["authority_status"] == "contested"


def test_coverage_stays_contested_when_dynamic_path_unresolved():
    result = investigate_invariant(
        _graph(),
        Invariant(
            invariant_id="unauthorized_delete",
            statement="unauthorized input must never reach delete_account",
            protected_scope=frozenset({"security:delete_account"}),
            source_nodes=frozenset({"request"}),
            sink_nodes=frozenset({"delete_account"}),
        ),
        analyzed_relations={"calls"},
        unresolved_dynamic_nodes={"plugin_dispatch"},
    )
    assert result.coverage_claim["value"]["status"] == "contested"
    assert result.coverage_claim["authority"] == 0.0


def test_no_path_found_is_not_proof_of_safety():
    graph = CodeRealityGraph()
    graph.add_node(CodeNode("request", "input"))
    graph.add_node(CodeNode("delete_account", "privileged_sink"))
    result = investigate_invariant(
        graph,
        Invariant(
            invariant_id="unauthorized_delete",
            statement="unauthorized input must never reach delete_account",
            protected_scope=frozenset({"security:delete_account"}),
            source_nodes=frozenset({"request"}),
            sink_nodes=frozenset({"delete_account"}),
        ),
        analyzed_relations={"calls"},
    )
    assert result.finding_claim["value"]["status"] == "not_found"
    assert result.finding_claim["authority"] == 0.0

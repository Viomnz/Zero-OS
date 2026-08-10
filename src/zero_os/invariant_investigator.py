from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from zero_os.code_reality_graph import CodeRealityGraph
from zero_os.pure_logic_claims import Claim, claim_from_dict


@dataclass(frozen=True)
class Invariant:
    invariant_id: str
    statement: str
    protected_scope: frozenset[str]
    source_nodes: frozenset[str] = field(default_factory=frozenset)
    sink_nodes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class InvestigationResult:
    invariant_id: str
    violation_paths: tuple[tuple[str, ...], ...]
    finding_claim: dict[str, Any]
    coverage_claim: dict[str, Any]


def investigate_invariant(
    graph: CodeRealityGraph,
    invariant: Invariant,
    *,
    analyzed_relations: set[str] | None = None,
    unresolved_dynamic_nodes: Iterable[str] = (),
) -> InvestigationResult:
    paths: list[tuple[str, ...]] = []
    for sink in invariant.sink_nodes:
        for path in graph.paths_to(invariant.source_nodes, sink):
            paths.append(tuple(path))

    finding_status = "candidate" if paths else "not_found"
    finding = Claim(
        claim_id=f"finding:{invariant.invariant_id}",
        claim_type="code_finding",
        source="invariant_investigator",
        value={"status": finding_status, "path_count": len(paths)},
        requested_scope=invariant.protected_scope,
        provenance=("code_reality_graph",),
        assumptions=("graph_represents_relevant_execution_edges",),
        alternatives=("violation_exists_outside_modeled_paths",),
        revocation_conditions=("graph_changed", "new_runtime_path_observed", "analysis_scope_expanded"),
    )

    unresolved = tuple(str(item) for item in unresolved_dynamic_nodes if str(item))
    coverage_status = "contested" if unresolved else "candidate"
    coverage = Claim(
        claim_id=f"coverage:{invariant.invariant_id}",
        claim_type="analysis_coverage",
        source="invariant_investigator",
        value={
            "status": coverage_status,
            "analyzed_relations": sorted(analyzed_relations or set()),
            "unresolved_dynamic_nodes": list(unresolved),
            "source_count": len(invariant.source_nodes),
            "sink_count": len(invariant.sink_nodes),
        },
        requested_scope=frozenset({f"coverage:{invariant.invariant_id}"}),
        provenance=("code_reality_graph",),
        assumptions=("modeled_edges_are_complete_within_declared_relations",),
        alternatives=("dynamic_dispatch_or_runtime_edges_are_missing",),
        revocation_conditions=("new_edge_discovered", "runtime_trace_disagrees", "dependency_changed"),
    )

    return InvestigationResult(
        invariant_id=invariant.invariant_id,
        violation_paths=tuple(paths),
        finding_claim=finding.to_dict(),
        coverage_claim=coverage.to_dict(),
    )


def invariant_from_dict(payload: dict[str, Any]) -> Invariant:
    return Invariant(
        invariant_id=str(payload.get("id", "")),
        statement=str(payload.get("statement", "")),
        protected_scope=frozenset(str(item) for item in payload.get("protected_scope", []) if str(item)),
        source_nodes=frozenset(str(item) for item in payload.get("source_nodes", []) if str(item)),
        sink_nodes=frozenset(str(item) for item in payload.get("sink_nodes", []) if str(item)),
    )

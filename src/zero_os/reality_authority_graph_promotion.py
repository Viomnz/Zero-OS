from __future__ import annotations

from zero_os.reality_authority_graph import graph_invariants
from zero_os.reality_authority_graph_pressure import run_graph_pressure


def evaluate_graph_research_promotion(*, independent_external_cases_passed: bool = False, fresh_domain_audit_passed: bool = False) -> dict:
    pressure = run_graph_pressure()
    invariants = set(graph_invariants())
    blockers: list[str] = []

    if not pressure.get("all_passed", False):
        blockers.append("graph_pressure_failed")
    required = {
        "objects_relations_and_joint_states_are_distinct_authority_subjects",
        "local_authority_never_implies_relational_or_joint_authority",
        "parent_revocation_propagates_through_relational_authority",
        "graph_analysis_may_block_but_never_grant_final_authority",
        "path_logic_remains_downstream_of_graph_authority",
    }
    if not required.issubset(invariants):
        blockers.append("graph_invariant_contract_incomplete")
    if not independent_external_cases_passed:
        blockers.append("independent_external_cases_missing")
    if not fresh_domain_audit_passed:
        blockers.append("fresh_domain_audit_missing")

    return {
        "promotion_permitted": not blockers,
        "status": "PROVISIONAL_GRAPH_RESEARCH_PROMOTION" if not blockers else "BLOCK_GRAPH_RESEARCH_PROMOTION",
        "blockers": blockers,
        "pressure": pressure,
        "master_law_change_justified": False,
        "graph_is_final_authority": False,
        "path_logic_final_authority": False,
        "pure_logic_self_certification_permitted": False,
        "interpretation": "relations and hyperedges are candidate first-class authority subjects derived under the current six laws; external pressure remains required",
    }

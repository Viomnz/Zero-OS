from __future__ import annotations

from zero_os.pure_logic_generality_pressure import run_generality_pressure


def evaluate_generality_research_promotion(*, independent_external_cases_passed: bool = False, fresh_domain_audit_passed: bool = False) -> dict:
    pressure = run_generality_pressure()
    blockers: list[str] = []

    if not pressure.get("composition_repeats_across_independent_domains", False):
        blockers.append("composition_candidate_not_repeated_across_domains")
    if not pressure.get("unexplained_case_ids"):
        blockers.append("taxonomy_escape_path_not_demonstrated")
    if pressure.get("taxonomy_complete", True):
        blockers.append("taxonomy_improperly_self_certified_complete")
    if pressure.get("pure_logic_laws_are_final", True):
        blockers.append("master_laws_improperly_marked_final")
    if not independent_external_cases_passed:
        blockers.append("independent_external_cases_missing")
    if not fresh_domain_audit_passed:
        blockers.append("fresh_domain_audit_missing")

    return {
        "promotion_permitted": not blockers,
        "status": "PROVISIONAL_GENERALITY_RESEARCH_PROMOTION" if not blockers else "BLOCK_GENERALITY_PROMOTION",
        "blockers": blockers,
        "pressure": pressure,
        "composition_candidate_promoted_to_master_law": False,
        "master_law_change_justified": False,
        "taxonomy_complete": False,
        "pure_logic_self_certification_permitted": False,
        "interpretation": "composition is a candidate cross-domain failure abstraction; current evidence supports mechanism pressure, not a seventh law",
    }

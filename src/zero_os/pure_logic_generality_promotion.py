from __future__ import annotations

from zero_os.pure_logic_generality_pressure import run_generality_pressure
from zero_os.relational_generality_pressure import run_relational_generality_pressure


def evaluate_generality_research_promotion(*, independent_external_cases_passed: bool = False, fresh_domain_audit_passed: bool = False) -> dict:
    pressure = run_generality_pressure()
    relational = run_relational_generality_pressure()
    blockers: list[str] = []

    if not pressure.get("composition_repeats_across_independent_domains", False):
        blockers.append("composition_candidate_not_repeated_across_domains")
    if not pressure.get("unexplained_case_ids"):
        blockers.append("taxonomy_escape_path_not_demonstrated")
    if pressure.get("taxonomy_complete", True):
        blockers.append("taxonomy_improperly_self_certified_complete")
    if pressure.get("pure_logic_laws_are_final", True):
        blockers.append("master_laws_improperly_marked_final")
    if not relational.get("relation_as_first_class_subject_repeated_across_domains", False):
        blockers.append("relational_authority_derivation_incomplete")
    if not independent_external_cases_passed:
        blockers.append("independent_external_cases_missing")
    if not fresh_domain_audit_passed:
        blockers.append("fresh_domain_audit_missing")

    derived_without_new_law = bool(relational.get("relation_as_first_class_subject_repeated_across_domains", False))

    return {
        "promotion_permitted": not blockers,
        "status": "PROVISIONAL_GENERALITY_RESEARCH_PROMOTION" if not blockers else "BLOCK_GENERALITY_PROMOTION",
        "blockers": blockers,
        "pressure": pressure,
        "relational_pressure": relational,
        "composition_candidate_promoted_to_master_law": False,
        "composition_candidate_current_status": (
            "DERIVED_AS_RELATIONAL_AUTHORITY_MECHANISM_UNDER_EXISTING_LAWS"
            if derived_without_new_law else
            "UNRESOLVED_CANDIDATE"
        ),
        "master_law_change_justified": False,
        "taxonomy_complete": False,
        "pure_logic_self_certification_permitted": False,
        "interpretation": (
            "current synthetic pressure suggests composition failure came from failing to treat relations and joint states as first-class provisional authority subjects; external cases are still required"
            if derived_without_new_law else
            "composition remains an unresolved cross-domain abstraction under pressure"
        ),
    }

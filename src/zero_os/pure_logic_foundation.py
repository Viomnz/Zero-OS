from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


PRIMARY_INVARIANT = "Logic serves reality. Reality never serves logic."


class MasterLaw(str, Enum):
    REALITY = "REALITY"
    SURVIVAL = "SURVIVAL"
    INVESTIGATION = "INVESTIGATION"
    PLURALITY = "PLURALITY"
    PATH = "PATH"
    RESOURCE = "RESOURCE"


class AuthorityState(str, Enum):
    UNTESTED = "UNTESTED"
    PROVISIONAL = "PROVISIONAL"
    SURVIVED_IN_SCOPE = "SURVIVED_IN_SCOPE"
    RESTRICTED = "RESTRICTED"
    CONTESTED = "CONTESTED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    HISTORICAL = "HISTORICAL"


@dataclass(frozen=True)
class FoundationInvariant:
    invariant_id: str
    statement: str
    final_authority: bool = False
    revisable: bool = True


MASTER_LAW_STATEMENTS: dict[MasterLaw, str] = {
    MasterLaw.REALITY: "Nothing internal is reality; all internal representations remain answerable to external reality.",
    MasterLaw.SURVIVAL: "Only what continues surviving stronger recursive pressure within demonstrated scope retains authority.",
    MasterLaw.INVESTIGATION: "Meaningful contradiction triggers causal investigation, repair, preserved failure history, and retest.",
    MasterLaw.PLURALITY: "Preserve viable alternatives until evidence contradicts, restricts, merges, or leaves them unresolved.",
    MasterLaw.PATH: "Among surviving paths, pursue the justified objective with least unnecessary irreversible damage.",
    MasterLaw.RESOURCE: "Allocate reasoning, testing, acting, waiting, storage, and verification by consequence, urgency, reversibility, and information gain.",
}


FOUNDATION_INVARIANTS: tuple[FoundationInvariant, ...] = (
    FoundationInvariant("reality_above_internal_authority", PRIMARY_INVARIANT),
    FoundationInvariant("master_laws_revisable", "The six current Master Laws are provisional and may be modified, merged, or replaced after stronger reality-tested pressure."),
    FoundationInvariant("no_self_certification", "No component may be the sole authority certifying itself, its scope, or its replacement."),
    FoundationInvariant("discovery_not_scope", "Discovery authority and scope authority are separate; discovery confidence cannot rescue failed scope certification."),
    FoundationInvariant("physical_not_cognitive_commitment", "Physical commitment to one action does not require cognitive commitment to one unresolved hypothesis."),
    FoundationInvariant("path_not_final_authority", "Path Law and Water Logic select among surviving paths but cannot create final authority."),
    FoundationInvariant("preservation_not_authority", "Preserving a claim, failure, correction, or beacon does not grant it current authority."),
    FoundationInvariant("local_not_joint_authority", "Authority over individual subjects does not automatically certify their relations, composition, or joint state."),
    FoundationInvariant("structure_not_time_authority", "Structural validity does not automatically establish temporal freshness, ordering, or sequence authority."),
    FoundationInvariant("prediction_not_causation", "Predictive association does not automatically grant causal or intervention authority."),
    FoundationInvariant("security_is_application", "Cybersecurity and Zero OS mechanisms are applications of Pure Logic, not its definition."),
    FoundationInvariant("consciousness_not_assumed", "Functional machine self-awareness does not prove phenomenal consciousness."),
    FoundationInvariant("zero_ai_replacement_allowed", "Zero AI may be replaced by a demonstrably stronger successor architecture."),
)


CANONICAL_PIPELINE: tuple[str, ...] = (
    "REALITY",
    "FALLIBLE_OBSERVATION",
    "PROVENANCE_REALITY_LEDGER",
    "PLURAL_HYPOTHESES_LOGICS_ONTOLOGIES",
    "PREDICTION",
    "RECURSIVE_PRESSURE_VERIFICATION_SCOPE_CHALLENGE",
    "CONTRADICTION_DETECTION",
    "CAUSAL_INVESTIGATION",
    "CONTRADICTION_MEMORY",
    "FILTER_RESTRICT_PRESERVE_INTEGRATE_REGENERATE",
    "OBJECTIVE_INSPECTION",
    "WATER_LOGIC",
    "PATH_GENERATION",
    "DAMAGE_REVERSIBILITY_RESOURCE_ANALYSIS",
    "ACT_PROBE_WAIT_RETREAT_ZERO",
    "REALITY_OUTCOME",
    "PREDICTION_OUTCOME_COMPARISON",
    "AUTHORITY_SCOPE_REVISION",
    "SELF_INVESTIGATION",
    "SANDBOXED_SELF_MODIFICATION",
    "ARCHITECTURE_COMPETITION_EVOLUTION",
    "REALITY",
)


AUTHORITY_SUBJECT_KINDS: tuple[str, ...] = (
    "SUBJECT",
    "RELATION",
    "JOINT_STATE",
    "TEMPORAL_STATE",
    "CAUSAL_CLAIM",
)


NON_FINAL_MECHANISMS: tuple[str, ...] = (
    "LLM_DISCOVERY",
    "VERIFIER",
    "PATH_LAW",
    "WATER_LOGIC",
    "REALITY_LEDGER",
    "REALITY_AUTHORITY_GRAPH",
    "IMMUNE_BEACON",
    "DECOY_BEACON",
    "PRESSURE_ENGINE",
    "SCOPE_CERTIFIER",
    "CONTROL_LOOP",
    "FIRMWARE_ATTESTATION",
)


def foundation_manifest() -> dict:
    """Return the canonical machine-readable foundation without granting authority.

    This manifest describes the current framework. It is not a proof that the
    framework is correct and cannot promote, mutate, sign, or certify itself.
    """
    return {
        "name": "PURE_LOGIC_ZERO_AI_CURRENT_FOUNDATION",
        "primary_invariant": PRIMARY_INVARIANT,
        "master_laws": {law.value: MASTER_LAW_STATEMENTS[law] for law in MasterLaw},
        "master_laws_final": False,
        "foundation_revisable": True,
        "pipeline": list(CANONICAL_PIPELINE),
        "authority_subject_kinds": list(AUTHORITY_SUBJECT_KINDS),
        "non_final_mechanisms": list(NON_FINAL_MECHANISMS),
        "foundation_invariants": [
            {
                "id": item.invariant_id,
                "statement": item.statement,
                "final_authority": item.final_authority,
                "revisable": item.revisable,
            }
            for item in FOUNDATION_INVARIANTS
        ],
        "final_authority_granted": False,
        "self_certified": False,
        "terminal_correct_state_exists": False,
    }


def validate_foundation_manifest(manifest: dict) -> tuple[bool, tuple[str, ...]]:
    """Check anti-dogma invariants of a foundation representation.

    Passing this function only means the representation retains the required
    structural constraints. It does not establish truth or promote the laws.
    """
    reasons: list[str] = []
    if manifest.get("primary_invariant") != PRIMARY_INVARIANT:
        reasons.append("primary_invariant_changed_without_explicit_foundation_revision")
    if manifest.get("master_laws_final") is not False:
        reasons.append("master_laws_cannot_be_final")
    if manifest.get("foundation_revisable") is not True:
        reasons.append("foundation_must_remain_revisable")
    if manifest.get("final_authority_granted") is not False:
        reasons.append("foundation_manifest_cannot_grant_final_authority")
    if manifest.get("self_certified") is not False:
        reasons.append("foundation_manifest_cannot_self_certify")
    if manifest.get("terminal_correct_state_exists") is not False:
        reasons.append("terminal_correct_state_forbidden")
    laws = set((manifest.get("master_laws") or {}).keys())
    required = {law.value for law in MasterLaw}
    if laws != required:
        reasons.append("current_six_master_law_set_not_explicit")
    return (not reasons, tuple(reasons))

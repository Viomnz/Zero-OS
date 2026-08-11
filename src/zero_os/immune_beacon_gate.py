from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from zero_os.immune_beacon import ImmuneBeacon, evaluate_beacon


@dataclass(frozen=True)
class BeaconGateDecision:
    continue_authority_evaluation: bool
    status: str
    reasons: tuple[str, ...]
    beacon_id: str
    subject_id: str
    demonstrated_scope: tuple[str, ...]
    final_authority_granted: bool = False


def evaluate_survival_gate(
    *,
    beacon: ImmuneBeacon,
    current_artifact_hash: str,
    current_state_revision: str,
    requested_scope: Iterable[str],
    active_parent_authority_ids: Iterable[str],
    minimum_pressure_level: int = 1,
    minimum_independent_groups: int = 1,
    active_contradictions: Iterable[str] = (),
    triggered_revocations: Iterable[str] = (),
) -> BeaconGateDecision:
    result = evaluate_beacon(
        beacon,
        current_artifact_hash=current_artifact_hash,
        current_state_revision=current_state_revision,
        requested_scope=requested_scope,
        active_parent_authority_ids=active_parent_authority_ids,
        minimum_pressure_level=minimum_pressure_level,
        minimum_independent_groups=minimum_independent_groups,
        active_contradictions=active_contradictions,
        triggered_revocations=triggered_revocations,
    )
    return BeaconGateDecision(
        continue_authority_evaluation=result.eligible_to_continue_authority_evaluation,
        status=result.status,
        reasons=result.reasons,
        beacon_id=beacon.beacon_id,
        subject_id=beacon.subject_id,
        demonstrated_scope=tuple(beacon.tested_scope),
        final_authority_granted=False,
    )


def gate_invariant_report() -> dict:
    return {
        "beacon_is_final_authority": False,
        "beacon_may_mint_capability": False,
        "beacon_may_expand_scope": False,
        "beacon_may_self_renew": False,
        "artifact_change_invalidates_old_beacon": True,
        "state_revision_change_invalidates_old_beacon": True,
        "contradiction_contests_beacon": True,
        "parent_revocation_contests_beacon": True,
        "issuer_independence_required": True,
        "scope_certifier_independence_required": True,
    }

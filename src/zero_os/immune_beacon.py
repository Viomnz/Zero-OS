from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class BeaconAuthorityState(str, Enum):
    UNTESTED = "UNTESTED"
    PROVISIONAL = "PROVISIONAL"
    SURVIVED_IN_SCOPE = "SURVIVED_IN_SCOPE"
    RESTRICTED = "RESTRICTED"
    CONTESTED = "CONTESTED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    HISTORICAL = "HISTORICAL"


_ACTIVE_STATES = {
    BeaconAuthorityState.PROVISIONAL,
    BeaconAuthorityState.SURVIVED_IN_SCOPE,
    BeaconAuthorityState.RESTRICTED,
}


@dataclass(frozen=True)
class PressureEvidence:
    evidence_id: str
    pressure_family: str
    pressure_level: int
    method_family: str
    lineage_id: str
    evaluator_id: str
    result: str
    provenance: tuple[str, ...] = ()

    def survived(self) -> bool:
        return self.result.upper() in {"PASS", "SURVIVED", "SURVIVED_IN_SCOPE"}


@dataclass(frozen=True)
class ImmuneBeacon:
    beacon_id: str
    subject_id: str
    subject_kind: str
    artifact_hash: str
    state_revision: str
    tested_scope: tuple[str, ...]
    pressure_families: tuple[str, ...]
    max_pressure_level: int
    evidence: tuple[PressureEvidence, ...]
    assumptions: tuple[str, ...]
    contradictions: tuple[str, ...]
    revocation_triggers: tuple[str, ...]
    parent_authority_ids: tuple[str, ...]
    issued_at_utc: str
    expires_at_utc: str
    authority_state: BeaconAuthorityState
    issuer_id: str
    scope_certifier_id: str

    def expired(self, now_utc: datetime | None = None) -> bool:
        now = now_utc or datetime.now(timezone.utc)
        try:
            expiry = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))
        except ValueError:
            return True
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now > expiry.astimezone(timezone.utc)

    def independent_evidence_groups(self) -> frozenset[tuple[str, str]]:
        return frozenset(
            (e.method_family, e.lineage_id)
            for e in self.evidence
            if e.survived() and e.method_family and e.lineage_id
        )


@dataclass(frozen=True)
class BeaconEvaluation:
    valid_for_requested_scope: bool
    status: str
    reasons: tuple[str, ...]
    authority_state: BeaconAuthorityState
    eligible_to_continue_authority_evaluation: bool
    final_authority_granted: bool = False


def evaluate_beacon(
    beacon: ImmuneBeacon,
    *,
    current_artifact_hash: str,
    current_state_revision: str,
    requested_scope: Iterable[str],
    active_parent_authority_ids: Iterable[str],
    minimum_pressure_level: int = 1,
    minimum_independent_groups: int = 1,
    active_contradictions: Iterable[str] = (),
    triggered_revocations: Iterable[str] = (),
    now_utc: datetime | None = None,
) -> BeaconEvaluation:
    reasons: list[str] = []
    state = beacon.authority_state

    if state not in _ACTIVE_STATES:
        reasons.append(f"beacon_authority_state_not_active:{state.value}")
    if beacon.expired(now_utc):
        reasons.append("beacon_expired")
    if not beacon.artifact_hash or beacon.artifact_hash != str(current_artifact_hash):
        reasons.append("beacon_artifact_hash_mismatch")
    if not beacon.state_revision or beacon.state_revision != str(current_state_revision):
        reasons.append("beacon_state_revision_mismatch")

    requested = {str(x) for x in requested_scope if str(x)}
    demonstrated = set(beacon.tested_scope)
    missing_scope = sorted(requested - demonstrated)
    if missing_scope:
        reasons.append("beacon_scope_not_demonstrated:" + ",".join(missing_scope))

    if int(beacon.max_pressure_level) < int(minimum_pressure_level):
        reasons.append("beacon_pressure_level_insufficient")

    surviving_families = {e.pressure_family for e in beacon.evidence if e.survived()}
    missing_families = sorted(set(beacon.pressure_families) - surviving_families)
    if missing_families:
        reasons.append("beacon_pressure_family_not_survived:" + ",".join(missing_families))

    independent_groups = beacon.independent_evidence_groups()
    if len(independent_groups) < max(1, int(minimum_independent_groups)):
        reasons.append("beacon_independent_evidence_insufficient")

    active_parents = {str(x) for x in active_parent_authority_ids if str(x)}
    missing_parents = sorted(set(beacon.parent_authority_ids) - active_parents)
    if missing_parents:
        reasons.append("beacon_parent_authority_missing:" + ",".join(missing_parents))

    contradictions = sorted(set(beacon.contradictions) | {str(x) for x in active_contradictions if str(x)})
    if contradictions:
        reasons.append("beacon_contested_by_contradiction:" + ",".join(contradictions))

    triggered = sorted(set(beacon.revocation_triggers) & {str(x) for x in triggered_revocations if str(x)})
    if triggered:
        reasons.append("beacon_revocation_triggered:" + ",".join(triggered))

    if beacon.issuer_id and beacon.issuer_id == beacon.subject_id:
        reasons.append("beacon_subject_cannot_self_issue")
    if beacon.scope_certifier_id and beacon.scope_certifier_id == beacon.subject_id:
        reasons.append("beacon_subject_cannot_self_certify_scope")
    if beacon.issuer_id and beacon.scope_certifier_id and beacon.issuer_id == beacon.scope_certifier_id:
        reasons.append("beacon_issuer_and_scope_certifier_not_independent")

    ok = not reasons
    return BeaconEvaluation(
        valid_for_requested_scope=ok,
        status="BEACON_SURVIVED_IN_SCOPE" if ok else "BEACON_CONTESTED",
        reasons=tuple(reasons),
        authority_state=state if ok else BeaconAuthorityState.CONTESTED,
        eligible_to_continue_authority_evaluation=ok,
        final_authority_granted=False,
    )


def downgrade_on_contradiction(beacon: ImmuneBeacon, contradiction_id: str) -> ImmuneBeacon:
    contradictions = tuple(sorted(set(beacon.contradictions) | {str(contradiction_id)}))
    return ImmuneBeacon(
        **{
            **beacon.__dict__,
            "contradictions": contradictions,
            "authority_state": BeaconAuthorityState.CONTESTED,
        }
    )


def revoke_beacon(beacon: ImmuneBeacon, reason: str) -> ImmuneBeacon:
    contradictions = tuple(sorted(set(beacon.contradictions) | {str(reason)}))
    return ImmuneBeacon(
        **{
            **beacon.__dict__,
            "contradictions": contradictions,
            "authority_state": BeaconAuthorityState.REVOKED,
        }
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class DecoyBeaconState(str, Enum):
    ARMED = "ARMED"
    TOUCHED = "TOUCHED"
    CONTESTED = "CONTESTED"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class DecoyBeacon:
    beacon_id: str
    decoy_kind: str
    apparent_role: str
    protected_location: str
    expected_accessors: tuple[str, ...]
    created_at: str
    expires_at: str
    evidence_sink: str
    response_policy: str
    state: DecoyBeaconState = DecoyBeaconState.ARMED
    contains_real_secret: bool = False
    grants_authority: bool = False
    # Legacy actor labels remain descriptive only. Suppression requires an exact
    # kernel-bound process identity, never a caller-controlled friendly name.
    expected_process_identities: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecoyTouch:
    beacon_id: str
    actor_id: str
    process_id: str
    action: str
    observed_at: str
    provenance: tuple[str, ...]
    expected_actor: bool = False
    accessor_binding_verified: bool = False


@dataclass(frozen=True)
class DecoyVerdict:
    suspicious: bool
    status: str
    reasons: tuple[str, ...]
    authority_delta: str
    quarantine_eligible: bool
    final_malicious_judgment: bool = False
    authority_granted: bool = False


def evaluate_decoy_touch(beacon: DecoyBeacon, touch: DecoyTouch) -> DecoyVerdict:
    reasons: list[str] = []
    now = datetime.fromisoformat(touch.observed_at.replace("Z", "+00:00"))
    expiry = datetime.fromisoformat(beacon.expires_at.replace("Z", "+00:00"))
    if beacon.contains_real_secret:
        reasons.append("decoy_contains_real_secret")
    if beacon.grants_authority:
        reasons.append("decoy_attempted_authority_role")
    if beacon.state in {DecoyBeaconState.RETIRED}:
        reasons.append("decoy_not_active")
    if now > expiry:
        reasons.append("decoy_expired")
    if not touch.provenance:
        reasons.append("touch_provenance_missing")
    if reasons:
        return DecoyVerdict(
            suspicious=False,
            status="DECOY_EVIDENCE_INVALID",
            reasons=tuple(reasons),
            authority_delta="NONE",
            quarantine_eligible=False,
        )

    expected_identity = touch.process_id in set(beacon.expected_process_identities)
    if touch.expected_actor and touch.accessor_binding_verified and expected_identity:
        return DecoyVerdict(
            suspicious=False,
            status="EXPECTED_DECOY_ACCESS",
            reasons=(),
            authority_delta="NONE",
            quarantine_eligible=False,
        )

    return DecoyVerdict(
        suspicious=True,
        status="DECOY_BEACON_TOUCHED",
        reasons=("unexpected_access_to_deception_artifact",),
        authority_delta="CONTEST_AND_SHRINK_SENSITIVE_CAPABILITIES",
        quarantine_eligible=True,
        final_malicious_judgment=False,
        authority_granted=False,
    )


def decoy_invariants(beacon: DecoyBeacon) -> dict:
    return {
        "decoy_is_not_survival_beacon": True,
        "contains_real_secret": beacon.contains_real_secret,
        "grants_authority": beacon.grants_authority,
        "touch_is_evidence_not_guilt": True,
        "friendly_actor_label_cannot_suppress_tripwire": True,
        "expected_access_requires_kernel_bound_process_identity": True,
        "path_logic_final_authority": False,
    }

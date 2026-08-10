from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from zero_os.pure_logic_authority import certify_candidate


CLAIM_OBSERVED = "observed"
CLAIM_PROPOSED = "proposed"
CLAIM_CONTESTED = "contested"
CLAIM_PROVISIONAL = "provisional"
CLAIM_REJECTED = "rejected"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strings(values: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in list(values or []) if str(item).strip())


@dataclass(frozen=True)
class Claim:
    claim_id: str
    claim_type: str
    value: Any
    source: str
    requested_scope: frozenset[str] = field(default_factory=frozenset)
    demonstrated_scope: frozenset[str] = field(default_factory=frozenset)
    provenance: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    alternatives: tuple[str, ...] = field(default_factory=tuple)
    contradictions: tuple[str, ...] = field(default_factory=tuple)
    falsification_attempts: tuple[str, ...] = field(default_factory=tuple)
    independent_evidence_groups: tuple[str, ...] = field(default_factory=tuple)
    status: str = CLAIM_PROPOSED
    authority: float = 0.0
    observed_at_utc: str = field(default_factory=_utc_now)
    expires_at_utc: str = ""
    revocation_conditions: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "value": self.value,
            "source": self.source,
            "requested_scope": sorted(self.requested_scope),
            "demonstrated_scope": sorted(self.demonstrated_scope),
            "provenance": list(self.provenance),
            "assumptions": list(self.assumptions),
            "alternatives": list(self.alternatives),
            "contradictions": list(self.contradictions),
            "falsification_attempts": list(self.falsification_attempts),
            "independent_evidence_groups": list(self.independent_evidence_groups),
            "status": self.status,
            "authority": float(self.authority),
            "observed_at_utc": self.observed_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "revocation_conditions": list(self.revocation_conditions),
            "may_mutate": self.status == CLAIM_PROVISIONAL and self.authority > 0.0,
        }


def make_claim(
    *,
    claim_id: str,
    claim_type: str,
    value: Any,
    source: str,
    requested_scope: Iterable[str],
    provenance: Iterable[str] | None = None,
    assumptions: Iterable[str] | None = None,
    alternatives: Iterable[str] | None = None,
    contradictions: Iterable[str] | None = None,
    observed_at_utc: str = "",
    expires_at_utc: str = "",
    revocation_conditions: Iterable[str] | None = None,
) -> Claim:
    return Claim(
        claim_id=str(claim_id),
        claim_type=str(claim_type),
        value=value,
        source=str(source),
        requested_scope=frozenset(_strings(requested_scope)),
        provenance=_strings(provenance),
        assumptions=_strings(assumptions),
        alternatives=_strings(alternatives),
        contradictions=_strings(contradictions),
        observed_at_utc=str(observed_at_utc or _utc_now()),
        expires_at_utc=str(expires_at_utc or ""),
        revocation_conditions=_strings(revocation_conditions),
    )


def certify_claim(claim: Claim, evidence: Iterable[dict[str, Any]]) -> Claim:
    records = [dict(item or {}) for item in evidence]
    decision = certify_candidate(
        {"source": claim.source, "scope": sorted(claim.requested_scope)},
        records,
    )
    status_map = {
        "provisional": CLAIM_PROVISIONAL,
        "contested": CLAIM_CONTESTED,
        "rejected": CLAIM_REJECTED,
    }
    groups = sorted({str(item.get("independent_group", "")) for item in records if str(item.get("independent_group", ""))})
    contradictions = list(claim.contradictions)
    if "independent_contradiction_present" in list(decision.get("reasons", [])):
        contradictions.append("independent_contradiction_present")
    return Claim(
        claim_id=claim.claim_id,
        claim_type=claim.claim_type,
        value=claim.value,
        source=claim.source,
        requested_scope=claim.requested_scope,
        demonstrated_scope=frozenset(str(item) for item in decision.get("demonstrated_scope", [])),
        provenance=claim.provenance,
        assumptions=claim.assumptions,
        alternatives=claim.alternatives,
        contradictions=tuple(dict.fromkeys(contradictions)),
        falsification_attempts=tuple(str(item.get("test", item.get("source", ""))) for item in records if str(item.get("test", item.get("source", "")))),
        independent_evidence_groups=tuple(groups),
        status=status_map.get(str(decision.get("status", "contested")), CLAIM_CONTESTED),
        authority=float(decision.get("authority", 0.0) or 0.0),
        observed_at_utc=claim.observed_at_utc,
        expires_at_utc=claim.expires_at_utc,
        revocation_conditions=claim.revocation_conditions,
    )


def authority_required(claim: Claim, scope: str) -> bool:
    target = str(scope).strip()
    return bool(
        target
        and claim.status == CLAIM_PROVISIONAL
        and claim.authority > 0.0
        and target in claim.demonstrated_scope
        and not claim.contradictions
    )

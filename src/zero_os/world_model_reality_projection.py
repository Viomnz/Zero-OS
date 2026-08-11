from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from zero_os.reality_ledger import RealityLedger, RealityRecord


def _expiry(observed_at_utc: str, ttl_seconds: int) -> str:
    try:
        observed = datetime.fromisoformat(str(observed_at_utc or "").replace("Z", "+00:00"))
    except ValueError:
        observed = datetime.now(timezone.utc)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return (observed.astimezone(timezone.utc) + timedelta(seconds=max(1, int(ttl_seconds)))).isoformat()


def project_world_model_to_reality_ledger(model: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy world-model booleans/scores into scoped Reality Ledger claims.

    This adapter deliberately does not grant AuthorityLedger state. A fresh and
    apparently healthy domain receives only PROVISIONAL demonstrated scope for the
    domain observation itself. Stale, blocking, or explicitly unhealthy domains are
    CONTESTED and demonstrate no operational authority.
    """
    payload = dict(model or {})
    ledger = RealityLedger()
    contested: list[str] = []
    provisional: list[str] = []

    for name, raw in dict(payload.get("domains") or {}).items():
        domain = dict(raw or {})
        source = str(domain.get("source", "unknown_source") or "unknown_source")
        observed_at = str(domain.get("observed_at_utc", "") or payload.get("time_utc", ""))
        ttl = max(1, int(domain.get("freshness_ttl_seconds", 60) or 60))
        stale = bool(domain.get("stale", False))
        blocking = bool(domain.get("blocking", False))
        healthy = bool(domain.get("healthy", False))
        scope = f"world:{name}"
        contradictions: list[str] = []
        if stale:
            contradictions.append("observation_stale")
        if blocking:
            contradictions.append("domain_blocking")
        if not healthy:
            contradictions.append("domain_not_healthy")

        status = "CONTESTED" if contradictions else "PROVISIONAL"
        demonstrated_scope = () if contradictions else (scope,)
        record_id = f"world:{name}:{observed_at or 'unknown'}"
        record = RealityRecord(
            record_id=record_id,
            subject_id=f"world_model:{name}",
            claim_type="domain_observation",
            value=dict(domain.get("summary") or {}),
            provenance=(source,),
            assumptions=("source_payload_is_fallible", "world_model_is_not_reality"),
            dependencies=(),
            requested_scope=(scope,),
            demonstrated_scope=demonstrated_scope,
            contradictions=tuple(contradictions),
            status=status,
            observed_at_utc=observed_at,
            expires_at_utc=_expiry(observed_at, ttl),
        )
        ledger.put(record)
        if status == "CONTESTED":
            contested.append(record_id)
        else:
            provisional.append(record_id)

    return {
        "ledger": ledger,
        "records": [record.to_dict() for record in ledger.records.values()],
        "record_count": len(ledger.records),
        "contested_record_ids": contested,
        "provisional_record_ids": provisional,
        "authority_granted": False,
        "epistemic_role": "provenance_and_scope_projection_only",
    }

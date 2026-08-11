from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict

from zero_os.authority_ledger import AuthorityLedger, AuthorityRecord
from zero_os.authority_root_of_trust import issue_attestation
from zero_os.capability_lease import capability_lease_context, lease_from_attestation
from zero_os.capability_registry import capability_class
from zero_os.dynamic_capability_authority import CapabilityAuthorityContext
from zero_os.objective_authority import ObjectiveAuthority, ObjectiveAuthorityLedger
from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, IdentityAuthority, decide as constitutional_decide
from zero_os.pure_logic_capability_kernel import authorize_capability
from zero_os.resource_law_budget import allocate_verification_budget
from zero_os.trust_graph import TrustNode


def context_from_plan(plan_context: dict | None) -> CapabilityAuthorityContext | None:
    payload = dict((plan_context or {}).get("capability_context") or {})
    if not payload:
        return None
    return CapabilityAuthorityContext(
        principal_id=str(payload.get("principal_id", "")),
        identity_verified=bool(payload.get("identity_verified", False)),
        granted_scopes=frozenset(str(x) for x in payload.get("granted_scopes", []) if str(x)),
        contradiction_severity=str(payload.get("contradiction_severity", "none")),
        anomaly_score=float(payload.get("anomaly_score", 0.0) or 0.0),
        evidence_fresh=bool(payload.get("evidence_fresh", True)),
        tenant_id=str(payload.get("tenant_id", "")),
        resource_tenant_id=str(payload.get("resource_tenant_id", "")),
    )


def trust_from_plan(plan_context: dict | None) -> TrustNode | None:
    payload = dict((plan_context or {}).get("trust_node") or {})
    if not payload:
        return None
    return TrustNode(
        principal_id=str(payload.get("principal_id", "")),
        identity_provenance=tuple(str(x) for x in payload.get("identity_provenance", []) if str(x)),
        demonstrated_scopes=frozenset(str(x) for x in payload.get("demonstrated_scopes", []) if str(x)),
        state=str(payload.get("state", "NORMAL")),
        contradiction_count=int(payload.get("contradiction_count", 0) or 0),
        anomaly_score=float(payload.get("anomaly_score", 0.0) or 0.0),
        revocation_reasons=tuple(str(x) for x in payload.get("revocation_reasons", []) if str(x)),
    )


def _authority_ledger(payload: dict) -> AuthorityLedger:
    ledger = AuthorityLedger()
    for raw in list(payload.get("authority_records", [])):
        item = dict(raw or {})
        if not item.get("authority_id"):
            continue
        ledger.put(
            AuthorityRecord(
                authority_id=str(item.get("authority_id", "")),
                subject_id=str(item.get("subject_id", "")),
                claim_type=str(item.get("claim_type", "")),
                value_fingerprint=str(item.get("value_fingerprint", "")),
                state_revision=str(item.get("state_revision", "")),
                demonstrated_scope=frozenset(str(x) for x in item.get("demonstrated_scope", []) if str(x)),
                state=str(item.get("state", "UNTESTED")),
                dependencies=frozenset(str(x) for x in item.get("dependencies", []) if str(x)),
                pressure_history=tuple(str(x) for x in item.get("pressure_history", []) if str(x)),
                contradiction_history=tuple(str(x) for x in item.get("contradiction_history", []) if str(x)),
                last_stronger_survival=str(item.get("last_stronger_survival", "")),
                fallback=str(item.get("fallback", "deny")),
                next_required_pressure=tuple(str(x) for x in item.get("next_required_pressure", []) if str(x)),
                expires_at_utc=str(item.get("expires_at_utc", "")),
                revocation_conditions=tuple(str(x) for x in item.get("revocation_conditions", []) if str(x)),
            )
        )
    return ledger


def _objective_ledger(payload: dict) -> ObjectiveAuthorityLedger:
    ledger = ObjectiveAuthorityLedger()
    for raw in list(payload.get("objective_records", [])):
        item = dict(raw or {})
        if not item.get("objective_id"):
            continue
        ledger.put(
            ObjectiveAuthority(
                objective_id=str(item.get("objective_id", "")),
                statement=str(item.get("statement", "")),
                provenance=tuple(str(x) for x in item.get("provenance", []) if str(x)),
                demonstrated_scope=frozenset(str(x) for x in item.get("demonstrated_scope", []) if str(x)),
                dependencies=frozenset(str(x) for x in item.get("dependencies", []) if str(x)),
                revocation_conditions=tuple(str(x) for x in item.get("revocation_conditions", []) if str(x)),
                contradiction_history=tuple(str(x) for x in item.get("contradiction_history", []) if str(x)),
                status=str(item.get("status", "PROVISIONAL")),
                expires_at_utc=str(item.get("expires_at_utc", "")),
            )
        )
    return ledger


def _constitutional_gate(kind: str, required_scope: str, plan_context: dict | None) -> dict:
    payload = dict((plan_context or {}).get("constitutional_context") or {})
    if not payload:
        return {"allowed": False, "reason": "constitutional_context_missing", "decision": None, "request": None, "payload": {}}
    actor_raw = dict(payload.get("actor") or {})
    actor = IdentityAuthority(
        principal_id=str(actor_raw.get("principal_id", "")),
        provenance=tuple(str(x) for x in actor_raw.get("provenance", []) if str(x)),
        authenticated=bool(actor_raw.get("authenticated", False)),
        demonstrated_scopes=frozenset(str(x) for x in actor_raw.get("demonstrated_scopes", []) if str(x)),
        trust_state=str(actor_raw.get("trust_state", "NORMAL")),
    )
    authority_id = str(payload.get("authority_id", ""))
    objective_id = str(payload.get("objective_id", ""))
    if not authority_id or not objective_id:
        return {"allowed": False, "reason": "constitutional_authority_or_objective_missing", "decision": None, "request": None, "payload": payload}
    capability = capability_class(kind)
    consequence = str((capability.risk if capability is not None else payload.get("consequence", "high")) or "high")
    reversible = bool(payload.get("reversible", True))
    request = ConstitutionalRequest(
        actor=actor,
        action_scope=str(required_scope),
        objective_id=objective_id,
        authority_id=authority_id,
        requested_capability=str(kind),
        consequence=consequence,
        reversible=reversible,
        contradictions=tuple(str(x) for x in payload.get("contradictions", []) if str(x)),
    )
    budget = allocate_verification_budget(
        consequence=consequence,
        urgency=str(payload.get("urgency", "medium")),
        reversibility=str(payload.get("reversibility", "high" if reversible else "low")),
        information_gain=str(payload.get("information_gain", "medium")),
    )
    decision = constitutional_decide(
        request=request,
        authority_ledger=_authority_ledger(payload),
        objective_ledger=_objective_ledger(payload),
        budget=budget,
        active_dependency_ids=[str(x) for x in payload.get("active_dependency_ids", []) if str(x)],
        correction_plane_allows=bool(payload.get("correction_plane_allows", True)),
        legal_state_ok=bool(payload.get("legal_state_ok", True)),
    )
    return {"allowed": decision.allowed, "reason": decision.status, "decision": decision, "request": request, "payload": payload}


def gate_action(cwd: str, kind: str, *, plan_context: dict | None = None, reversible: bool = True, blast_radius: str = "local") -> dict:
    capability = capability_class(kind)
    decision = authorize_capability(cwd, kind, context=context_from_plan(plan_context), trust=trust_from_plan(plan_context), reversible=reversible, blast_radius=blast_radius)
    payload = {
        "allowed": decision.allowed,
        "kind": decision.kind,
        "reason": decision.reason,
        "disposition": decision.disposition,
        "required_scope": decision.required_scope,
        "response": asdict(decision.response),
        "constitutional": None,
        "constitutional_request": None,
    }
    if not decision.allowed:
        return payload
    if capability is not None and capability.mode != "mutation" and (capability.sensitive or capability.risk in {"high", "critical"}):
        constitutional = _constitutional_gate(capability.name, capability.required_scope, plan_context)
        payload["constitutional"] = constitutional.get("decision")
        payload["constitutional_request"] = constitutional.get("request")
        if not bool(constitutional.get("allowed", False)):
            payload["allowed"] = False
            payload["reason"] = str(constitutional.get("reason", "constitutional_authority_denied"))
            payload["disposition"] = "restrict"
    return payload


def _lease_scopes(kind: str, required_scope: str, plan_context: dict | None = None) -> set[str]:
    scopes = {str(required_scope)} if str(required_scope) else set()
    capability = capability_class(kind)
    context_payload = dict((plan_context or {}).get("capability_context") or {})
    granted = {str(x) for x in context_payload.get("granted_scopes", []) if str(x)}
    permitted_hosts = {str(x).strip().lower() for x in context_payload.get("permitted_hosts", []) if str(x).strip()}
    if capability is None:
        return scopes
    if capability.mode == "network_read":
        scopes.update({"network:fetch", "network:read"})
    elif capability.mode == "secret_read":
        scopes.add("credential:read")
    elif capability.mode == "invoke":
        scopes.add("tool:invoke")
    elif capability.mode == "device":
        scopes.add("device:access")
    elif capability.name == "filesystem_read":
        scopes.add("filesystem:read")
    elif capability.mode == "mutation":
        if capability.external_side_effect:
            scopes.add("network:write")
        if capability.name in {"code_change", "self_repair", "recover", "store_install", "self_upgrade", "policy_change", "authority_change"}:
            scopes.add("filesystem:write")
    for host in permitted_hosts:
        host_scope = f"host:{host}"
        if host_scope in granted or "host:*" in granted:
            scopes.add(host_scope)
    for special in {"host:*", "network:local", "credential:transmit"}:
        if special in granted:
            scopes.add(special)
    return scopes


@contextmanager
def authorized_capability_context(cwd: str, kind: str, *, plan_context: dict | None = None, reversible: bool = True, blast_radius: str = "local", ttl_seconds: int = 30):
    gate = gate_action(cwd, kind, plan_context=plan_context, reversible=reversible, blast_radius=blast_radius)
    if not gate["allowed"]:
        yield gate
        return
    context = context_from_plan(plan_context)
    principal_id = context.principal_id if context is not None else "zero-os"
    request = gate.get("constitutional_request")
    decision = gate.get("constitutional")
    if request is None or decision is None or not bool(decision.allowed):
        denied = dict(gate)
        denied["allowed"] = False
        denied["reason"] = "issuer_requires_survived_constitutional_decision"
        yield denied
        return
    authority_record = _authority_ledger(dict((plan_context or {}).get("constitutional_context") or {})).get(request.authority_id)
    subject_id = authority_record.subject_id if authority_record is not None else request.authority_id
    state_revision = authority_record.state_revision if authority_record is not None else "unknown"
    scopes = _lease_scopes(kind, gate["required_scope"], plan_context)
    attestation = issue_attestation(
        cwd,
        artifact_kind="capability_lease",
        principal_id=principal_id,
        authority_id=request.authority_id,
        objective_id=request.objective_id,
        action_kind=kind,
        subject_id=subject_id,
        state_revision=state_revision,
        scopes=scopes,
        constitutional_allowed=decision.allowed,
        constitutional_status="AUTHORIZED",
        ttl_seconds=ttl_seconds,
    )
    lease = lease_from_attestation(cwd, attestation)
    with capability_lease_context(lease):
        payload = dict(gate)
        payload["lease"] = {
            "principal_id": lease.principal_id,
            "scopes": sorted(lease.scopes),
            "expires_at_utc": lease.expires_at_utc,
            "issuer_id": lease.attestation.issuer_id,
            "artifact_id": lease.attestation.artifact_id,
        }
        yield payload

from datetime import datetime, timedelta, timezone

from zero_os.active_scope_pressure import PressureCandidate, select_next_scope_pressure
from zero_os.agent_permission_policy import classify_action
from zero_os.authority_ledger import (
    AuthorityLedger,
    AuthorityRecord,
    CONTESTED,
    REVOKED,
    SURVIVED_IN_SCOPE,
)
from zero_os.evidence_binding import EvidenceRecord, canonical_fingerprint, verified_independence_groups
from zero_os.final_action_authority import ActionAuthorityRequest, authorize_action
from zero_os.pure_logic_claims import Claim, CLAIM_PROVISIONAL, authority_required, claim_from_dict


def _evidence(evidence_id, lineage, method, *, supports=True, revision="r1"):
    value = {"ready": True}
    return EvidenceRecord(
        evidence_id=evidence_id,
        subject_id="runtime-A",
        claim_type="runtime_ready",
        value_fingerprint=canonical_fingerprint(value),
        state_revision=revision,
        source=evidence_id,
        source_lineage=frozenset(lineage),
        method_family=method,
        supports=supports,
        scope=frozenset({"runtime:ready"}),
        quality=0.9,
    )


def test_shared_lineage_does_not_become_independent_by_naming():
    a = _evidence("audit-a", {"same_sensor"}, "formal")
    b = _evidence("audit-b", {"same_sensor"}, "empirical")
    groups = verified_independence_groups([a, b])
    assert len(groups) == 1


def test_repeated_weak_pass_does_not_expand_scope():
    ledger = AuthorityLedger()
    ledger.put(
        AuthorityRecord(
            authority_id="runtime-ready",
            subject_id="runtime-A",
            claim_type="runtime_ready",
            value_fingerprint=canonical_fingerprint({"ready": True}),
            state_revision="r1",
            demonstrated_scope=frozenset({"runtime:ready"}),
            state=SURVIVED_IN_SCOPE,
        )
    )
    for index in range(20):
        ledger.pressure_event(
            "runtime-ready",
            pressure_id=f"weak-{index}",
            outcome="pass",
            independent=False,
            inside_demonstrated_scope=True,
            stronger_than_previous=False,
            new_scope={"runtime:admin"},
        )
    assert "runtime:admin" not in ledger.get("runtime-ready").demonstrated_scope


def test_independent_in_scope_failure_revokes_and_propagates():
    ledger = AuthorityLedger()
    ledger.put(AuthorityRecord("verifier", "verifier", "verifier", "x", "r1", frozenset({"verify"}), SURVIVED_IN_SCOPE))
    ledger.put(AuthorityRecord("runtime", "runtime-A", "runtime_ready", "y", "r1", frozenset({"runtime:ready"}), SURVIVED_IN_SCOPE, frozenset({"verifier"})))
    ledger.pressure_event("verifier", pressure_id="strong-red-team", outcome="fail", independent=True, inside_demonstrated_scope=True)
    assert ledger.get("verifier").state == REVOKED
    assert ledger.get("runtime").state == CONTESTED


def test_final_action_denies_stale_revision_even_with_good_evidence():
    ledger = AuthorityLedger()
    value = {"ready": True}
    ledger.put(
        AuthorityRecord(
            authority_id="runtime-ready",
            subject_id="runtime-A",
            claim_type="runtime_ready",
            value_fingerprint=canonical_fingerprint(value),
            state_revision="r1",
            demonstrated_scope=frozenset({"runtime:ready"}),
            state=SURVIVED_IN_SCOPE,
        )
    )
    evidence = [_evidence("formal-a", {"sensor-a"}, "formal"), _evidence("runtime-b", {"sensor-b"}, "runtime")]
    request = ActionAuthorityRequest("act-1", "runtime-A", "runtime_ready", value, "r2", "runtime:ready", "runtime-ready")
    decision = authorize_action(request, ledger=ledger, evidence=evidence)
    assert decision.allowed is False
    assert decision.reason in {"independent_exact_claim_evidence_missing", "state_revision_changed"}


def test_final_action_allows_only_exact_fresh_independent_claim():
    ledger = AuthorityLedger()
    value = {"ready": True}
    ledger.put(
        AuthorityRecord(
            authority_id="runtime-ready",
            subject_id="runtime-A",
            claim_type="runtime_ready",
            value_fingerprint=canonical_fingerprint(value),
            state_revision="r1",
            demonstrated_scope=frozenset({"runtime:ready"}),
            state=SURVIVED_IN_SCOPE,
        )
    )
    evidence = [_evidence("formal-a", {"sensor-a"}, "formal"), _evidence("runtime-b", {"sensor-b"}, "runtime")]
    request = ActionAuthorityRequest("act-1", "runtime-A", "runtime_ready", value, "r1", "runtime:ready", "runtime-ready")
    decision = authorize_action(request, ledger=ledger, evidence=evidence)
    assert decision.allowed is True
    assert decision.independent_support_groups == 2


def test_expired_claim_cannot_authorize():
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    claim = Claim(
        claim_id="c",
        claim_type="runtime_ready",
        value=True,
        source="runtime",
        demonstrated_scope=frozenset({"runtime:ready"}),
        status=CLAIM_PROVISIONAL,
        authority=1.0,
        expires_at_utc=expired,
    )
    assert authority_required(claim, "runtime:ready") is False
    assert claim_from_dict(claim.to_dict()).claim_id == "c"


def test_scope_pressure_selector_ignores_discovery_fit():
    weak_for_scope_but_high_discovery = PressureCandidate("a", 0.1, 0.1, 0.1, 0.1, 0.1, 1.0, discovery_fit=1.0)
    strong_scope_probe = PressureCandidate("b", 0.9, 0.9, 0.8, 0.8, 0.7, 1.0, discovery_fit=0.0)
    assert select_next_scope_pressure([weak_for_scope_but_high_discovery]).pressure_id == "a"
    assert select_next_scope_pressure([weak_for_scope_but_high_discovery, strong_scope_probe]).pressure_id == "b"


def test_unknown_action_is_denied_by_default(tmp_path):
    decision = classify_action(str(tmp_path), "totally_new_mutating_action")
    assert decision["decision"] == "deny"
    assert decision["explicitly_configured"] is False

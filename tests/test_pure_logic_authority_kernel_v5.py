from datetime import datetime, timedelta, timezone

from zero_os.active_evidence_investigator import generate_evidence_requests
from zero_os.architecture_promotion_authority import evaluate_architecture_promotion
from zero_os.authority_ledger import AuthorityLedger, AuthorityRecord, SURVIVED_IN_SCOPE
from zero_os.core import CORE_POLICY
from zero_os.discovery_scope_plane import DiscoveryCandidate, ScopePressure, certify_scope, select_discovery_winner
from zero_os.independent_outcome_verifier import OutcomeEvidence, verify_outcome
from zero_os.objective_authority import ObjectiveAuthority, ObjectiveAuthorityLedger
from zero_os.protected_correction_plane import CorrectionCandidate, default_correction_plane
from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, IdentityAuthority, decide
from zero_os.resource_law_budget import allocate_verification_budget


def _future(seconds=120):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _authority_ledger():
    ledger = AuthorityLedger()
    ledger.put(
        AuthorityRecord(
            authority_id="claim-1",
            subject_id="action-1",
            claim_type="action_authority",
            value_fingerprint="abc",
            state_revision="r1",
            demonstrated_scope=frozenset({"system:critical_write"}),
            state=SURVIVED_IN_SCOPE,
            expires_at_utc=_future(),
        )
    )
    return ledger


def _objective_ledger():
    ledger = ObjectiveAuthorityLedger()
    ledger.put(
        ObjectiveAuthority(
            objective_id="obj-1",
            statement="perform bounded repair",
            provenance=("user_request",),
            demonstrated_scope=frozenset({"system:critical_write"}),
            expires_at_utc=_future(),
            status="SURVIVED_IN_SCOPE",
        )
    )
    return ledger


def test_core_is_protected_but_not_epistemically_immutable():
    assert CORE_POLICY.runtime_core_protected is True
    assert CORE_POLICY.revision_capable is True
    assert CORE_POLICY.immutable_core is False
    assert CORE_POLICY.privileged_identity_authority_required is True


def test_discovery_winner_does_not_certify_scope():
    winner = select_discovery_winner(
        [
            DiscoveryCandidate("a", "A", 0.99, frozenset({"runtime:all"})),
            DiscoveryCandidate("b", "B", 0.20, frozenset({"runtime:all"})),
        ]
    )
    assert winner.candidate_id == "a"
    scope = certify_scope(winner, [])
    assert scope.status == "CONTESTED"
    assert "runtime:all" in scope.contested_scope


def test_scope_requires_independent_falsification_pressure():
    candidate = DiscoveryCandidate("a", "A", 1.0, frozenset({"runtime:read"}))
    weak = ScopePressure("p1", "runtime:read", False, True, "pass", "same_model")
    scope = certify_scope(candidate, [weak])
    assert not scope.demonstrated_scope

    strong = ScopePressure("p2", "runtime:read", True, True, "pass", "empirical_runtime", ("sensor_b",))
    scope = certify_scope(candidate, [strong])
    assert scope.demonstrated_scope == frozenset({"runtime:read"})


def test_contested_scope_generates_new_evidence_request():
    requests = generate_evidence_requests(
        contested_scopes=["runtime:write"],
        existing_method_families=["empirical_runtime"],
        existing_lineages=["model-a"],
    )
    assert len(requests) == 1
    assert requests[0].target_scope == "runtime:write"
    assert requests[0].preferred_method_family != "empirical_runtime"


def test_privileged_action_requires_identity_evidence_and_scope():
    actor = IdentityAuthority(
        principal_id="agent",
        provenance=("local_process",),
        authenticated=False,
        demonstrated_scopes=frozenset({"system:critical_write"}),
    )
    request = ConstitutionalRequest(actor, "system:critical_write", "obj-1", "claim-1", "policy_change", "critical", True)
    decision = decide(
        request=request,
        authority_ledger=_authority_ledger(),
        objective_ledger=_objective_ledger(),
        budget=allocate_verification_budget(consequence="critical", reversibility="medium"),
        active_dependency_ids=[],
    )
    assert decision.allowed is False
    assert "strong_identity_evidence_required" in decision.reasons


def test_objective_authority_is_separate_from_action_authority():
    actor = IdentityAuthority(
        principal_id="agent",
        provenance=("hardware_key",),
        authenticated=True,
        demonstrated_scopes=frozenset({"system:critical_write"}),
    )
    request = ConstitutionalRequest(actor, "system:critical_write", "missing-objective", "claim-1", "policy_change", "critical", True)
    decision = decide(
        request=request,
        authority_ledger=_authority_ledger(),
        objective_ledger=_objective_ledger(),
        budget=allocate_verification_budget(consequence="critical", reversibility="medium"),
        active_dependency_ids=[],
    )
    assert decision.allowed is False
    assert "objective_authority_missing_or_out_of_scope" in decision.reasons


def test_actor_cannot_be_sole_outcome_verifier():
    evidence = [OutcomeEvidence("actor", "runtime_probe", "ok", True, ("actor",))]
    result = verify_outcome(actor_id="actor", expected_state="ok", evidence=evidence)
    assert result.verified is False


def test_independent_outcome_can_verify_with_distinct_source():
    evidence = [OutcomeEvidence("probe-b", "runtime_probe", "ok", True, ("sensor-b",))]
    result = verify_outcome(actor_id="actor", expected_state="ok", evidence=evidence)
    assert result.verified is True


def test_correction_plane_blocks_self_evaluation_and_missing_rollback():
    candidate = CorrectionCandidate(
        candidate_id="c1",
        target="core_policy",
        proposer_id="agent-a",
        provenance=("patch",),
        invariant_checks=("inv-pass",),
        pressure_results=("pressure-pass",),
        independent_evaluators=("agent-a",),
        rollback_reference="",
        canary_reference="canary-1",
        compatibility_reference="compat-1",
    )
    decision = default_correction_plane().architecture_revision_allowed(candidate)
    assert decision.allowed is False
    assert "proposer_cannot_be_sole_or_self_evaluator" in decision.reasons
    assert "rollback_missing" in decision.reasons


def test_architecture_promotion_refuses_one_bypass():
    candidate = CorrectionCandidate(
        candidate_id="c2",
        target="core_policy",
        proposer_id="agent-a",
        provenance=("patch",),
        invariant_checks=("inv-pass",),
        pressure_results=("pressure-pass",),
        independent_evaluators=("verifier-b",),
        rollback_reference="snapshot-1",
        canary_reference="canary-1",
        compatibility_reference="compat-1",
    )
    result = evaluate_architecture_promotion(
        candidate=candidate,
        correction_plane=default_correction_plane(),
        critical_invariants_passed=True,
        independent_outcome_verified=True,
        identified_authority_bypasses=1,
        identified_capability_bypasses=0,
        demonstrated_scope=["python_static"],
        unresolved_scope=["native_runtime"],
    )
    assert result.promote is False
    assert "identified_authority_bypass_present" in result.reasons


def test_resource_law_scales_verification_depth():
    cheap = allocate_verification_budget(consequence="low", reversibility="high")
    critical = allocate_verification_budget(consequence="critical", reversibility="low")
    assert critical.depth > cheap.depth
    assert critical.required_evidence_groups >= cheap.required_evidence_groups
    assert critical.require_independent_outcome is True
    assert critical.require_formal_invariant_check is True

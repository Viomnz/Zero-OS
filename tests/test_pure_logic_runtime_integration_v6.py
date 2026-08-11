from datetime import datetime, timedelta, timezone

from zero_os.architecture_promotion_authority import evaluate_architecture_promotion
from zero_os.authority_ledger import AuthorityLedger, AuthorityRecord, SURVIVED_IN_SCOPE
from zero_os.evidence_binding import EvidenceRecord, canonical_fingerprint
from zero_os.final_action_authority import ActionAuthorityRequest, authorize_and_issue_execution_ticket
from zero_os.objective_authority import ObjectiveAuthority, ObjectiveAuthorityLedger
from zero_os.protected_correction_plane import CorrectionCandidate, default_correction_plane
from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, IdentityAuthority
from zero_os.resource_law_budget import allocate_verification_budget


def _future(seconds=120):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _setup(scope="system:policy_change", consequence="critical"):
    value = {"operation": "bounded_policy_change", "target": "test"}
    authority = AuthorityLedger()
    authority.put(
        AuthorityRecord(
            authority_id="claim-1",
            subject_id="action-1",
            claim_type="action_authority",
            value_fingerprint=canonical_fingerprint(value),
            state_revision="r1",
            demonstrated_scope=frozenset({scope}),
            state=SURVIVED_IN_SCOPE,
            expires_at_utc=_future(),
        )
    )
    objective = ObjectiveAuthorityLedger()
    objective.put(
        ObjectiveAuthority(
            objective_id="obj-1",
            statement="perform bounded policy change",
            provenance=("user_request",),
            demonstrated_scope=frozenset({scope}),
            status="SURVIVED_IN_SCOPE",
            expires_at_utc=_future(),
        )
    )
    actor = IdentityAuthority(
        principal_id="operator",
        provenance=("hardware_key", "local_session"),
        authenticated=True,
        demonstrated_scopes=frozenset({scope}),
    )
    constitutional = ConstitutionalRequest(
        actor=actor,
        action_scope=scope,
        objective_id="obj-1",
        authority_id="claim-1",
        requested_capability="policy_change",
        consequence=consequence,
        reversible=True,
    )
    request = ActionAuthorityRequest(
        action_id="policy-change-1",
        subject_id="action-1",
        claim_type="action_authority",
        claim_value=value,
        state_revision="r1",
        required_scope=scope,
        authority_id="claim-1",
        mutating=True,
    )
    evidence = [
        EvidenceRecord(
            "e1",
            "action-1",
            "action_authority",
            canonical_fingerprint(value),
            "r1",
            "runtime-probe-a",
            frozenset({"sensor-a"}),
            "runtime_observation",
            True,
            frozenset({scope}),
        ),
        EvidenceRecord(
            "e2",
            "action-1",
            "action_authority",
            canonical_fingerprint(value),
            "r1",
            "model-check-b",
            frozenset({"model-b"}),
            "model_check",
            True,
            frozenset({scope}),
        ),
        EvidenceRecord(
            "e3",
            "action-1",
            "action_authority",
            canonical_fingerprint(value),
            "r1",
            "canary-c",
            frozenset({"canary-c"}),
            "canary_execution",
            True,
            frozenset({scope}),
        ),
    ]
    return request, authority, objective, constitutional, evidence


def test_mutation_ticket_cannot_exist_without_v5_constitution(tmp_path):
    request, authority, _objective, _constitutional, evidence = _setup()
    result = authorize_and_issue_execution_ticket(
        str(tmp_path),
        "policy_change",
        request,
        ledger=authority,
        evidence=evidence,
    )
    assert result["ok"] is False
    assert result["reason"] == "constitutional_context_missing"
    assert result["ticket"] is None


def test_critical_mutation_requires_full_constitution_and_resource_budget(tmp_path):
    request, authority, objective, constitutional, evidence = _setup()
    budget = allocate_verification_budget(consequence="critical", reversibility="low")
    result = authorize_and_issue_execution_ticket(
        str(tmp_path),
        "policy_change",
        request,
        ledger=authority,
        evidence=evidence,
        constitutional_request=constitutional,
        objective_ledger=objective,
        verification_budget=budget,
        legal_state_ok=True,
        correction_plane_allows=True,
    )
    assert result["ok"] is True
    assert result["constitutional_decision"].allowed is True
    assert result["ticket"] is not None


def test_revoked_objective_blocks_ticket_even_when_claim_evidence_is_strong(tmp_path):
    request, authority, objective, constitutional, evidence = _setup()
    objective.records["obj-1"] = ObjectiveAuthority(
        objective_id="obj-1",
        statement="perform bounded policy change",
        provenance=("user_request",),
        demonstrated_scope=frozenset({request.required_scope}),
        status="REVOKED",
        expires_at_utc=_future(),
    )
    result = authorize_and_issue_execution_ticket(
        str(tmp_path),
        "policy_change",
        request,
        ledger=authority,
        evidence=evidence,
        constitutional_request=constitutional,
        objective_ledger=objective,
        verification_budget=allocate_verification_budget(consequence="critical", reversibility="low"),
    )
    assert result["ok"] is False
    assert result["reason"] == "constitutional_authority_denied"
    assert "objective_authority_missing_or_out_of_scope" in result["constitutional_decision"].reasons


def test_constitutional_scope_cannot_be_weakened_at_ticket_mint(tmp_path):
    request, authority, objective, constitutional, evidence = _setup()
    weaker = ConstitutionalRequest(
        actor=constitutional.actor,
        action_scope="runtime:observe",
        objective_id=constitutional.objective_id,
        authority_id=constitutional.authority_id,
        requested_capability=constitutional.requested_capability,
        consequence=constitutional.consequence,
        reversible=True,
    )
    result = authorize_and_issue_execution_ticket(
        str(tmp_path),
        "policy_change",
        request,
        ledger=authority,
        evidence=evidence,
        constitutional_request=weaker,
        objective_ledger=objective,
        verification_budget=allocate_verification_budget(consequence="critical", reversibility="low"),
    )
    assert result["ok"] is False
    assert result["reason"] == "constitutional_scope_mismatch"


def test_architecture_promotion_blocks_incomplete_runtime_integration():
    candidate = CorrectionCandidate(
        candidate_id="v6",
        target="authority_kernel",
        proposer_id="builder-a",
        provenance=("git-diff",),
        invariant_checks=("tests",),
        pressure_results=("pressure-suite",),
        independent_evaluators=("verifier-b",),
        rollback_reference="branch-v5",
        canary_reference="canary-v6",
        compatibility_reference="compat-v6",
    )
    report = {
        "promotion_permitted": False,
        "requirements": [
            {
                "requirement_id": "main_executor_uses_constitution",
                "satisfied": False,
            }
        ],
    }
    result = evaluate_architecture_promotion(
        candidate=candidate,
        correction_plane=default_correction_plane(),
        critical_invariants_passed=True,
        independent_outcome_verified=True,
        identified_authority_bypasses=0,
        identified_capability_bypasses=0,
        demonstrated_scope=["python_static"],
        unresolved_scope=["runtime_dynamic"],
        runtime_integration_report=report,
    )
    assert result.promote is False
    assert "runtime_authority_integration_incomplete" in result.reasons
    assert "runtime_integration_missing:main_executor_uses_constitution" in result.reasons

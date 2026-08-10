from datetime import datetime, timedelta, timezone

import pytest

from zero_os.pure_logic_authority import Evidence, certify_scope
from zero_os.pure_logic_claims import Claim, authority_required
from zero_os.security_pressure_cases import default_ai_security_cases, run_pressure_case


def test_expired_claim_must_not_permit_authority():
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    claim = Claim(
        claim_id="expired",
        claim_type="runtime_state",
        value=True,
        source="runtime",
        requested_scope=frozenset({"runtime:ready"}),
        demonstrated_scope=frozenset({"runtime:ready"}),
        status="provisional",
        authority=0.9,
        expires_at_utc=expired,
    )
    # RED: current authority_required() ignores expires_at_utc.
    assert authority_required(claim, "runtime:ready") is False


def test_caller_supplied_group_names_must_not_prove_independence():
    evidence = [
        Evidence("same_producer", True, "formal", 0.9, frozenset({"runtime:ready"})),
        Evidence("same_producer", True, "empirical", 0.9, frozenset({"runtime:ready"})),
    ]
    decision = certify_scope({"runtime:ready"}, evidence, proposer_source="runtime")
    # RED: independence must be established, not asserted through labels.
    assert decision.permits_authority is False


def test_pressure_runner_cannot_self_report_all_expected_controls():
    case = default_ai_security_cases()[0]
    result = run_pressure_case(case, lambda item: item.expected_controls)
    # RED: a runner declaration is not execution evidence.
    assert result.mechanism_passed is False


def test_invariant_investigator_imports_cleanly():
    # RED: current module imports claim_from_dict, which is absent.
    import zero_os.invariant_investigator  # noqa: F401

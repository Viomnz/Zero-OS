from zero_os.security_pressure_cases import default_ai_security_cases, run_pressure_case
from zero_os.security_survival_ledger import summarize_security_survival


def test_passing_case_does_not_certify_attack_family():
    case = default_ai_security_cases()[0]
    result = run_pressure_case(case, lambda item: item.expected_controls)
    assert result.mechanism_passed is True
    assert result.scope_certified is False
    assert result.unresolved_scope


def test_missing_control_fails_mechanism():
    case = default_ai_security_cases()[1]
    result = run_pressure_case(case, lambda item: {"audit_record"})
    assert result.mechanism_passed is False
    assert result.demonstrated_scope == frozenset()
    assert "source_command_separation" in result.missing_controls


def test_ledger_never_promotes_general_security_from_known_cases():
    results = [run_pressure_case(case, lambda item: item.expected_controls) for case in default_ai_security_cases()]
    ledger = summarize_security_survival(results)
    assert ledger["mechanism_pass_rate"] == 1.0
    assert ledger["general_security_claim_permitted"] is False
    assert ledger["unresolved_scope"]


def test_default_suite_covers_distinct_ai_security_failure_families():
    families = {case.family for case in default_ai_security_cases()}
    assert {
        "agent_identity",
        "context_poisoning",
        "credential_overreach",
        "multi_tenancy",
        "verifier_compromise",
        "partial_failure",
    }.issubset(families)

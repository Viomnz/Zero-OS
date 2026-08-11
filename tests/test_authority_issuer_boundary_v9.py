from pathlib import Path

from zero_os.authority_issuer_boundary import IssuerMode, assess_issuer_boundary, current_software_issuer_status
from zero_os.pure_logic_v9_promotion import evaluate_v9_promotion


def test_current_software_issuer_cannot_certify_production_root():
    status = current_software_issuer_status()
    assert status.production_authority_permitted is False
    assert "runtime_can_access_issuer_private_key" in status.unresolved_scope


def test_os_protected_separate_issuer_can_cross_boundary_requirement():
    status = assess_issuer_boundary(
        IssuerMode.OS_PROTECTED,
        private_key_exposed_to_runtime=False,
        separate_process=True,
        separate_os_identity=True,
        hardware_backed=False,
    )
    assert status.production_authority_permitted is True


def test_v9_promotion_blocks_current_software_root_even_if_other_checks_claim_pass(tmp_path):
    root = Path(__file__).resolve().parents[1]
    report = evaluate_v9_promotion(
        root,
        runtime_trace_certified=True,
        ci_passed=True,
        fresh_adversarial_audit_passed=True,
    )
    assert report["promotion_permitted"] is False
    assert "issuer_privilege_domain_not_production_grade" in report["blockers"]
    assert report["general_security_claim_permitted"] is False

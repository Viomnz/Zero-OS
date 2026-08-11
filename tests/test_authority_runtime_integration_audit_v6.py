from pathlib import Path

from zero_os.authority_runtime_integration_audit import audit_authority_runtime_integration


def test_v6_identified_runtime_paths_are_constitutionally_integrated():
    root = Path(__file__).resolve().parents[1]
    report = audit_authority_runtime_integration(root)
    missing = [
        item["requirement_id"]
        for item in report["requirements"]
        if not item["satisfied"]
    ]
    assert report["promotion_permitted"] is True, missing
    assert report["critical_failure_count"] == 0
    assert report["high_failure_count"] == 0
    assert report["integration_coverage"] == 1.0


def test_integration_audit_never_claims_runtime_proof():
    root = Path(__file__).resolve().parents[1]
    report = audit_authority_runtime_integration(root)
    assert "symbol_presence_is_not_runtime_reachability_proof" in report["limitations"]
    assert "fresh_adversarial_audit_required" in report["limitations"]

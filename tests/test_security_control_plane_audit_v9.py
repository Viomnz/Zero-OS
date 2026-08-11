from pathlib import Path

from zero_os.security_control_plane_audit import audit_security_control_plane


def test_v9_blocks_promotion_until_legacy_antivirus_controls_are_migrated():
    root = Path(__file__).resolve().parents[1]
    report = audit_security_control_plane(root)
    unresolved = {item["finding_id"] for item in report["findings"] if not item["resolved"]}
    assert report["promotion_permitted"] is False
    assert "legacy_antivirus_deterministic_feed_key" in unresolved
    assert "legacy_antivirus_control_mutators_mediated" in unresolved


def test_v9_new_control_plane_mechanisms_are_present():
    root = Path(__file__).resolve().parents[1]
    report = audit_security_control_plane(root)
    resolved = {item["finding_id"] for item in report["findings"] if item["resolved"]}
    assert "security_control_plane_requires_runtime_handoff" in resolved
    assert "feed_signing_uses_random_control_key" in resolved
    assert "security_controls_inside_correction_plane" in resolved

from pathlib import Path

from zero_os import antivirus
from zero_os.cure_firewall_agent import run_cure_firewall_agent


def test_antivirus_feed_key_must_not_be_derivable_from_public_path(tmp_path):
    key_path = Path(tmp_path) / ".zero_os" / "keys" / "antivirus_feed.key"
    derived_from_path = antivirus.hashlib.sha256(str(key_path).encode("utf-8")).hexdigest().encode("utf-8")
    actual = antivirus._feed_key(str(tmp_path))

    # Current implementation equals this deterministic public derivation.
    assert actual != derived_from_path


def test_cure_firewall_failed_target_must_make_report_not_ok(tmp_path):
    # Missing target forces the underlying file run to fail/survive false.
    report = run_cure_firewall_agent(
        str(tmp_path),
        pressure=100,
        targets=["definitely_missing_target.py"],
        verify=True,
    )

    assert report["issues"]
    assert report["ok"] is False


def test_cure_firewall_partial_scan_must_expose_scope_not_perfect(tmp_path):
    for index in range(30):
        (Path(tmp_path) / f"file_{index:02d}.py").write_text("x = 1\n", encoding="utf-8")

    report = run_cure_firewall_agent(str(tmp_path), pressure=80, verify=True)

    # Current default discovery caps at 25. A partial sample must carry explicit
    # coverage metadata and cannot represent workspace-wide perfection.
    assert report["file_targets"] < 30
    assert "coverage_ratio" in report
    assert report["coverage_ratio"] < 1.0
    assert report["perfect"] is False

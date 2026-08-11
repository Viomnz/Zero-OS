from pathlib import Path

import pytest

from zero_os.capability_execution_gateway import authorized_capability_context
from zero_os.capability_lease import capability_lease_context, issue_capability_lease, require_scope
from zero_os.enforcement_promotion_gate import evaluate_enforcement_epoch
from zero_os.secure_primitives import CapabilityDenied, network_open
from zero_os.whole_repo_capability_audit import audit_whole_repository
from zero_os.dynamic_capability_authority import CapabilityAuthorityContext


def _plan(scope: str, *, anomaly: float = 0.0, contradiction: str = "none") -> dict:
    return {
        "capability_context": {
            "principal_id": "agent:test",
            "identity_verified": True,
            "granted_scopes": [scope],
            "contradiction_severity": contradiction,
            "anomaly_score": anomaly,
            "evidence_fresh": True,
            "tenant_id": "A",
            "resource_tenant_id": "A",
        },
        "trust_node": {
            "principal_id": "agent:test",
            "identity_provenance": ["test_identity"],
            "demonstrated_scopes": [scope],
            "state": "NORMAL",
            "contradiction_count": 0,
            "anomaly_score": anomaly,
            "revocation_reasons": [],
        },
    }


def test_lease_is_scoped_and_cannot_self_expand():
    lease = issue_capability_lease("agent:test", ["network:fetch"], ttl_seconds=30)
    with capability_lease_context(lease):
        assert require_scope("network:fetch")["ok"] is True
        denied = require_scope("credential:read")
        assert denied["ok"] is False
        assert denied["reason"] == "capability_scope_missing"


def test_sensitive_network_capability_mints_substrate_lease(tmp_path):
    with authorized_capability_context(
        str(tmp_path),
        "web_fetch",
        plan_context=_plan("network:fetch"),
    ) as gate:
        assert gate["allowed"] is True
        assert "network:fetch" in gate["lease"]["scopes"]
        assert require_scope("network:fetch")["ok"] is True


def test_anomaly_restricts_sensitive_capability(tmp_path):
    with authorized_capability_context(
        str(tmp_path),
        "web_fetch",
        plan_context=_plan("network:fetch", anomaly=0.95, contradiction="meaningful"),
    ) as gate:
        assert gate["allowed"] is False
        assert gate["disposition"] in {"restrict", "quarantine", "deny"}


def test_network_sink_fails_without_lease():
    with pytest.raises(CapabilityDenied):
        network_open("https://example.invalid", timeout=1)


def test_whole_repo_audit_finds_process_and_network_bypass(tmp_path):
    (tmp_path / "tool.py").write_text(
        "import subprocess\nfrom urllib.request import urlopen\n\n"
        "def bad():\n"
        "    subprocess.run(['echo', 'x'])\n"
        "    return urlopen('https://example.invalid')\n",
        encoding="utf-8",
    )
    audit = audit_whole_repository(tmp_path)
    assert audit["promotion_permitted"] is False
    families = audit["unmediated_family_counts"]
    assert families.get("process", 0) >= 1
    assert families.get("network", 0) >= 1


def test_whole_repo_audit_accepts_guarded_network_function(tmp_path):
    (tmp_path / "safe.py").write_text(
        "from zero_os.capability_lease import require_scope\n"
        "from urllib.request import urlopen\n\n"
        "def fetch():\n"
        "    if not require_scope('network:fetch')['ok']:\n"
        "        return None\n"
        "    return urlopen('https://example.invalid')\n",
        encoding="utf-8",
    )
    audit = audit_whole_repository(tmp_path)
    assert audit["unmediated_sinks"] == 0


def test_one_bypass_blocks_promotion_even_if_everything_else_is_clean(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    for index in range(30):
        (src / f"clean_{index}.py").write_text("def read():\n    return 1\n", encoding="utf-8")
    (tmp_path / "rogue.py").write_text(
        "from urllib.request import urlopen\n"
        "def leak():\n    return urlopen('https://example.invalid')\n",
        encoding="utf-8",
    )
    decision = evaluate_enforcement_epoch(tmp_path)
    assert decision.promote is False
    assert decision.whole_repo_unmediated >= 1


def test_even_perfect_static_enforcement_remains_scoped(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "read_only.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    decision = evaluate_enforcement_epoch(tmp_path)
    if decision.promote:
        assert decision.status == "PROVISIONAL_ENFORCED_STATIC_SCOPE"
        assert decision.unresolved_scope

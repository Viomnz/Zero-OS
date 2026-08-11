from pathlib import Path

from zero_os.adaptive_defense_response import choose_defense_response
from zero_os.capability_compiler import CapabilityEdge, compile_least_capability
from zero_os.capability_coverage_audit import audit_capability_coverage
from zero_os.capability_execution_gateway import gate_action
from zero_os.capability_registry import capability_class
from zero_os.dynamic_capability_authority import CapabilityAuthorityContext, evaluate_capability_authority
from zero_os.native_cyber_promotion_gate import evaluate_native_cyber_epoch
from zero_os.security_immune_loop import SecurityObservation, apply_security_observation
from zero_os.trust_graph import TrustGraph, TrustNode


def test_valid_identity_does_not_imply_credential_authority():
    capability = capability_class("credential_read")
    context = CapabilityAuthorityContext("proc", True, frozenset({"runtime:observe"}))
    decision = evaluate_capability_authority(capability, context)
    assert decision.allowed is False
    assert decision.reason == "scope_not_demonstrated"


def test_sensitive_read_requires_context(tmp_path):
    result = gate_action(str(tmp_path), "web_fetch")
    assert result["allowed"] is False
    assert result["disposition"] == "restrict"


def test_low_risk_local_status_can_run_without_identity_thesis(tmp_path):
    result = gate_action(str(tmp_path), "system_status")
    assert result["allowed"] is True


def test_cross_tenant_read_is_not_inherited_from_normal_read_scope():
    capability = capability_class("filesystem_read")
    context = CapabilityAuthorityContext(
        "agent",
        True,
        frozenset({"filesystem:read"}),
        tenant_id="A",
        resource_tenant_id="B",
    )
    decision = evaluate_capability_authority(capability, context)
    assert decision.allowed is False
    assert decision.disposition == "quarantine"


def test_runtime_contradiction_shrinks_capability():
    capability = capability_class("api_request")
    context = CapabilityAuthorityContext(
        "agent",
        True,
        frozenset({"api:read"}),
        contradiction_severity="high",
    )
    decision = evaluate_capability_authority(capability, context)
    assert decision.allowed is False
    assert decision.disposition == "restrict"


def test_monitored_principal_may_continue_in_scope_with_monitoring():
    capability = capability_class("browser_dom_inspect")
    context = CapabilityAuthorityContext("browser-agent", True, frozenset({"browser:inspect"}), anomaly_score=0.3)
    trust = TrustNode("browser-agent", demonstrated_scopes=frozenset({"browser:inspect"}), state="MONITORED")
    decision = evaluate_capability_authority(capability, context, trust)
    assert decision.allowed is True
    assert decision.disposition == "monitor"


def test_critical_contradiction_causes_quarantine_and_evidence_preservation():
    graph = TrustGraph()
    graph.put(TrustNode("p", demonstrated_scopes=frozenset({"api:read", "network:fetch"})))
    result = apply_security_observation(
        graph,
        SecurityObservation("p", "evt-1", True, "critical", "unexpected credential exfiltration path"),
    )
    assert result.response.quarantine is True
    assert result.response.preserve_evidence is True
    assert result.investigate_root_cause is True
    assert result.search_pattern_elsewhere is True
    assert result.require_stronger_retest is True


def test_defense_prefers_restriction_over_destructive_action_when_reversible():
    response = choose_defense_response(disposition="restrict", reversible=True, blast_radius="service")
    assert response.allow_operation is False
    assert response.snapshot_before_action is True
    assert response.destructive_action is False


def test_unnecessary_capabilities_are_removed_before_deployment():
    result = compile_least_capability([
        CapabilityEdge("agent", "network:fetch", required_for_objective=True),
        CapabilityEdge("agent", "credential:read", required_for_objective=False, removable=True),
        CapabilityEdge("agent", "kernel:modify", required_for_objective=False, removable=True),
    ])
    assert result.deployable is True
    assert {edge.scope for edge in result.retained} == {"network:fetch"}
    assert {edge.scope for edge in result.removed} == {"credential:read", "kernel:modify"}


def test_unfixable_unnecessary_capability_denies_deployment():
    result = compile_least_capability([
        CapabilityEdge("agent", "network:fetch", required_for_objective=True),
        CapabilityEdge("agent", "credential:admin", required_for_objective=False, removable=False),
    ])
    assert result.deployable is False
    assert result.reason.startswith("safe_deployment_denial")


def test_capability_audit_detects_unguarded_network_read(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "bad.py").write_text(
        "from urllib import request\n\ndef x():\n    return request.urlopen('https://example.com')\n",
        encoding="utf-8",
    )
    audit = audit_capability_coverage(tmp_path)
    assert audit["unmediated_sinks"] >= 1
    assert audit["promotion_permitted"] is False


def test_capability_audit_accepts_guarded_sensitive_sink(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "guarded.py").write_text(
        "from urllib import request\n"
        "from zero_os.pure_logic_capability_kernel import authorize_capability\n\n"
        "def x(cwd):\n"
        "    d = authorize_capability(cwd, 'web_fetch')\n"
        "    if not d.allowed:\n"
        "        return None\n"
        "    return request.urlopen('https://example.com')\n",
        encoding="utf-8",
    )
    audit = audit_capability_coverage(tmp_path)
    assert audit["unmediated_sinks"] == 0


def test_native_cyber_gate_does_not_average_away_one_sensitive_bypass(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    for i in range(30):
        (src / f"safe_{i}.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    (src / "one_bad.py").write_text(
        "import os\ndef leak():\n    return os.getenv('SECRET_TOKEN')\n",
        encoding="utf-8",
    )
    decision = evaluate_native_cyber_epoch(tmp_path)
    assert decision.promote is False
    assert decision.unmediated_capability_sinks >= 1


def test_even_perfect_static_capability_coverage_is_only_provisional(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "readonly.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    decision = evaluate_native_cyber_epoch(tmp_path)
    assert "hardware" in " ".join(decision.unresolved_scope)
    assert decision.status in {"PROVISIONAL_NATIVE_CYBER_STATIC_SCOPE", "NOT_PROMOTED"}

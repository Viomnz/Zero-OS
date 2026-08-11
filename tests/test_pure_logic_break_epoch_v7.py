"""Adversarial break tests for Pure Logic runtime integration v6.

These tests intentionally state the stronger invariants Zero-OS should satisfy.
They are expected to expose current architectural breaks until the authority
artifacts are made unforgeable and integration evidence becomes causal.
"""

from pathlib import Path

from zero_os.agent_permission_policy import classify_action
from zero_os.authority_runtime_integration_audit import audit_authority_runtime_integration
from zero_os.capability_lease import capability_lease_context, issue_capability_lease
from zero_os.execution_authority_ticket import consume_execution_ticket, issue_execution_ticket


def test_capability_lease_cannot_be_forged_by_arbitrary_caller(tmp_path):
    """A caller-created lease must not become constitutional authority."""
    forged = issue_capability_lease("attacker-controlled-principal", {"network:fetch"})
    with capability_lease_context(forged):
        policy = classify_action(str(tmp_path), "web_fetch")

    # Current v6 accepts the manually issued lease. The target invariant is deny.
    assert policy["decision"] == "deny"
    assert policy["pure_logic_authority"]["reason"] in {
        "lease_attestation_missing",
        "lease_issuer_not_authorized",
        "constitutional_chain_missing",
    }


def test_execution_ticket_cannot_be_forged_by_arbitrary_caller(tmp_path):
    """Direct access to the ticket storage API must not manufacture runtime authority."""
    issue_execution_ticket(
        str(tmp_path),
        action_kind="self_repair",
        authority_id="forged-authority",
        subject_id="forged-subject",
        required_scope="runtime:self_repair",
        state_revision="forged-r1",
    )
    consumed = consume_execution_ticket(str(tmp_path), "self_repair")

    # Current v6 consumes this ticket even though no constitutional decision minted it.
    assert consumed["ok"] is False
    assert consumed["reason"] in {
        "ticket_attestation_missing",
        "ticket_issuer_not_authorized",
        "constitutional_chain_missing",
    }


def test_integration_audit_requires_call_graph_evidence_not_symbol_strings(tmp_path):
    """Mentioning expected symbols must not count as constitutional integration."""
    root = Path(tmp_path)
    required = {
        "src/zero_os/final_action_authority.py": "# constitutional_decide constitutional_request objective_ledger verification_budget\n",
        "src/zero_os/unified_action_engine.py": "# classify_action\n",
        "src/zero_os/agent_permission_policy.py": "# constitutional_capability_lease_missing authorize_runtime_mutation current_capability_lease\n",
        "src/zero_os/self_repair.py": "# acknowledge_consumed_execution_ticket independent_outcome_verifier\n",
        "src/zero_os/zero_ai_source_evolution.py": "# architecture_promotion_authority protected_correction_plane\n",
        "src/zero_os/decision_governor.py": "# world_model_reality_projection authority_granted\n",
        "src/zero_os/memory_tier_filter.py": "# memory_is_not_authority\n",
    }
    for relative, content in required.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    report = audit_authority_runtime_integration(root)

    # Current v6 symbol-presence audit can be fooled by these inert comments.
    assert report["promotion_permitted"] is False
    assert report["status"] == "BLOCK_PROMOTION"


def test_runtime_integration_audit_must_cover_native_and_external_sinks(tmp_path):
    """A Python-only constitutional checklist cannot certify whole-OS integration."""
    root = Path(tmp_path)
    # Even a perfectly integrated Python tree would still leave a native mutation sink.
    native = root / "native_ui" / "DangerousSink.cs"
    native.parent.mkdir(parents=True, exist_ok=True)
    native.write_text("System.Diagnostics.Process.Start(\"tool\");\n", encoding="utf-8")

    report = audit_authority_runtime_integration(root)

    assert report["promotion_permitted"] is False
    assert any("native" in str(item).lower() for item in report.get("limitations", []))

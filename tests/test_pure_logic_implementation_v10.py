from pathlib import Path

from zero_os.pure_logic_runtime_status import MASTER_LAWS, pure_logic_runtime_status
from zero_os.pure_logic_security_api import policy_set, suppression_add
from zero_os.security_control_plane import load_state


def test_public_security_commands_use_pure_logic_facade():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/zero_os/system_zero_ai_knowledge_security_commands.py").read_text(encoding="utf-8")
    assert "from zero_os.pure_logic_security_api import" in source
    assert "from zero_os.antivirus import (" not in source


def test_antivirus_agent_uses_pure_logic_facade():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/zero_os/antivirus_agent.py").read_text(encoding="utf-8")
    assert "from zero_os.pure_logic_security_api import quarantine_file, scan_target" in source


def test_security_control_mutation_fails_closed_without_authority(tmp_path):
    before = load_state(str(tmp_path))
    policy = policy_set(str(tmp_path), "heuristic_threshold", "10")
    suppression = suppression_add(str(tmp_path), "TEST-SIG")
    after = load_state(str(tmp_path))
    assert policy["ok"] is False
    assert suppression["ok"] is False
    assert after.revision == before.revision
    assert after.antivirus_policy == before.antivirus_policy
    assert after.suppressions == before.suppressions


def test_pure_logic_status_never_self_certifies_general_security(tmp_path):
    report = pure_logic_runtime_status(tmp_path)
    assert tuple(report["master_laws"]) == MASTER_LAWS
    assert report["self_certification_permitted"] is False
    assert report["claims"]["general_security_claim_permitted"] is False
    assert report["unresolved_scope"]


def test_control_plane_validates_before_consuming_authority_contract():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/zero_os/security_control_plane.py").read_text(encoding="utf-8")
    plan_pos = source.index("_plan_mutations(current, normalized)")
    authority_pos = source.index("handoff = _authorized_security_change(cwd)")
    assert plan_pos < authority_pos


def test_runtime_trace_is_wired_to_issuer_and_ticket_sinks():
    root = Path(__file__).resolve().parents[1]
    issuer = (root / "src/zero_os/authority_root_of_trust.py").read_text(encoding="utf-8")
    tickets = (root / "src/zero_os/execution_authority_ticket.py").read_text(encoding="utf-8")
    assert 'event_kind="constitutional_decision"' in issuer
    assert 'event_kind="issuer_attestation"' in issuer
    assert '"runtime_consume"' in tickets
    assert '"sink_acknowledge"' in tickets

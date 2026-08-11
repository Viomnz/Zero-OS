from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from zero_os.authority_ledger import AuthorityLedger, AuthorityRecord, PROVISIONAL, REVOKED
from zero_os.evidence_binding import EvidenceRecord, canonical_fingerprint
from zero_os.execution_authority_ticket import consume_execution_ticket
from zero_os.final_action_authority import ActionAuthorityRequest, authorize_action_and_mint_ticket
from zero_os.mutation_registry import mutation_class
from zero_os.pure_logic_epoch_audit import audit_repository
from zero_os.pure_logic_promotion_gate import evaluate_pure_logic_epoch
from zero_os.pure_logic_runtime_kernel import authorize_runtime_mutation


def _evidence(subject: str, claim_type: str, value, revision: str, scope: str):
    fp = canonical_fingerprint(value)
    return [
        EvidenceRecord(
            evidence_id="formal-1",
            subject_id=subject,
            claim_type=claim_type,
            value_fingerprint=fp,
            state_revision=revision,
            source="formal_checker",
            source_lineage=frozenset({"formal_stack"}),
            method_family="symbolic",
            supports=True,
            scope=frozenset({scope}),
        ),
        EvidenceRecord(
            evidence_id="runtime-1",
            subject_id=subject,
            claim_type=claim_type,
            value_fingerprint=fp,
            state_revision=revision,
            source="runtime_probe",
            source_lineage=frozenset({"runtime_stack"}),
            method_family="empirical",
            supports=True,
            scope=frozenset({scope}),
        ),
    ]


def _ledger(authority_id: str, subject: str, claim_type: str, value, revision: str, scope: str):
    ledger = AuthorityLedger()
    ledger.put(
        AuthorityRecord(
            authority_id=authority_id,
            subject_id=subject,
            claim_type=claim_type,
            value_fingerprint=canonical_fingerprint(value),
            state_revision=revision,
            demonstrated_scope=frozenset({scope}),
            state=PROVISIONAL,
            expires_at_utc=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        )
    )
    return ledger


def test_kernel_rejects_known_mutation_without_ticket(tmp_path):
    decision = authorize_runtime_mutation(str(tmp_path), "code_change")
    assert decision.allowed is False
    assert decision.reason == "fresh_scoped_authority_missing"


def test_kernel_rejects_unknown_mutation_kind(tmp_path):
    decision = authorize_runtime_mutation(str(tmp_path), "invented_write_everything")
    assert decision.allowed is False
    assert decision.reason == "unknown_mutation_kind"


def test_exact_authority_mints_ticket_then_kernel_consumes_once(tmp_path):
    kind = "code_change"
    scope = mutation_class(kind).required_scope
    subject = "repo:zero-os"
    claim_type = "mutation_permission"
    value = {"action": kind, "target": "src/zero_os/example.py"}
    revision = "git:abc123"
    authority_id = "auth:code-change"
    ledger = _ledger(authority_id, subject, claim_type, value, revision, scope)
    request = ActionAuthorityRequest(
        action_id="action:1",
        subject_id=subject,
        claim_type=claim_type,
        claim_value=value,
        state_revision=revision,
        required_scope=scope,
        authority_id=authority_id,
        mutating=True,
    )
    decision = authorize_action_and_mint_ticket(
        str(tmp_path),
        kind,
        request,
        ledger=ledger,
        evidence=_evidence(subject, claim_type, value, revision, scope),
    )
    assert decision.allowed is True

    first = authorize_runtime_mutation(str(tmp_path), kind)
    assert first.allowed is True
    second = authorize_runtime_mutation(str(tmp_path), kind)
    assert second.allowed is False


def test_ticket_scope_cannot_authorize_different_mutation(tmp_path):
    kind = "code_change"
    scope = mutation_class(kind).required_scope
    subject = "repo:zero-os"
    claim_type = "mutation_permission"
    value = {"action": kind}
    revision = "r1"
    authority_id = "auth:scope"
    ledger = _ledger(authority_id, subject, claim_type, value, revision, scope)
    request = ActionAuthorityRequest(
        action_id="a",
        subject_id=subject,
        claim_type=claim_type,
        claim_value=value,
        state_revision=revision,
        required_scope=scope,
        authority_id=authority_id,
    )
    assert authorize_action_and_mint_ticket(
        str(tmp_path), kind, request, ledger=ledger,
        evidence=_evidence(subject, claim_type, value, revision, scope),
    ).allowed
    other = authorize_runtime_mutation(str(tmp_path), "cloud_deploy")
    assert other.allowed is False


def test_revoked_dependency_blocks_action(tmp_path):
    scope = mutation_class("code_change").required_scope
    subject = "repo:zero-os"
    claim_type = "mutation_permission"
    value = {"action": "code_change"}
    revision = "r1"
    ledger = AuthorityLedger()
    ledger.put(
        AuthorityRecord(
            authority_id="verifier",
            subject_id="verifier",
            claim_type="verifier_authority",
            value_fingerprint=canonical_fingerprint(True),
            state_revision="v1",
            demonstrated_scope=frozenset({"verification:code"}),
            state=REVOKED,
        )
    )
    ledger.put(
        AuthorityRecord(
            authority_id="action",
            subject_id=subject,
            claim_type=claim_type,
            value_fingerprint=canonical_fingerprint(value),
            state_revision=revision,
            demonstrated_scope=frozenset({scope}),
            state=PROVISIONAL,
            dependencies=frozenset({"verifier"}),
        )
    )
    request = ActionAuthorityRequest(
        action_id="a",
        subject_id=subject,
        claim_type=claim_type,
        claim_value=value,
        state_revision=revision,
        required_scope=scope,
        authority_id="action",
    )
    decision = authorize_action_and_mint_ticket(
        str(tmp_path), "code_change", request, ledger=ledger,
        evidence=_evidence(subject, claim_type, value, revision, scope),
    )
    assert decision.allowed is False


def test_audit_blocks_unmediated_filesystem_mutation(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "unsafe.py").write_text(
        "from pathlib import Path\n\ndef mutate():\n    Path('x').write_text('danger')\n",
        encoding="utf-8",
    )
    audit = audit_repository(tmp_path)
    assert audit["promotion_permitted"] is False
    assert audit["unmediated_candidates"] >= 1


def test_audit_recognizes_function_with_authority_check(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "safe.py").write_text(
        "from pathlib import Path\n"
        "from zero_os.pure_logic_runtime_kernel import authorize_runtime_mutation\n\n"
        "def mutate(cwd):\n"
        "    d = authorize_runtime_mutation(cwd, 'code_change')\n"
        "    if not d.allowed:\n"
        "        return False\n"
        "    Path('x').write_text('ok')\n"
        "    return True\n",
        encoding="utf-8",
    )
    audit = audit_repository(tmp_path)
    assert audit["unmediated_candidates"] == 0


def test_promotion_gate_refuses_average_score_laundering(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    for index in range(20):
        (src / f"safe_{index}.py").write_text("def read_only():\n    return 1\n", encoding="utf-8")
    (src / "one_bad_sink.py").write_text(
        "from pathlib import Path\ndef bad():\n    Path('x').unlink()\n",
        encoding="utf-8",
    )
    decision = evaluate_pure_logic_epoch(tmp_path)
    assert decision.promote is False
    assert decision.unmediated_mutations >= 1


def test_even_perfect_static_coverage_is_not_global_security_claim(tmp_path):
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "read_only.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    decision = evaluate_pure_logic_epoch(tmp_path)
    assert decision.promote is True
    assert decision.status == "PROVISIONAL_STATIC_SCOPE"
    assert decision.unresolved_scope

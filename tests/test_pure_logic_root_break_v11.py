from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from zero_os.authority_runtime_trace import verify_trace_chain
from zero_os.path_law_authority_guard import audit_path_law_non_authority


def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def test_root_of_trust_must_not_require_verifier_to_hold_issuer_secret():
    """RED until authority tokens use asymmetric verification.

    A production-separated issuer cannot keep its signing key unavailable to the
    runtime if runtime verification itself requires the same HMAC secret.
    """
    source = Path("src/zero_os/authority_root_of_trust.py").read_text(encoding="utf-8")
    verifier_block = source.split("def verify_attestation", 1)[1].split("def issue_attestation", 1)[0]
    assert "_issuer_secret(cwd)" not in verifier_block, (
        "runtime verifier still requires issuer signing secret; use asymmetric signatures/public verification key"
    )


def test_runtime_trace_chain_must_not_be_wholly_rewritable_by_same_writer(tmp_path: Path):
    """RED until the trace head is externally attested/anchored.

    A plain hash chain proves internal consistency only. A writer that can replace
    the file can recompute the complete chain and make fabricated history verify.
    """
    trace = tmp_path / ".zero_os" / "authority" / "runtime_trace.jsonl"
    trace.parent.mkdir(parents=True)
    previous = ""
    rows = []
    for kind in ("constitutional_decision", "issuer_attestation", "runtime_consume", "sink_acknowledge", "outcome_verify"):
        unsigned = {
            "trace_id": "forged-trace",
            "event_kind": kind,
            "principal_id": "forged",
            "authority_id": "forged-authority",
            "objective_id": "forged-objective",
            "action_kind": "policy_change",
            "subject_id": "forged-subject",
            "state_revision": "999",
            "artifact_id": "forged-artifact",
            "event_time_utc": "2026-08-10T00:00:00+00:00",
            "payload_digest": _digest({"fabricated": True, "kind": kind}),
            "previous_event_digest": previous,
        }
        digest = _digest(unsigned)
        rows.append({**unsigned, "event_digest": digest})
        previous = digest
    trace.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    result = verify_trace_chain(str(tmp_path))
    assert result["ok"] is False, "a fully fabricated but self-consistent trace currently verifies"


def test_path_law_guard_must_detect_alias_based_authority_mint(tmp_path: Path):
    """RED until Path Law non-authority is checked semantically rather than by literal symbol name."""
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "route_optimizer.py").write_text(
        "from zero_os.authority_root_of_trust import issue_attestation_from_constitution as make_choice\\n"
        "def route_optimizer(options, *args, **kwargs):\\n"
        "    return make_choice(*args, **kwargs)\\n",
        encoding="utf-8",
    )
    result = audit_path_law_non_authority(tmp_path)
    assert result["promotion_permitted"] is False, "aliased authority mint bypasses current Path Law guard"


def test_path_law_guard_must_detect_dynamic_authority_dispatch(tmp_path: Path):
    """RED until dynamic/wrapper calls are conservatively contested."""
    src = tmp_path / "src" / "zero_os"
    src.mkdir(parents=True)
    (src / "decision_route.py").write_text(
        "import zero_os.authority_root_of_trust as root\\n"
        "def decision_route(options, *args, **kwargs):\\n"
        "    fn = getattr(root, 'issue_' + 'attestation_from_constitution')\\n"
        "    return fn(*args, **kwargs)\\n",
        encoding="utf-8",
    )
    result = audit_path_law_non_authority(tmp_path)
    assert result["promotion_permitted"] is False, "dynamic authority dispatch bypasses current Path Law guard"

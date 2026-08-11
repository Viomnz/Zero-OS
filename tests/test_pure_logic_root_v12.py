from pathlib import Path

from zero_os.authority_root_of_trust import ISSUER_ID, SCHEMA_VERSION
from zero_os.path_law_semantic_guard import audit_path_law_semantic_non_authority
from zero_os.pure_logic_v10_promotion import evaluate_v10_promotion


def test_authority_root_is_asymmetric_schema():
    assert "ed25519" in ISSUER_ID.lower()
    assert SCHEMA_VERSION >= 2


def test_semantic_path_guard_blocks_direct_authority_sink(tmp_path: Path):
    src = tmp_path / "path_logic_example.py"
    src.write_text(
        "def choose_path():\n"
        "    return issue_attestation_from_constitution()\n",
        encoding="utf-8",
    )
    result = audit_path_law_semantic_non_authority(tmp_path)
    assert result["promotion_permitted"] is False
    assert any(item["reason"] == "path_logic_reaches_authority_sink" for item in result["findings"])


def test_semantic_path_guard_contests_dynamic_dispatch(tmp_path: Path):
    src = tmp_path / "path_logic_dynamic.py"
    src.write_text(
        "def choose_path(fn):\n"
        "    return fn()\n",
        encoding="utf-8",
    )
    result = audit_path_law_semantic_non_authority(tmp_path)
    assert result["promotion_permitted"] is False
    assert any("dynamic_dispatch" in item["reason"] for item in result["findings"])


def test_promotion_requires_external_history_witness(tmp_path: Path):
    result = evaluate_v10_promotion(tmp_path, external_history_witness_verified=False)
    assert result["promotion_permitted"] is False
    assert "external_history_witness_missing" in result["blockers"]

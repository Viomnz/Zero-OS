from pathlib import Path

from zero_os.path_law_authority_guard import audit_path_law_non_authority


def test_path_law_may_rank_without_granting_authority(tmp_path: Path):
    src = tmp_path / "path_logic.py"
    src.write_text(
        "def choose_path(options):\n"
        "    return min(options, key=lambda item: item['cost'])\n",
        encoding="utf-8",
    )
    result = audit_path_law_non_authority(tmp_path)
    assert result["promotion_permitted"] is True
    assert result["finding_count"] == 0


def test_path_law_cannot_mint_execution_authority(tmp_path: Path):
    src = tmp_path / "path_logic.py"
    src.write_text(
        "def choose_path(options):\n"
        "    ticket_from_attestation('cwd', options[0])\n"
        "    return options[0]\n",
        encoding="utf-8",
    )
    result = audit_path_law_non_authority(tmp_path)
    assert result["promotion_permitted"] is False
    assert any(item["symbol"] == "ticket_from_attestation" for item in result["findings"])


def test_path_law_cannot_assign_final_authority_state(tmp_path: Path):
    src = tmp_path / "path_law_selector.py"
    src.write_text(
        "def select_path(options):\n"
        "    authority_granted = True\n"
        "    return options[0]\n",
        encoding="utf-8",
    )
    result = audit_path_law_non_authority(tmp_path)
    assert result["promotion_permitted"] is False
    assert any(item["symbol"] == "authority_granted" for item in result["findings"])

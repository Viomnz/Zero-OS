from __future__ import annotations

import json
from pathlib import Path


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sig = _load(root / "security" / "artifacts" / "artifact_signatures.json")
    contracts = _load(root / "zero_os_config" / "release_contracts.json")
    if not isinstance(sig, dict):
        print("release verify failed: missing artifact_signatures.json")
        return 2
    records = sig.get("records", [])
    if not isinstance(records, list) or len(records) == 0:
        print("release verify failed: no signed artifacts")
        return 3
    if not isinstance(contracts, dict) or not isinstance(contracts.get("contracts", []), list):
        print("release verify failed: invalid release_contracts.json")
        return 4
    print("release verify passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

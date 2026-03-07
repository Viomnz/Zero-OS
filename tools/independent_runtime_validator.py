from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.runtime_coupling import independent_validate


def main() -> int:
    out = independent_validate(str(ROOT))
    print(out)
    return 0 if out.get("ok", False) else 2


if __name__ == "__main__":
    raise SystemExit(main())

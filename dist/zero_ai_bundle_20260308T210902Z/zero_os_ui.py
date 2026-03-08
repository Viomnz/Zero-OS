from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    base = Path(__file__).resolve().parent
    sys.path.insert(0, str(base / "src"))
    from zero_os.universal_ui_launcher import cli

    return cli()


if __name__ == "__main__":
    raise SystemExit(main())

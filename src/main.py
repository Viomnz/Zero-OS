from __future__ import annotations

import argparse
import os
import sys

from zero_os.highway import Highway


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Zero OS Main Highway")
    parser.add_argument("task", help="Natural-language task for Zero OS")
    args = parser.parse_args()

    cwd = os.getcwd()
    result = Highway(cwd=cwd).dispatch(args.task, cwd=cwd)
    print(f"lane={result.capability}")
    print(result.summary)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import os

from zero_os.highway import Highway


def main() -> None:
    parser = argparse.ArgumentParser(description="Zero OS Main Highway")
    parser.add_argument("task", help="Natural-language task for Zero OS")
    args = parser.parse_args()

    result = Highway().dispatch(args.task, cwd=os.getcwd())
    print(f"lane={result.capability}")
    print(result.summary)


if __name__ == "__main__":
    main()

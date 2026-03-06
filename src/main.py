from __future__ import annotations

import argparse
import os
import sys

from zero_os.highway import Highway
from zero_os.readiness import os_readiness
from zero_os.compute_runtime import initialize_compute_runtime
from zero_os.state import get_profile_setting


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Zero OS Main Highway")
    parser.add_argument("task", help="Natural-language task for Zero OS")
    args = parser.parse_args()

    cwd = os.getcwd()
    initialize_compute_runtime(cwd, get_profile_setting(cwd))
    min_score = int(os.getenv("ZERO_OS_BOOT_MIN_SCORE", "0"))
    if min_score > 0:
        readiness = os_readiness(cwd)
        if readiness["score"] < min_score and args.task.strip().lower() not in {
            "os readiness",
            "os readiness --json",
            "os missing fix",
        }:
            print("lane=core")
            print(
                "boot blocked: os readiness below threshold\n"
                f"required_score={min_score}\n"
                f"current_score={readiness['score']}\n"
                "run: os missing fix"
            )
            raise SystemExit(2)

    result = Highway(cwd=cwd).dispatch(args.task, cwd=cwd)
    print(f"lane={result.capability}")
    print(result.summary)


if __name__ == "__main__":
    main()

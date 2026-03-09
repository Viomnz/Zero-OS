from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from zero_os.phase_runtime import zero_ai_runtime_agent_worker_run

    parser = argparse.ArgumentParser(description="Zero OS Runtime Agent")
    parser.add_argument("--cwd", default=str(root), help="Workspace root for the Zero OS runtime")
    parser.add_argument("--poll", type=int, default=30, help="Agent heartbeat interval in seconds")
    args = parser.parse_args()

    zero_ai_runtime_agent_worker_run(args.cwd, poll_seconds=args.poll)


if __name__ == "__main__":
    main()

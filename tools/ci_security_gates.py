from __future__ import annotations

import argparse
import subprocess
import sys


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd).returncode


def commands_for_profile(profile: str) -> list[list[str]]:
    if profile == "ci":
        return [
            [sys.executable, "tools/security_gate.py", "--profile", "ci"],
        ]
    raise ValueError(f"unsupported CI security gate profile: {profile}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fast CI security gate bundle.")
    parser.add_argument("--profile", choices=("ci",), default="ci")
    args = parser.parse_args(argv)
    cmds = commands_for_profile(args.profile)
    for cmd in cmds:
        rc = _run(cmd)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

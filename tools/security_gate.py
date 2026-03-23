from __future__ import annotations

import argparse
import subprocess
import sys


def run(cmd: list[str]) -> int:
    print("running:", " ".join(cmd), flush=True)
    p = subprocess.run(cmd)
    if p.returncode != 0:
        print(f"failed: {' '.join(cmd)} (exit {p.returncode})", file=sys.stderr, flush=True)
    return p.returncode


def suites_for_profile(profile: str) -> list[list[str]]:
    focused_security_suite = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_antivirus_system",
        "tests.test_quantum_virus_curefirewall",
        "tests.test_security_core",
        "tests.test_security_integrity_layer",
        "tests.test_security_tooling",
        "tests.test_enterprise_security",
        "tests.test_zero_ai_gate",
        "-q",
    ]
    if profile == "ci":
        return [focused_security_suite]
    if profile == "maturity":
        return [focused_security_suite]
    if profile == "full":
        return [
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-q"],
            focused_security_suite,
        ]
    raise ValueError(f"unsupported security gate profile: {profile}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Zero OS security-focused test gates.")
    parser.add_argument(
        "--profile",
        choices=("ci", "maturity", "full"),
        default="maturity",
        help="Gate profile to run. 'full' preserves the older broad test-discover behavior.",
    )
    args = parser.parse_args(argv)
    suites = suites_for_profile(args.profile)
    print(f"security gate profile: {args.profile}", flush=True)
    for cmd in suites:
        rc = run(cmd)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

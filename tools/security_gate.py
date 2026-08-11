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
    focused_unittest_suite = [
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
    focused_pytest_regressions = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_sink_enforcement_v28.py",
        "tests/test_zero_os_cleanup_v30.py",
    ]
    if profile in {"ci", "maturity"}:
        return [focused_unittest_suite, focused_pytest_regressions]
    if profile == "full":
        # Pytest executes both unittest.TestCase suites and plain pytest tests,
        # so the full profile can no longer silently skip function-style tests.
        return [[sys.executable, "-m", "pytest", "-q", "tests"]]
    raise ValueError(f"unsupported security gate profile: {profile}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Zero OS security-focused test gates.")
    parser.add_argument(
        "--profile",
        choices=("ci", "maturity", "full"),
        default="maturity",
        help="Gate profile to run. 'full' executes the complete pytest suite, including unittest-compatible tests.",
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

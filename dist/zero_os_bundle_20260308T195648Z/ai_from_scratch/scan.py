from __future__ import annotations

import json
import py_compile
import subprocess
from pathlib import Path


def run_scan(base: Path) -> dict:
    src_files = [p for p in base.rglob("*.py") if ".git" not in str(p) and ".zero_os" not in str(p)]

    syntax_errors = []
    for f in src_files:
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            syntax_errors.append({"file": str(f), "error": str(e)})

    test_cmd = ["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]
    proc = subprocess.run(test_cmd, cwd=str(base), capture_output=True, text=True)

    report = {
        "syntax_error_count": len(syntax_errors),
        "syntax_errors": syntax_errors,
        "tests_exit_code": proc.returncode,
        "tests_passed": proc.returncode == 0,
        "tests_stdout_tail": "\n".join(proc.stdout.splitlines()[-30:]),
        "tests_stderr_tail": "\n".join(proc.stderr.splitlines()[-30:]),
    }

    rt = base / ".zero_os" / "runtime"
    rt.mkdir(parents=True, exist_ok=True)
    (rt / "zero_ai_scan_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

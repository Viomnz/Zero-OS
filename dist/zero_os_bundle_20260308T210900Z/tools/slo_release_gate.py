from __future__ import annotations

import json
from pathlib import Path
import subprocess


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def main() -> int:
    root = Path.cwd()
    targets = _load(root / "zero_os_config" / "top_user_choice_targets.json", {})
    required = targets.get("required_artifacts", []) if isinstance(targets, dict) else []
    # Generate required runtime artifacts when possible before final gating.
    generators = {
        ".zero_os/runtime/triad_balance.json": ["python", "src/main.py", "triad balance run"],
        ".zero_os/runtime/independent_runtime_validation.json": ["python", "tools/independent_runtime_validator.py"],
        ".zero_os/runtime/zero_ai_recovery_report.json": ["python", "src/main.py", "zero ai recover"],
    }
    for rel, cmd in generators.items():
        p = root / rel
        if not p.exists():
            subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)

    missing = []
    for rel in required:
        p = root / str(rel)
        if not p.exists():
            missing.append(str(rel))

    iv = _load(root / ".zero_os" / "runtime" / "independent_runtime_validation.json", {})
    triad = _load(root / ".zero_os" / "runtime" / "triad_balance.json", {})
    checks = {
        "required_artifacts_present": len(missing) == 0,
        "runtime_validation_ok": bool(iv.get("ok", False)),
        "triad_balanced": bool(triad.get("balanced", False)),
    }
    ok = all(checks.values())
    report = {
        "ok": ok,
        "checks": checks,
        "missing_artifacts": missing,
    }
    print(json.dumps(report))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

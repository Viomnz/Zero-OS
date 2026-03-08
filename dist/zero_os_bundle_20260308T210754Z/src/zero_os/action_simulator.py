from __future__ import annotations


def simulate_action(action: str, checks: dict[str, bool], dry_run_supported: bool = True) -> dict:
    failed = sorted(name for name, ok in checks.items() if not ok)
    success = dry_run_supported and not failed
    impact = "contained" if success else "uncertain"
    return {
        "ok": success,
        "dry_run_supported": bool(dry_run_supported),
        "failed_checks": failed,
        "predicted_impact": impact,
    }

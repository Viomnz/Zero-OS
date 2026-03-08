from __future__ import annotations

from typing import Any, Callable

from zero_os.enterprise_security import enterprise_status
from zero_os.gap_coverage import zero_ai_gap_fix, zero_ai_gap_status, zero_ai_upgrade_system
from zero_os.maturity import maturity_scaffold_all, maturity_status
from zero_os.native_platform import maximize as native_platform_maximize
from zero_os.ops_maturity import enterprise_max_maturity_apply
from zero_os.production_platform_ops import maximize as production_platform_maximize
from zero_os.readiness import apply_beginner_os_fix, apply_missing_fix, beginner_os_coverage, os_readiness
from zero_os.real_os_status import real_os_status
from zero_os.security_hardening import harden_apply, zero_ai_security_apply
from zero_os.share_bundle import export_bundle, export_zero_ai_bundle_strict, share_package, share_zero_ai_package_strict


def auto_max_fix_upgrade_everything(cwd: str, max_passes: int = 3) -> dict[str, Any]:
    passes: list[dict[str, Any]] = []
    final_summary: dict[str, Any] = {}

    for index in range(1, max(1, int(max_passes)) + 1):
        current: dict[str, Any] = {"pass": index, "actions": []}

        _record(current, "os_missing_fix", lambda: apply_missing_fix(cwd))
        _record(current, "beginner_os_fix", lambda: apply_beginner_os_fix(cwd))
        _record(current, "security_harden", lambda: harden_apply(cwd))
        _record(current, "zero_ai_security_apply", lambda: zero_ai_security_apply(cwd))
        _record(current, "maturity_scaffold_all", lambda: maturity_scaffold_all(cwd))
        _record(current, "zero_ai_gap_fix", lambda: zero_ai_gap_fix(cwd))
        _record(current, "zero_ai_upgrade_system", lambda: zero_ai_upgrade_system(cwd))
        _record(current, "enterprise_max_maturity_apply", lambda: enterprise_max_maturity_apply(cwd))
        _record(current, "native_platform_maximize", lambda: native_platform_maximize(cwd))
        _record(current, "production_platform_maximize", lambda: production_platform_maximize(cwd, "ZeroOS", "1.0.0"))
        _record(current, "zero_os_export_bundle", lambda: export_bundle(cwd))
        _record(current, "zero_os_share_package", lambda: share_package(cwd))
        _record(current, "zero_ai_export_bundle_strict", lambda: export_zero_ai_bundle_strict(cwd))
        _record(current, "zero_ai_share_package_strict", lambda: share_zero_ai_package_strict(cwd))

        final_summary = {
            "readiness": os_readiness(cwd),
            "beginner_os": beginner_os_coverage(cwd),
            "real_os": real_os_status(cwd),
            "maturity": maturity_status(cwd),
            "zero_ai_gap": zero_ai_gap_status(cwd),
            "enterprise_security": enterprise_status(cwd),
        }
        current["summary"] = final_summary
        current["complete"] = _is_complete(final_summary)
        passes.append(current)

        if current["complete"]:
            break

    return {
        "ok": _is_complete(final_summary),
        "max_passes": max_passes,
        "passes_run": len(passes),
        "passes": passes,
        "final_summary": final_summary,
    }


def _record(container: dict[str, Any], name: str, fn: Callable[[], Any]) -> None:
    try:
        result = fn()
        container["actions"].append({"name": name, "ok": True, "result": result})
    except Exception as exc:  # pragma: no cover - defensive aggregator
        container["actions"].append({"name": name, "ok": False, "error": str(exc)})


def _is_complete(summary: dict[str, Any]) -> bool:
    readiness = float(summary.get("readiness", {}).get("score", 0))
    beginner = float(summary.get("beginner_os", {}).get("score", 0))
    real_os = float(summary.get("real_os", {}).get("real_os_readiness_score", 0))
    maturity = bool(summary.get("maturity", {}).get("perfect", False))
    zero_ai = bool(summary.get("zero_ai_gap", {}).get("maximized", False))
    enterprise = bool(summary.get("enterprise_security", {}).get("enabled", False) or summary.get("enterprise_security", {}).get("ok", False))
    return readiness >= 100 and beginner >= 100 and real_os >= 100 and maturity and zero_ai and enterprise

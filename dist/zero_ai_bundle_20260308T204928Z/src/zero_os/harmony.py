from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.triad_balance import run_triad_balance, triad_balance_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def zero_ai_harmony_status(cwd: str, autocorrect: bool = True) -> dict:
    rt = _runtime(cwd)
    triad = triad_balance_status(cwd)
    if triad.get("missing", False) and autocorrect:
        triad = run_triad_balance(cwd)

    policy = _read_json(rt / "smart_logic_policy.json")
    gate = _read_json(rt / "zero_ai_gate_state.json")
    reasoner = _read_json(rt / "internal_zero_reasoner_state.json")
    monitor = _read_json(rt / "agents_monitor.json")

    policy_ok = bool((policy.get("engines", {}) or {}).get("zero_ai_gate_smart_logic_v1")) and bool(
        (policy.get("engines", {}) or {}).get("zero_ai_internal_smart_logic_v1")
    )
    generation_gap = abs(int(gate.get("model_generation", 1)) - int(reasoner.get("model_generation", 1)))

    checks = {
        "triad_balanced": bool(triad.get("balanced", False)),
        "smart_logic_policy_loaded": policy_ok,
        "agents_monitor_present": bool(monitor),
        "gate_reasoner_generation_aligned": generation_gap <= 2,
    }
    issues = [k for k, v in checks.items() if not v]
    score = round((sum(1 for v in checks.values() if v) / max(1, len(checks))) * 100, 2)
    report = {
        "ok": True,
        "time_utc": _utc_now(),
        "harmony_score": score,
        "harmonized": score == 100.0 and len(issues) == 0,
        "checks": checks,
        "issues": issues,
        "details": {
            "triad_score": triad.get("triad_score"),
            "triad_system_score": triad.get("system_score"),
            "gate_model_generation": int(gate.get("model_generation", 1)),
            "reasoner_model_generation": int(reasoner.get("model_generation", 1)),
            "generation_gap": generation_gap,
            "smart_logic_policy_path": str(rt / "smart_logic_policy.json"),
        },
    }
    (rt / "zero_ai_harmony.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


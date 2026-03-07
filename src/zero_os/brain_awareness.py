from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.harmony import zero_ai_harmony_status
from zero_os.knowledge_map import build_knowledge_index, knowledge_status
from zero_os.maturity import maturity_status
from zero_os.recovery import zero_ai_backup_status
from zero_os.security_hardening import zero_ai_security_status
from zero_os.consciousness_core import consciousness_status, consciousness_tick


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def build_brain_awareness(cwd: str) -> dict:
    build_knowledge_index(cwd)
    knowledge = knowledge_status(cwd)
    harmony = zero_ai_harmony_status(cwd, autocorrect=True)
    security = zero_ai_security_status(cwd)
    maturity = maturity_status(cwd)
    backup = zero_ai_backup_status(cwd)
    consciousness = consciousness_tick(cwd, prompt="brain awareness synchronization cycle")

    checks = {
        "knowledge_index_ready": bool(knowledge.get("ok", False)),
        "harmony_ready": bool(harmony.get("harmonized", False)),
        "security_hardened": bool(security.get("hardened", False)),
        "maturity_perfect": bool(maturity.get("perfect", False)),
        "backup_ready": int(backup.get("snapshot_count", 0)) >= 1 or bool(backup.get("cure_firewall_backup_exists", False)),
        "consciousness_ready": bool(consciousness.get("ok", False)),
    }
    score = round((sum(1 for v in checks.values() if v) / max(1, len(checks))) * 100, 2)
    issues = [k for k, v in checks.items() if not v]
    actions = []
    if not checks["backup_ready"]:
        actions.append("run: zero ai backup create")
    if not checks["security_hardened"]:
        actions.append("run: zero ai security apply")
    if not checks["maturity_perfect"]:
        actions.append("run: maturity scaffold all")
    if not checks["consciousness_ready"]:
        actions.append("run: zero ai consciousness tick")

    out = {
        "ok": True,
        "time_utc": _utc_now(),
        "brain_awareness_score": score,
        "aware": score == 100.0 and not issues,
        "checks": checks,
        "issues": issues,
        "suggested_actions": actions,
        "signals": {
            "knowledge": knowledge,
            "harmony": {"harmony_score": harmony.get("harmony_score"), "harmonized": harmony.get("harmonized")},
            "security": {
                "zero_ai_security_score": security.get("zero_ai_security_score"),
                "zero_ai_security_total": security.get("zero_ai_security_total"),
                "hardened": security.get("hardened"),
            },
            "maturity": {"score": maturity.get("score"), "perfect": maturity.get("perfect")},
            "backup": backup,
            "consciousness": {
                "continuity_index": consciousness.get("self_model", {}).get("continuity_index"),
                "introspection_cycles": consciousness.get("meta_awareness", {}).get("introspection_cycles"),
                "last_quality_score": consciousness.get("meta_awareness", {}).get("last_quality_score"),
            },
        },
    }
    (_runtime(cwd) / "zero_ai_brain_awareness.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def brain_awareness_status(cwd: str) -> dict:
    p = _runtime(cwd) / "zero_ai_brain_awareness.json"
    if not p.exists():
        return {"ok": False, "missing": True, "hint": "run: zero ai brain awareness build"}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "missing": True, "hint": "run: zero ai brain awareness build"}

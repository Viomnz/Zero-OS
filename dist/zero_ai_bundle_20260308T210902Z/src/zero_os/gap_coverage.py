from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.brain_awareness import brain_awareness_status, build_brain_awareness
from zero_os.consciousness_core import consciousness_status, consciousness_tick
from zero_os.harmony import zero_ai_harmony_status
from zero_os.knowledge_map import build_knowledge_index, knowledge_status
from zero_os.maturity import maturity_scaffold_all, maturity_status
from zero_os.recovery import zero_ai_backup_create, zero_ai_backup_status
from zero_os.security_hardening import zero_ai_security_apply, zero_ai_security_status
from zero_os.triad_balance import run_triad_balance


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _find_any(root: Path, patterns: list[str]) -> str:
    for pattern in patterns:
        for match in root.glob(pattern):
            if match.is_file():
                return str(match)
    return ""


def _align_generation_state(cwd: str) -> dict:
    rt = _runtime(cwd)
    gate_path = rt / "zero_ai_gate_state.json"
    reasoner_path = rt / "internal_zero_reasoner_state.json"

    def _load(path: Path, default: dict) -> dict:
        if not path.exists():
            return dict(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return dict(default)

    gate = _load(gate_path, {"model_generation": 1})
    reasoner = _load(reasoner_path, {"model_generation": 1, "profile": "balanced", "mode": "stability"})
    target = max(int(gate.get("model_generation", 1)), int(reasoner.get("model_generation", 1)))
    gate["model_generation"] = target
    reasoner["model_generation"] = target
    gate_path.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    reasoner_path.write_text(json.dumps(reasoner, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "aligned_model_generation": target}


def _bump_generation_state(cwd: str, reason: str = "zero ai system upgrade") -> dict:
    rt = _runtime(cwd)
    gate_path = rt / "zero_ai_gate_state.json"
    reasoner_path = rt / "internal_zero_reasoner_state.json"

    def _load(path: Path, default: dict) -> dict:
        if not path.exists():
            return dict(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return dict(default)

    gate = _load(gate_path, {"model_generation": 1})
    reasoner = _load(reasoner_path, {"model_generation": 1, "profile": "balanced", "mode": "stability"})
    previous = max(int(gate.get("model_generation", 1)), int(reasoner.get("model_generation", 1)))
    upgraded = previous + 1
    gate["model_generation"] = upgraded
    reasoner["model_generation"] = upgraded
    reasoner["last_upgrade_reason"] = reason
    reasoner["last_upgrade_utc"] = _utc_now()
    gate_path.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    reasoner_path.write_text(json.dumps(reasoner, indent=2) + "\n", encoding="utf-8")
    report = {
        "ok": True,
        "previous_model_generation": previous,
        "upgraded_model_generation": upgraded,
        "reason": reason,
        "time_utc": _utc_now(),
    }
    (rt / "zero_ai_upgrade_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def zero_ai_gap_status(cwd: str) -> dict:
    runtime_root = _runtime(cwd)
    workspace_root = Path(cwd).resolve()
    mat = maturity_status(cwd)
    sec = zero_ai_security_status(cwd)
    backup = zero_ai_backup_status(cwd)
    know = knowledge_status(cwd)
    con = consciousness_status(cwd)
    harm = zero_ai_harmony_status(cwd, autocorrect=False)
    brain = brain_awareness_status(cwd)
    detected_paths = {
        "knowledge_index": _find_any(
            runtime_root,
            [
                "zero_ai_knowledge_index.json",
                "*knowledge*index*.json",
            ],
        ),
        "brain_awareness": _find_any(
            runtime_root,
            [
                "zero_ai_brain_awareness.json",
                "*brain*awareness*.json",
            ],
        ),
        "consciousness_state": _find_any(
            runtime_root,
            [
                "zero_ai_consciousness_state.json",
                "*consciousness*state*.json",
            ],
        ),
        "consciousness_ledger": _find_any(
            runtime_root,
            [
                "zero_ai_consciousness_ledger.jsonl",
                "*consciousness*ledger*.jsonl",
            ],
        ),
        "backup_snapshot": _find_any(
            workspace_root / ".zero_os" / "production" / "snapshots",
            [
                "*/snapshot.json",
            ],
        ),
    }

    checks = {
        "maturity_perfect": bool(mat.get("perfect", False)),
        "security_hardened": bool(sec.get("hardened", False)),
        "backup_ready": (
            int(backup.get("snapshot_count", 0)) > 0
            or bool(backup.get("cure_firewall_backup_exists", False))
            or bool(detected_paths["backup_snapshot"])
        ),
        "knowledge_ready": bool(know.get("ok", False)) or bool(detected_paths["knowledge_index"]),
        "consciousness_ready": (
            bool(con.get("ok", False)) and int(con.get("ledger_events", 0)) > 0
        ) or bool(detected_paths["consciousness_state"] and detected_paths["consciousness_ledger"]),
        "harmony_ready": bool(harm.get("harmonized", False)),
        "brain_awareness_ready": (
            bool(brain.get("ok", False)) and not bool(brain.get("missing", False))
        ) or bool(detected_paths["brain_awareness"]),
    }
    gaps = [k for k, v in checks.items() if not v]
    root_issues: dict[str, list[str]] = {}
    if not checks["maturity_perfect"]:
        root_issues["maturity_perfect"] = list(mat.get("missing", []) or [])
    if not checks["security_hardened"]:
        root_issues["security_hardened"] = ["zero ai security profile not fully applied"]
    if not checks["backup_ready"]:
        root_issues["backup_ready"] = ["no backup snapshot/cure firewall backup found"]
    if not checks["knowledge_ready"]:
        root_issues["knowledge_ready"] = ["knowledge index missing or invalid"]
    if not checks["consciousness_ready"]:
        root_issues["consciousness_ready"] = ["no consciousness ledger events"]
    if not checks["harmony_ready"]:
        root_issues["harmony_ready"] = list(harm.get("issues", []) or [])
    if not checks["brain_awareness_ready"]:
        root_issues["brain_awareness_ready"] = list(brain.get("issues", []) or [])
    priorities = []
    if not checks["maturity_perfect"]:
        priorities.append("run: maturity scaffold all")
    if not checks["security_hardened"]:
        priorities.append("run: zero ai security apply")
    if not checks["backup_ready"]:
        priorities.append("run: zero ai backup create")
    if not checks["knowledge_ready"]:
        priorities.append("run: zero ai knowledge build")
    if not checks["consciousness_ready"]:
        priorities.append("run: zero ai consciousness tick")
    if not checks["harmony_ready"]:
        priorities.append("run: zero ai harmony")
    if not checks["brain_awareness_ready"]:
        priorities.append("run: zero ai brain awareness build")
    score = round((sum(1 for v in checks.values() if v) / max(1, len(checks))) * 100, 2)
    out = {
        "ok": True,
        "time_utc": _utc_now(),
        "gap_coverage_score": score,
        "maximized": score == 100.0 and len(gaps) == 0,
        "checks": checks,
        "gaps": gaps,
        "root_issues": root_issues,
        "next_priority": priorities,
        "signals": {
            "maturity": {"score": mat.get("score"), "perfect": mat.get("perfect"), "missing": mat.get("missing", [])},
            "security": {"hardened": sec.get("hardened"), "score": sec.get("zero_ai_security_score")},
            "backup": backup,
            "knowledge": know,
            "consciousness": {"ledger_events": con.get("ledger_events", 0)},
            "harmony": {"score": harm.get("harmony_score"), "harmonized": harm.get("harmonized")},
            "brain_awareness": {"aware": brain.get("aware"), "score": brain.get("brain_awareness_score")},
            "detected_paths": detected_paths,
        },
    }
    (_runtime(cwd) / "zero_ai_gap_status.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def zero_ai_gap_fix(cwd: str) -> dict:
    before = zero_ai_gap_status(cwd)
    actions = []
    maturity_scaffold_all(cwd)
    actions.append("maturity_scaffold_all")
    zero_ai_security_apply(cwd)
    actions.append("zero_ai_security_apply")
    zero_ai_backup_create(cwd)
    actions.append("zero_ai_backup_create")
    build_knowledge_index(cwd, max_files=50000)
    actions.append("build_knowledge_index")
    consciousness_tick(cwd, prompt="zero ai gap fix")
    actions.append("consciousness_tick")
    zero_ai_harmony_status(cwd, autocorrect=True)
    actions.append("zero_ai_harmony_status")
    _align_generation_state(cwd)
    actions.append("align_generation_state")
    # Second triad/harmony pass improves convergence for stale runtime states.
    run_triad_balance(cwd)
    actions.append("run_triad_balance")
    zero_ai_harmony_status(cwd, autocorrect=True)
    actions.append("zero_ai_harmony_status_second_pass")
    build_brain_awareness(cwd)
    actions.append("build_brain_awareness")
    after = zero_ai_gap_status(cwd)
    return {"ok": True, "time_utc": _utc_now(), "actions": actions, "before": before, "after": after}


def zero_ai_upgrade_system(cwd: str) -> dict:
    from zero_os.autonomous_runtime_ecosystem import ai_optimize
    from zero_os.production_core import benchmark_run, device_status, filesystem_status, memory_smart_optimize
    from zero_os.self_repair import self_repair_run

    before = zero_ai_gap_status(cwd)
    actions = []
    if not before.get("maximized", False):
        zero_ai_gap_fix(cwd)
        actions.append("zero_ai_gap_fix")
    optimize = {
        "ok": True,
        "time_utc": _utc_now(),
        "memory": memory_smart_optimize(cwd),
        "filesystem": filesystem_status(cwd),
        "device": device_status(),
        "benchmark": benchmark_run(cwd),
        "safety_mode": "no_storage_packing_of_live_source_files",
    }
    actions.append("safe_system_optimize")
    runtime_opt = ai_optimize(cwd)
    actions.append("autonomous_runtime_ai_optimize")
    repair = self_repair_run(cwd)
    actions.append("self_repair_run")
    zero_ai_security_apply(cwd)
    actions.append("zero_ai_security_apply")
    build_knowledge_index(cwd, max_files=50000)
    actions.append("build_knowledge_index")
    consciousness_tick(cwd, prompt="zero ai self upgrade for better system")
    actions.append("consciousness_tick")
    run_triad_balance(cwd)
    actions.append("run_triad_balance")
    build_brain_awareness(cwd)
    actions.append("build_brain_awareness")
    generation = _bump_generation_state(cwd)
    actions.append("bump_generation_state")
    after = zero_ai_gap_status(cwd)
    return {
        "ok": bool(after.get("maximized", False)),
        "time_utc": _utc_now(),
        "actions": actions,
        "generation_upgrade": generation,
        "before": before,
        "after": after,
        "optimize": optimize,
        "runtime_optimize": runtime_opt,
        "self_repair": repair,
        "summary": "Zero AI performed a guarded self-upgrade focused on system hardening, optimization, recovery, and state evolution.",
    }

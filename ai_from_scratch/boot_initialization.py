from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from ai_from_scratch.calibration_layer import run_calibration
    from ai_from_scratch.core_rule_layer import ensure_core_rules, verify_core_rules
    from ai_from_scratch.model import TinyBigramModel, inspect_checkpoint_payload
    from ai_from_scratch.shutdown_recovery import load_recovery_state
except ModuleNotFoundError:
    from calibration_layer import run_calibration
    from core_rule_layer import ensure_core_rules, verify_core_rules
    from model import TinyBigramModel, inspect_checkpoint_payload
    from shutdown_recovery import load_recovery_state


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _checkpoint_integrity(base: Path) -> dict:
    ckpt = base / "ai_from_scratch" / "checkpoint.json"
    backup = _runtime(str(base)) / "checkpoint.backup.json"
    if not ckpt.exists():
        if backup.exists():
            ckpt.write_text(backup.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            try:
                raw = json.loads(ckpt.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                raw = {}
            summary = inspect_checkpoint_payload(raw)
            return {
                "ok": True,
                "reason": "checkpoint restored from backup",
                "architecture": summary.get("architecture", ""),
                "native": bool(summary.get("native", False)),
                "vocab_size": int(summary.get("vocab_size", 0)),
            }
        # Self-heal: generate a minimal checkpoint from local project text.
        seed_text = ""
        for candidate in [base / "README.md", base / "zero_os.md"]:
            if candidate.exists():
                seed_text += candidate.read_text(encoding="utf-8", errors="replace") + "\n"
        if not seed_text.strip():
            seed_text = "Zero OS baseline model corpus."
        model = TinyBigramModel.build(seed_text)
        model.save(str(ckpt))
        backup.write_text(ckpt.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        meta = model.metadata()
        return {
            "ok": True,
            "reason": "checkpoint auto-restored",
            "architecture": meta["architecture"],
            "native": bool(meta["fully_native"]),
            "vocab_size": int(meta["vocab_size"]),
        }
    try:
        raw = json.loads(ckpt.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "reason": "checkpoint invalid json"}
    summary = inspect_checkpoint_payload(raw)
    if not summary.get("ok", False):
        return {"ok": False, "reason": summary.get("reason", "checkpoint malformed")}
    backup.write_text(ckpt.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    return {
        "ok": True,
        "reason": "checkpoint valid",
        "architecture": summary.get("architecture", ""),
        "native": bool(summary.get("native", False)),
        "vocab_size": int(summary.get("vocab_size", 0)),
    }


def _memory_validation(base: Path) -> dict:
    path = _runtime(str(base)) / "internal_zero_reasoner_memory.json"
    if not path.exists():
        return {"ok": True, "reason": "memory missing; will initialize"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "reason": "memory invalid json"}
    ok = isinstance(raw, dict) and isinstance(raw.get("success_patterns", []), list) and isinstance(
        raw.get("failure_patterns", []), list
    )
    return {"ok": ok, "reason": "memory valid" if ok else "memory malformed"}


def run_boot_initialization(cwd: str) -> dict:
    base = Path(cwd).resolve()
    ensure_core_rules(cwd)
    core = verify_core_rules(cwd)
    ckpt = _checkpoint_integrity(base)
    mem = _memory_validation(base)
    calibration = run_calibration(cwd)
    recovery = load_recovery_state(cwd)

    ok = bool(core.get("ok", False) and ckpt.get("ok", False) and mem.get("ok", False))
    result = {
        "time_utc": _utc_now(),
        "ok": ok,
        "core_rules": core,
        "model_integrity": ckpt,
        "memory_validation": mem,
        "signal_calibration": calibration,
        "recovery": recovery,
        "safe_mode": not ok,
    }
    (_runtime(cwd) / "boot_initialization.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result

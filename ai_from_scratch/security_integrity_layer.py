from __future__ import annotations

import hashlib
import json
from pathlib import Path


MALICIOUS_PATTERNS = (
    "rm -rf /",
    "format c:",
    "delete all files",
    "disable security",
    "disable firewall",
    "exfiltrate",
    "ransomware",
)

RESTRICTED_PREFIXES = ("admin:", "root:", "kernel:")


def _runtime_dir(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _checkpoint_integrity(base: Path) -> dict:
    ckpt = base / "ai_from_scratch" / "checkpoint.json"
    state = _runtime_dir(base) / "checkpoint_integrity.json"
    if not ckpt.exists():
        return {"ok": True, "reason": "missing checkpoint", "current_hash": "", "stored_hash": ""}
    current = _hash_file(ckpt)
    if not state.exists():
        payload = {"checkpoint_sha256": current}
        state.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return {"ok": True, "reason": "initialized", "current_hash": current, "stored_hash": current}
    try:
        stored = json.loads(state.read_text(encoding="utf-8", errors="replace")).get("checkpoint_sha256", "")
    except Exception:
        stored = ""
    if not stored:
        stored = current
        state.write_text(json.dumps({"checkpoint_sha256": stored}, indent=2) + "\n", encoding="utf-8")
    ok = current == stored
    return {"ok": ok, "reason": "match" if ok else "checkpoint hash mismatch", "current_hash": current, "stored_hash": stored}


def _memory_integrity(base: Path) -> dict:
    mem = _runtime_dir(base) / "internal_zero_reasoner_memory.json"
    if not mem.exists():
        return {"ok": True, "reason": "missing memory"}
    try:
        data = json.loads(mem.read_text(encoding="utf-8", errors="replace"))
        ok = isinstance(data, dict) and isinstance(data.get("success_patterns", []), list) and isinstance(
            data.get("failure_patterns", []), list
        )
        return {"ok": ok, "reason": "valid structure" if ok else "invalid memory structure"}
    except Exception:
        return {"ok": False, "reason": "memory json parse failed"}


def _is_malicious_input(prompt: str) -> tuple[bool, str]:
    text = str(prompt or "").strip().lower()
    if not text:
        return True, "empty prompt"
    for pat in MALICIOUS_PATTERNS:
        if pat in text:
            return True, f"blocked pattern: {pat}"
    return False, "clean"


def _dangerous_command_intent(prompt: str) -> tuple[bool, str]:
    text = str(prompt or "").strip().lower()
    risky_prefixes = ("shell run ", "powershell run ", "terminal run ", "process kill ")
    if any(text.startswith(p) for p in risky_prefixes):
        return True, "dangerous command intent"
    return False, "normal intent"


def _authorization_check(prompt: str, channel: str) -> dict:
    text = str(prompt or "").strip().lower()
    if any(text.startswith(p) for p in RESTRICTED_PREFIXES) and channel != "system_api":
        return {"ok": False, "reason": "restricted command requires system_api channel"}
    return {"ok": True, "reason": "authorized"}


def security_integrity_check(base: Path, prompt: str, channel: str) -> dict:
    malicious, mal_reason = _is_malicious_input(prompt)
    danger, danger_reason = _dangerous_command_intent(prompt)
    auth = _authorization_check(prompt, channel)
    checkpoint = _checkpoint_integrity(base)
    memory = _memory_integrity(base)
    command_gate_ok = (not danger) or channel == "system_api" or str(prompt).lower().startswith("authorized ")
    # Runtime integrity mismatches should not block safe conversational traffic.
    soft_integrity_ok = checkpoint["ok"] and memory["ok"]
    privileged_intent = channel == "system_api" or str(prompt).lower().startswith("authorized ")
    ok = (not malicious) and auth["ok"] and command_gate_ok and (soft_integrity_ok or not privileged_intent)
    return {
        "ok": ok,
        "malicious_input": {"blocked": malicious, "reason": mal_reason},
        "command_intent": {"blocked": bool(danger and not command_gate_ok), "reason": danger_reason},
        "authorization": auth,
        "checkpoint_integrity": checkpoint,
        "memory_integrity": memory,
        "integrity_soft_fail": bool(not soft_integrity_ok and ok),
    }

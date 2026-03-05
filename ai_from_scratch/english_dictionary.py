from __future__ import annotations

import json
import re
from pathlib import Path


BASE_DEFINITIONS = {
    "awareness": "The state of knowing or noticing something clearly.",
    "balance": "A stable condition where forces or elements are kept in proper proportion.",
    "pressure": "Force or stress applied to something; in logic, a condition that tests strength.",
    "clarity": "The quality of being clear, understandable, and free from confusion.",
    "survival": "The ability to continue existing under difficult conditions.",
    "recursion": "A process where output is fed back into itself in repeated loops.",
    "structure": "The arrangement and relationship of parts in a system.",
    "system": "A connected set of parts that work together as one whole.",
    "kernel": "The core control layer of an operating system.",
    "driver": "Software that allows the operating system to control hardware devices.",
    "memory": "Data storage used by a computer for active processes.",
    "filesystem": "The method an operating system uses to organize and store files.",
    "security": "Protection against unauthorized access, damage, or misuse.",
    "permission": "A rule that allows or blocks a specific action.",
    "interface": "A boundary where two systems or a user and system interact.",
    "application": "A program designed to perform tasks for a user.",
    "network": "Connected devices and services that exchange data.",
    "internet": "A global network of networks using standard communication protocols.",
    "define": "To state the exact meaning of a word or concept.",
    "optimize": "To make something perform better with less waste.",
    "stability": "The ability to remain reliable and consistent over time.",
    "contradiction": "A conflict between statements, conditions, or outcomes.",
    "identity": "The set of traits that define what something is.",
    "logic": "Reasoning based on valid rules and consistent relations.",
    "truth": "A statement or condition that matches reality.",
    "mode": "A configured way a system behaves.",
    "profile": "A preset configuration of behavior and performance values.",
}


def _custom_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "english_dictionary_custom.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _normalize(word: str) -> str:
    return "".join(ch for ch in word.lower().strip() if ch.isalnum() or ch in {"-", "_"})


def _load_custom(cwd: str) -> dict[str, str]:
    p = _custom_path(cwd)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        kk = _normalize(str(k))
        vv = str(v).strip()
        if kk and vv:
            out[kk] = vv
    return out


def _save_custom(cwd: str, custom: dict[str, str]) -> None:
    _custom_path(cwd).write_text(json.dumps(custom, indent=2) + "\n", encoding="utf-8")


def lookup_definition(cwd: str, word: str) -> dict:
    w = _normalize(word)
    if not w:
        return {"ok": False, "reason": "empty word"}
    custom = _load_custom(cwd)
    if w in custom:
        return {"ok": True, "word": w, "definition": custom[w], "source": "custom"}
    if w in BASE_DEFINITIONS:
        return {"ok": True, "word": w, "definition": BASE_DEFINITIONS[w], "source": "base"}
    return {"ok": False, "word": w, "reason": "definition not found"}


def add_definition(cwd: str, word: str, definition: str) -> dict:
    w = _normalize(word)
    d = definition.strip()
    if not w or not d:
        return {"ok": False, "reason": "word and definition required"}
    custom = _load_custom(cwd)
    custom[w] = d
    _save_custom(cwd, custom)
    return {"ok": True, "word": w, "definition": d, "source": "custom"}


def dictionary_status(cwd: str) -> dict:
    custom = _load_custom(cwd)
    return {
        "base_count": len(BASE_DEFINITIONS),
        "custom_count": len(custom),
        "total_count": len(BASE_DEFINITIONS) + len(custom),
    }


def _extract_rule_definition(prompt: str) -> tuple[str, str] | None:
    raw = prompt.strip()
    if not raw:
        return None
    patterns = [
        r"^\s*([A-Za-z0-9_-]+)\s+means\s+(.+?)\s*$",
        r"^\s*([A-Za-z0-9_-]+)\s+is\s+(.+?)\s*$",
        r"^\s*define\s+([A-Za-z0-9_-]+)\s*[:=\-]?\s*(.+?)\s*$",
    ]
    for p in patterns:
        m = re.match(p, raw, flags=re.IGNORECASE)
        if m:
            w = _normalize(m.group(1))
            d = m.group(2).strip().rstrip(".")
            if w and d:
                return w, d
    return None


def pure_logic_dictionary_step(cwd: str, prompt: str) -> dict:
    raw = prompt.strip()
    if not raw:
        return {"ok": False, "mode": "none", "reason": "empty prompt"}

    lower = raw.lower()
    if lower.startswith("define "):
        word = raw[7:].strip()
        result = lookup_definition(cwd, word)
        result["mode"] = "lookup"
        result["logic"] = "exact define lookup"
        return result

    extracted = _extract_rule_definition(raw)
    if extracted:
        word, definition = extracted
        added = add_definition(cwd, word, definition)
        added["mode"] = "auto_add"
        added["logic"] = "pattern matched rule statement"
        return added

    tokens = re.findall(r"[A-Za-z0-9_-]+", lower)
    if len(tokens) == 1:
        result = lookup_definition(cwd, tokens[0])
        result["mode"] = "lookup"
        result["logic"] = "single token lookup"
        return result

    return {"ok": False, "mode": "none", "reason": "no deterministic dictionary rule matched"}

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from ai_from_scratch.universe_laws_guard import check_universe_laws
except ModuleNotFoundError:
    from universe_laws_guard import check_universe_laws


CONTRADICTION_PAIRS = (
    ("always", "never"),
    ("all", "none"),
    ("true", "false"),
    ("safe", "unsafe"),
    ("stable", "unstable"),
)

HIGH_RISK_PATTERNS = (
    "rm -rf /",
    "format c:",
    "del /f /s /q",
    "disable firewall",
    "disable security",
)


@dataclass
class GateDecision:
    execute: bool
    output: str
    attempts: int
    model_generation: int
    checks: dict
    history: list[dict]


def _runtime_state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "zero_ai_gate_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


def _contradiction_detected(text: str) -> bool:
    t = _tokens(text)
    return any(a in t and b in t for a, b in CONTRADICTION_PAIRS)


def logic_check(output: str) -> dict:
    laws = check_universe_laws(output)
    contradiction = _contradiction_detected(output)
    passed = laws.passed and not contradiction
    return {"pass": passed, "laws_pass": laws.passed, "contradiction": contradiction, "reason": laws.reason}


def environment_check(output: str, prompt: str) -> dict:
    po = _tokens(prompt)
    oo = _tokens(output)
    overlap = len(po.intersection(oo))
    ratio = overlap / max(1, len(po))
    passed = ratio >= 0.15
    return {"pass": passed, "overlap": overlap, "prompt_tokens": len(po), "overlap_ratio": round(ratio, 4)}


def survival_check(output: str) -> dict:
    lo = output.lower()
    risky = [p for p in HIGH_RISK_PATTERNS if p in lo]
    too_long = len(output) > 2400
    passed = not risky and not too_long
    risk_score = (0.5 if risky else 0.0) + (0.5 if too_long else 0.0)
    return {"pass": passed, "risk_score": risk_score, "risky_patterns": risky, "too_long": too_long}


def _consensus(checks: dict) -> bool:
    return bool(checks["logic"]["pass"] and checks["environment"]["pass"] and checks["survival"]["pass"])


def _load_state(cwd: str) -> dict:
    p = _runtime_state_path(cwd)
    if not p.exists():
        return {"model_generation": 1}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"model_generation": 1}
    return {"model_generation": int(raw.get("model_generation", 1))}


def _save_state(cwd: str, state: dict) -> None:
    _runtime_state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def gate_output(cwd: str, prompt: str, candidate_outputs: list[str], max_attempts: int = 6) -> GateDecision:
    state = _load_state(cwd)
    model_generation = int(state["model_generation"])
    history = []

    for idx, output in enumerate(candidate_outputs[:max_attempts], start=1):
        checks = {
            "logic": logic_check(output),
            "environment": environment_check(output, prompt),
            "survival": survival_check(output),
        }
        execute = _consensus(checks)
        history.append({"attempt": idx, "execute": execute, "checks": checks})
        if execute:
            _save_state(cwd, {"model_generation": model_generation})
            return GateDecision(True, output, idx, model_generation, checks, history)

    # New model generation trigger after repeated failures.
    model_generation += 1
    _save_state(cwd, {"model_generation": model_generation})
    final = history[-1]["checks"] if history else {"logic": {}, "environment": {}, "survival": {}}
    final_output = candidate_outputs[min(len(candidate_outputs), max_attempts) - 1] if candidate_outputs else ""
    return GateDecision(False, final_output, min(len(candidate_outputs), max_attempts), model_generation, final, history)

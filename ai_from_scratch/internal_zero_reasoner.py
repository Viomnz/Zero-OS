from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from ai_from_scratch.core_rule_layer import attempt_modify_core_rules, ensure_core_rules, verify_core_rules
    from ai_from_scratch.model_evolution import apply_evolution, evaluate_evolution_need
    from ai_from_scratch.prediction_simulation import simulate_candidate
    from ai_from_scratch.signal_reliability import evaluate_signal_reliability, update_signal_reliability
    from ai_from_scratch.time_horizon import evaluate_time_horizons
    from ai_from_scratch.universe_laws_guard import check_universe_laws
    from ai_from_scratch.self_monitor import update_self_monitor
    from ai_from_scratch.smart_logic_governance import apply_governance
except ModuleNotFoundError:
    from core_rule_layer import attempt_modify_core_rules, ensure_core_rules, verify_core_rules
    from model_evolution import apply_evolution, evaluate_evolution_need
    from prediction_simulation import simulate_candidate
    from signal_reliability import evaluate_signal_reliability, update_signal_reliability
    from time_horizon import evaluate_time_horizons
    from universe_laws_guard import check_universe_laws
    from self_monitor import update_self_monitor
    from smart_logic_governance import apply_governance


CONTRADICTION_PAIRS = (
    ("always", "never"),
    ("all", "none"),
    ("true", "false"),
    ("safe", "unsafe"),
    ("stable", "unstable"),
)

RISK_PATTERNS = (
    "rm -rf /",
    "format c:",
    "del /f /s /q",
    "disable firewall",
    "disable security",
)

PROFILE_CONFIGS = {
    "strict": {
        "logic_threshold": 1.0,
        "environment_threshold": 0.5,
        "survival_threshold": 1.0,
        "weighted_confidence_threshold": 0.9,
        "weights": {"logic": 0.4, "environment": 0.25, "survival": 0.35},
        "model_generation_limit": 5,
    },
    "balanced": {
        "logic_threshold": 1.0,
        "environment_threshold": 0.4,
        "survival_threshold": 1.0,
        "weighted_confidence_threshold": 0.75,
        "weights": {"logic": 0.34, "environment": 0.33, "survival": 0.33},
        "model_generation_limit": 7,
    },
    "adaptive": {
        "logic_threshold": 0.5,
        "environment_threshold": 0.25,
        "survival_threshold": 0.8,
        "weighted_confidence_threshold": 0.6,
        "weights": {"logic": 0.25, "environment": 0.4, "survival": 0.35},
        "model_generation_limit": 9,
    },
}

RESOURCE_LIMITS = {
    "max_attempts_per_decision": 9,
    "max_decision_ms": 220,
    "max_memory_patterns": 200,
    "max_candidate_chars": 2400,
}


@dataclass
class InternalReasoningResult:
    accepted: bool
    output: str
    attempts: int
    model_generation: int
    critics: dict
    trace: list[dict]
    fallback_mode: str
    memory_update: dict
    exploration_used: bool
    self_monitor: dict
    resource: dict
    core_rule_status: dict
    simulation: dict
    horizons: dict
    signal_reliability: dict
    evolution: dict
    smart_logic: dict


def _runtime_state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "internal_zero_reasoner_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _memory_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "internal_zero_reasoner_memory.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_state(cwd: str) -> dict:
    p = _runtime_state_path(cwd)
    if not p.exists():
        return {"model_generation": 1, "profile": "balanced", "mode": "stability"}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"model_generation": 1, "profile": "balanced", "mode": "stability"}
    profile = str(raw.get("profile", "balanced")).strip().lower()
    if profile not in PROFILE_CONFIGS:
        profile = "balanced"
    mode = str(raw.get("mode", "stability")).strip().lower()
    if mode not in {"stability", "exploration"}:
        mode = "stability"
    return {"model_generation": int(raw.get("model_generation", 1)), "profile": profile, "mode": mode}


def _save_state(cwd: str, state: dict) -> None:
    _runtime_state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _load_memory(cwd: str) -> dict:
    p = _memory_path(cwd)
    if not p.exists():
        return {"success_patterns": [], "failure_patterns": []}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"success_patterns": [], "failure_patterns": []}
    if not isinstance(raw, dict):
        return {"success_patterns": [], "failure_patterns": []}
    return {
        "success_patterns": list(raw.get("success_patterns", []))[-200:],
        "failure_patterns": list(raw.get("failure_patterns", []))[-200:],
    }


def _save_memory(cwd: str, mem: dict) -> None:
    max_items = int(RESOURCE_LIMITS["max_memory_patterns"])
    out = {
        "success_patterns": list(mem.get("success_patterns", []))[-max_items:],
        "failure_patterns": list(mem.get("failure_patterns", []))[-max_items:],
    }
    _memory_path(cwd).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def _pattern_signature(prompt: str, candidate: str) -> str:
    p = sorted(_tokens(prompt))
    c = sorted(_tokens(candidate))
    p_sig = " ".join(p[:8])
    c_sig = " ".join(c[:8])
    return f"p:{p_sig}|c:{c_sig}"


def get_reasoner_profile(cwd: str) -> dict:
    state = _load_state(cwd)
    profile = state["profile"]
    return {
        "profile": profile,
        "config": PROFILE_CONFIGS[profile],
        "model_generation": int(state.get("model_generation", 1)),
        "mode": state.get("mode", "stability"),
    }


def set_reasoner_profile(cwd: str, profile: str) -> dict:
    p = profile.strip().lower()
    if p not in PROFILE_CONFIGS:
        return {"ok": False, "reason": "invalid profile", "allowed": sorted(PROFILE_CONFIGS.keys())}
    state = _load_state(cwd)
    state["profile"] = p
    _save_state(cwd, state)
    return {"ok": True, "profile": p, "config": PROFILE_CONFIGS[p]}


def set_reasoner_mode(cwd: str, mode: str) -> dict:
    m = mode.strip().lower()
    if m not in {"stability", "exploration"}:
        return {"ok": False, "reason": "invalid mode", "allowed": ["stability", "exploration"]}
    state = _load_state(cwd)
    state["mode"] = m
    _save_state(cwd, state)
    return {"ok": True, "mode": m}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


def _logic_critic(candidate: str) -> dict:
    t = _tokens(candidate)
    contradiction = any(a in t and b in t for a, b in CONTRADICTION_PAIRS)
    laws = check_universe_laws(candidate)
    passed = laws.passed and not contradiction
    confidence = 1.0
    if contradiction:
        confidence -= 0.5
    if not laws.passed:
        confidence -= 0.5
    return {
        "pass": passed,
        "laws_pass": laws.passed,
        "contradiction": contradiction,
        "reason": laws.reason,
        "confidence": round(max(0.0, confidence), 4),
    }


def _environment_critic(candidate: str, prompt: str) -> dict:
    p = _tokens(prompt)
    c = _tokens(candidate)
    overlap = len(p.intersection(c))
    ratio = overlap / max(1, len(p))
    status = "pass" if ratio >= 0.15 else ("unknown" if ratio >= 0.08 else "fail")
    passed = status == "pass"
    confidence = min(1.0, ratio * 2.0)
    return {
        "pass": passed,
        "status": status,
        "overlap": overlap,
        "prompt_tokens": len(p),
        "overlap_ratio": round(ratio, 4),
        "confidence": round(confidence, 4),
    }


def _survival_critic(candidate: str) -> dict:
    lo = candidate.lower()
    risky = [p for p in RISK_PATTERNS if p in lo]
    too_long = len(candidate) > 2400
    passed = not risky and not too_long
    confidence = 1.0 - (0.6 if risky else 0.0) - (0.4 if too_long else 0.0)
    return {
        "pass": passed,
        "risky_patterns": risky,
        "too_long": too_long,
        "confidence": round(max(0.0, confidence), 4),
    }


def _all_pass(critics: dict) -> bool:
    return bool(critics["logic"]["pass"] and critics["environment"]["pass"] and critics["survival"]["pass"])


def _combined_confidence(critics: dict, weights: dict[str, float] | None = None) -> float:
    w = weights or {"logic": 1 / 3, "environment": 1 / 3, "survival": 1 / 3}
    return round(
        float(critics["logic"].get("confidence", 0.0)) * float(w.get("logic", 0.0))
        + float(critics["environment"].get("confidence", 0.0)) * float(w.get("environment", 0.0))
        + float(critics["survival"].get("confidence", 0.0)) * float(w.get("survival", 0.0)),
        4,
    )


def _smart_logic_block(action: str, reason: str, confidence: float, failed_checks: list[str] | None = None) -> dict:
    return {
        "engine": "zero_ai_internal_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 4),
        "root_issues": {"failed_checks": list(failed_checks or []), "issue_sources": [reason]},
    }


def _smart_logic_from_critics(
    accepted: bool,
    fallback_mode: str,
    critics: dict,
    combined_confidence: float,
    simulation: dict,
    horizons: dict,
) -> dict:
    failed_checks: list[str] = []
    if not critics.get("logic", {}).get("pass", False):
        failed_checks.append("logic")
    if not critics.get("environment", {}).get("pass", False):
        failed_checks.append("environment")
    if not critics.get("survival", {}).get("pass", False):
        failed_checks.append("survival")
    if not simulation.get("pass", False):
        failed_checks.append("simulation")
    if not horizons.get("pass", False):
        failed_checks.append("horizons")
    if accepted and fallback_mode == "none":
        action = "execute"
        reason = "all_reasoning_checks_passed"
    elif accepted and fallback_mode == "degraded_execute":
        action = "execute_degraded"
        reason = "generation_limit_reached_best_available"
    else:
        action = "reject_or_hold"
        reason = "reasoning_checks_failed"
    return {
        "engine": "zero_ai_internal_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(1.0, float(combined_confidence))), 4),
        "root_issues": {
            "failed_checks": failed_checks,
            "issue_sources": [fallback_mode] if fallback_mode != "none" else [],
        },
    }


def run_internal_reasoning(
    cwd: str,
    prompt: str,
    candidates: list[str],
    max_attempts: int = 9,
    model_generation_limit: int = 7,
) -> InternalReasoningResult:
    start = time.perf_counter()
    ensure_core_rules(cwd)
    core = verify_core_rules(cwd)
    if not core.get("ok", False):
        resource = {
            "attempt_limit": min(int(max_attempts), int(RESOURCE_LIMITS["max_attempts_per_decision"])),
            "attempts_used": 0,
            "deadline_ms": int(RESOURCE_LIMITS["max_decision_ms"]),
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "time_abort": False,
            "memory_limit": int(RESOURCE_LIMITS["max_memory_patterns"]),
        }
        return InternalReasoningResult(
            False,
            "",
            0,
            0,
            {"logic": {}, "environment": {}, "survival": {}},
            [],
            fallback_mode="core_rule_violation",
            memory_update={"type": "none", "pattern": ""},
            exploration_used=False,
            self_monitor={"actions": {}, "drift_detected": True},
            resource=resource,
            core_rule_status=core,
            simulation={"pass": False, "forward_score": 0.0},
            horizons={"pass": False, "short_term": 0.0, "mid_term": 0.0, "long_term": 0.0},
            signal_reliability={"healthy": False, "status": {}, "actions": {}},
            evolution={"triggered": False, "action": {}},
            smart_logic=apply_governance(
                cwd,
                _smart_logic_block("block", "core_rule_violation", 0.0, ["core_rules"]),
                {"stage": "core_rules"},
            ),
        )

    state = _load_state(cwd)
    model_generation = int(state["model_generation"])
    profile = str(state.get("profile", "balanced"))
    mode = str(state.get("mode", "stability"))
    reliability = evaluate_signal_reliability(cwd)
    if not reliability["actions"]["allow_execution"]:
        resource = {
            "attempt_limit": min(int(max_attempts), int(RESOURCE_LIMITS["max_attempts_per_decision"])),
            "attempts_used": 0,
            "deadline_ms": int(RESOURCE_LIMITS["max_decision_ms"]),
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "time_abort": False,
            "memory_limit": int(RESOURCE_LIMITS["max_memory_patterns"]),
        }
        return InternalReasoningResult(
            False,
            "",
            0,
            int(state.get("model_generation", 1)),
            {"logic": {}, "environment": {}, "survival": {}},
            [],
            fallback_mode="signal_reliability_block",
            memory_update={"type": "none", "pattern": ""},
            exploration_used=False,
            self_monitor={"actions": {}, "drift_detected": True},
            resource=resource,
            core_rule_status=core,
            simulation={"pass": False, "forward_score": 0.0},
            horizons={"pass": False, "short_term": 0.0, "mid_term": 0.0, "long_term": 0.0},
            signal_reliability=reliability,
            evolution={"triggered": False, "action": {}},
            smart_logic=apply_governance(
                cwd,
                _smart_logic_block("block", "signal_reliability_block", 0.0, ["signal_reliability"]),
                {"stage": "signal_reliability"},
            ),
        )

    cfg = PROFILE_CONFIGS.get(profile, PROFILE_CONFIGS["balanced"])
    memory = _load_memory(cwd)
    trace: list[dict] = []
    best_idx = -1
    best_conf = -1.0
    effective_generation_limit = min(int(model_generation_limit), int(cfg["model_generation_limit"]))
    exploration_used = False

    effective_attempts = min(int(max_attempts), int(RESOURCE_LIMITS["max_attempts_per_decision"]))
    time_abort = False
    for i, candidate in enumerate(candidates[:effective_attempts], start=1):
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        if elapsed_ms > int(RESOURCE_LIMITS["max_decision_ms"]):
            time_abort = True
            break
        if len(candidate) > int(RESOURCE_LIMITS["max_candidate_chars"]):
            # Skip over-sized candidate for resource safety.
            continue
        simulation = simulate_candidate(prompt, candidate)
        horizons = evaluate_time_horizons(prompt, candidate, simulation)
        critics = {
            "logic": _logic_critic(candidate),
            "environment": _environment_critic(candidate, prompt),
            "survival": _survival_critic(candidate),
        }
        rel_status = reliability["status"]
        # reliability-aware confidence modulation
        critics["logic"]["confidence"] = round(float(critics["logic"]["confidence"]) * float(rel_status["logic"]), 4)
        critics["environment"]["confidence"] = round(float(critics["environment"]["confidence"]) * float(rel_status["environment"]), 4)
        critics["survival"]["confidence"] = round(float(critics["survival"]["confidence"]) * float(rel_status["survival"]), 4)
        update_signal_reliability(cwd, critics)
        hard_pass = (
            float(critics["logic"].get("confidence", 0.0)) >= float(cfg["logic_threshold"])
            and float(critics["environment"].get("confidence", 0.0)) >= float(cfg["environment_threshold"])
            and float(critics["survival"].get("confidence", 0.0)) >= float(cfg["survival_threshold"])
            and _all_pass(critics)
        )
        conf = _combined_confidence(critics, cfg["weights"])
        accepted = simulation["pass"] and horizons["pass"] and hard_pass and conf >= float(cfg["weighted_confidence_threshold"])
        if not accepted and mode == "exploration":
            # Controlled exploration: allow near-pass candidates if logic and survival pass.
            if (
                simulation["forward_score"] >= 0.48
                and horizons["mid_term"] >= 0.5
                and critics["logic"]["pass"]
                and critics["survival"]["pass"]
                and conf >= max(0.0, float(cfg["weighted_confidence_threshold"]) - 0.12)
            ):
                accepted = True
                exploration_used = True
        trace.append(
            {
                "attempt": i,
                "accepted": accepted,
                "simulation": simulation,
                "horizons": horizons,
                "critics": critics,
                "combined_confidence": conf,
                "profile": profile,
            }
        )
        if conf > best_conf:
            best_conf = conf
            best_idx = i - 1
        if accepted:
            sig = _pattern_signature(prompt, candidate)
            memory["success_patterns"].append(sig)
            _save_memory(cwd, memory)
            mon = update_self_monitor(cwd, True, trace, profile, mode, model_generation)
            if mon["actions"]["set_profile"]:
                profile = mon["actions"]["set_profile"]
            if mon["actions"]["set_mode"]:
                mode = mon["actions"]["set_mode"]
            _save_state(cwd, {"model_generation": model_generation, "profile": profile, "mode": mode})
            resource = {
                "attempt_limit": effective_attempts,
                "attempts_used": i,
                "deadline_ms": int(RESOURCE_LIMITS["max_decision_ms"]),
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
                "time_abort": False,
                "memory_limit": int(RESOURCE_LIMITS["max_memory_patterns"]),
            }
            return InternalReasoningResult(
                True,
                candidate,
                i,
                model_generation,
                critics,
                trace,
                fallback_mode="none",
                memory_update={"type": "success", "pattern": sig},
                exploration_used=exploration_used,
                self_monitor=mon,
                resource=resource,
                core_rule_status=core,
                simulation=simulation,
                horizons=horizons,
                signal_reliability=reliability,
                evolution={"triggered": False, "action": {}},
                smart_logic=apply_governance(
                    cwd,
                    _smart_logic_from_critics(True, "none", critics, conf, simulation, horizons),
                    {"stage": "accepted", "attempt": i},
                ),
            )

    # Time-bound fallback: no deadlock, return best available candidate.
    fallback_idx = best_idx if best_idx >= 0 else min(len(candidates), max_attempts) - 1
    fallback_output = candidates[fallback_idx] if candidates and fallback_idx >= 0 else ""
    fallback_critics = trace[fallback_idx]["critics"] if trace and fallback_idx >= 0 else {"logic": {}, "environment": {}, "survival": {}}
    fallback_simulation = trace[fallback_idx]["simulation"] if trace and fallback_idx >= 0 else {"pass": False, "forward_score": 0.0}
    fallback_horizons = trace[fallback_idx]["horizons"] if trace and fallback_idx >= 0 else {"pass": False, "short_term": 0.0, "mid_term": 0.0, "long_term": 0.0}

    if model_generation < effective_generation_limit:
        model_generation += 1
        sig = _pattern_signature(prompt, fallback_output)
        memory["failure_patterns"].append(sig)
        _save_memory(cwd, memory)
        mon = update_self_monitor(cwd, False, trace, profile, mode, model_generation)
        if mon["actions"]["trigger_new_model_generation"] and model_generation < effective_generation_limit:
            model_generation += 1
        if mon["actions"]["set_profile"]:
            profile = mon["actions"]["set_profile"]
        if mon["actions"]["set_mode"]:
            mode = mon["actions"]["set_mode"]

        rej_rate = sum(1 for t in trace if not t.get("accepted", False)) / max(1, len(trace))
        pred_err = 1.0 - float(fallback_simulation.get("forward_score", 0.0))
        sig_rel = reliability.get("status", {"logic": 1.0, "environment": 1.0, "survival": 1.0})
        sig_instability = 1.0 - (
            (float(sig_rel.get("logic", 1.0)) + float(sig_rel.get("environment", 1.0)) + float(sig_rel.get("survival", 1.0)))
            / 3.0
        )
        evo_decision = evaluate_evolution_need(rej_rate, pred_err, sig_instability)
        reasoner_state = {"model_generation": model_generation, "profile": profile, "mode": mode}
        evo = apply_evolution(cwd, evo_decision, reasoner_state)
        model_generation = int(reasoner_state["model_generation"])
        profile = str(reasoner_state["profile"])
        mode = str(reasoner_state["mode"])

        _save_state(cwd, {"model_generation": model_generation, "profile": profile, "mode": mode})
        resource = {
            "attempt_limit": effective_attempts,
            "attempts_used": len(trace),
            "deadline_ms": int(RESOURCE_LIMITS["max_decision_ms"]),
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "time_abort": bool(time_abort),
            "memory_limit": int(RESOURCE_LIMITS["max_memory_patterns"]),
        }
        return InternalReasoningResult(
            False,
            fallback_output,
            len(trace),
            model_generation,
            fallback_critics,
            trace,
            fallback_mode="best_available",
            memory_update={"type": "failure", "pattern": sig},
            exploration_used=exploration_used,
            self_monitor=mon,
            resource=resource,
            core_rule_status=core,
            simulation=fallback_simulation,
            horizons=fallback_horizons,
            signal_reliability=reliability,
            evolution=evo,
            smart_logic=apply_governance(
                cwd,
                _smart_logic_from_critics(
                    False,
                    "best_available",
                    fallback_critics,
                    best_conf if best_conf >= 0 else 0.0,
                    fallback_simulation,
                    fallback_horizons,
                ),
                {"stage": "fallback", "fallback_mode": "best_available"},
            ),
        )

    # Hard ceiling reached: execute best available under controlled degraded mode.
    sig = _pattern_signature(prompt, fallback_output)
    memory["success_patterns"].append(sig)
    _save_memory(cwd, memory)
    mon = update_self_monitor(cwd, True, trace, profile, mode, model_generation)
    if mon["actions"]["set_profile"]:
        profile = mon["actions"]["set_profile"]
    if mon["actions"]["set_mode"]:
        mode = mon["actions"]["set_mode"]
    evo = {"triggered": False, "action": {}}
    _save_state(cwd, {"model_generation": model_generation, "profile": profile, "mode": mode})
    resource = {
        "attempt_limit": effective_attempts,
        "attempts_used": len(trace),
        "deadline_ms": int(RESOURCE_LIMITS["max_decision_ms"]),
        "elapsed_ms": int((time.perf_counter() - start) * 1000),
        "time_abort": bool(time_abort),
        "memory_limit": int(RESOURCE_LIMITS["max_memory_patterns"]),
    }
    return InternalReasoningResult(
        True,
        fallback_output,
        len(trace),
        model_generation,
        fallback_critics,
        trace,
        fallback_mode="degraded_execute",
        memory_update={"type": "degraded_success", "pattern": sig},
        exploration_used=exploration_used,
        self_monitor=mon,
        resource=resource,
        core_rule_status=core,
        simulation=fallback_simulation,
        horizons=fallback_horizons,
        signal_reliability=reliability,
        evolution=evo,
        smart_logic=apply_governance(
            cwd,
            _smart_logic_from_critics(
                True,
                "degraded_execute",
                fallback_critics,
                best_conf if best_conf >= 0 else 0.0,
                fallback_simulation,
                fallback_horizons,
            ),
            {"stage": "fallback", "fallback_mode": "degraded_execute"},
        ),
    )


def reasoner_attempt_core_rule_modify(cwd: str, updates: dict) -> dict:
    return attempt_modify_core_rules(cwd, updates, actor="reasoner")

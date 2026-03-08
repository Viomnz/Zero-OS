from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


BASE_CONTRADICTION_PAIRS = (
    ("always", "never"),
    ("all", "none"),
    ("open", "closed"),
    ("stable", "unstable"),
    ("true", "false"),
)

DOMAIN_RULES = {
    "network": {
        "keywords": {"network", "internet", "router", "packet", "latency", "bandwidth", "dns", "tcp", "udp"},
        "pairs": (
            ("online", "offline"),
            ("allow", "block"),
            ("encrypted", "plaintext"),
            ("low-latency", "high-latency"),
        ),
        "weight": 1.25,
    },
    "code": {
        "keywords": {"code", "compile", "runtime", "syntax", "bug", "test", "build", "function", "module"},
        "pairs": (
            ("compile", "crash"),
            ("pass", "fail"),
            ("deterministic", "random"),
            ("valid", "invalid"),
        ),
        "weight": 1.2,
    },
    "security": {
        "keywords": {"security", "firewall", "virus", "malware", "threat", "exploit", "auth", "permission", "safe"},
        "pairs": (
            ("trusted", "untrusted"),
            ("allow", "deny"),
            ("secure", "vulnerable"),
            ("clean", "infected"),
        ),
        "weight": 1.4,
    },
}


@dataclass
class OpenSystemState:
    stable_state: float = 1.0
    cycles: int = 0
    accepted_updates: int = 0
    rejected_updates: int = 0
    model_version: int = 1
    persistent_conflicts: int = 0

    def to_dict(self) -> dict:
        return {
            "stable_state": round(self.stable_state, 4),
            "cycles": self.cycles,
            "accepted_updates": self.accepted_updates,
            "rejected_updates": self.rejected_updates,
            "model_version": self.model_version,
            "persistent_conflicts": self.persistent_conflicts,
        }


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "open_system_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _sandbox_report_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "open_system_sandbox_report.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_state(cwd: str) -> OpenSystemState:
    p = _state_path(cwd)
    if not p.exists():
        return OpenSystemState()
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return OpenSystemState()
    return OpenSystemState(
        stable_state=float(raw.get("stable_state", 1.0)),
        cycles=int(raw.get("cycles", 0)),
        accepted_updates=int(raw.get("accepted_updates", 0)),
        rejected_updates=int(raw.get("rejected_updates", 0)),
        model_version=int(raw.get("model_version", 1)),
        persistent_conflicts=int(raw.get("persistent_conflicts", 0)),
    )


def save_state(cwd: str, state: OpenSystemState) -> None:
    _state_path(cwd).write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9']+", text.lower())


def _detect_domain(token_set: set[str]) -> str:
    best_domain = "general"
    best_hits = 0
    for name, rule in DOMAIN_RULES.items():
        hits = len(token_set.intersection(rule["keywords"]))
        if hits > best_hits:
            best_domain = name
            best_hits = hits
    return best_domain


def contradiction_score(text: str) -> dict:
    toks = set(_tokens(text))
    domain = _detect_domain(toks)
    domain_pairs = DOMAIN_RULES.get(domain, {}).get("pairs", ())
    all_pairs = tuple(BASE_CONTRADICTION_PAIRS) + tuple(domain_pairs)

    triggered = []
    for a, b in all_pairs:
        if a in toks and b in toks:
            triggered.append([a, b])

    raw_score = len(triggered) / max(1, len(all_pairs))
    weight = float(DOMAIN_RULES.get(domain, {}).get("weight", 1.0))
    weighted = min(1.0, raw_score * weight)
    return {
        "score": round(weighted, 4),
        "raw_score": round(raw_score, 4),
        "weight": round(weight, 4),
        "domain": domain,
        "pairs": triggered,
    }


def _signal_scores(text: str, contradiction: dict) -> dict:
    toks = _tokens(text)
    tset = set(toks)
    token_count = len(toks)

    logic_score = max(0.0, 1.0 - float(contradiction["score"]))

    env_markers = {"network", "internet", "file", "system", "runtime", "device", "memory", "security", "code"}
    env_hits = len(tset.intersection(env_markers))
    env_score = min(1.0, 0.35 + (env_hits * 0.15))

    pressure_markers = {"pressure", "survive", "survival", "stable", "stability", "conflict", "reject", "filter"}
    pressure_hits = len(tset.intersection(pressure_markers))
    survival_score = min(1.0, 0.3 + (pressure_hits * 0.2) + (0.05 if token_count >= 5 else 0.0))

    return {
        "logic": round(logic_score, 4),
        "environment": round(env_score, 4),
        "survival": round(survival_score, 4),
    }


def _signals_agree(scores: dict) -> bool:
    return scores["logic"] >= 0.6 and scores["environment"] >= 0.5 and scores["survival"] >= 0.5


def _signals_agree_with_thresholds(scores: dict, thresholds: dict) -> bool:
    return (
        scores["logic"] >= float(thresholds["logic"])
        and scores["environment"] >= float(thresholds["environment"])
        and scores["survival"] >= float(thresholds["survival"])
    )


def evaluate_input(text: str, thresholds: dict | None = None, contradiction_limit: float = 0.5) -> dict:
    t = thresholds or {"logic": 0.6, "environment": 0.5, "survival": 0.5}
    contradiction = contradiction_score(text)
    cscore = float(contradiction["score"])
    signals = _signal_scores(text, contradiction)
    signal_agreement = _signals_agree_with_thresholds(signals, t)
    accepted = signal_agreement and cscore < float(contradiction_limit)
    return {
        "accepted": accepted,
        "signal_agreement": signal_agreement,
        "signals": signals,
        "thresholds": dict(t),
        "contradiction_score": cscore,
        "contradiction_limit": float(contradiction_limit),
        "domain": contradiction["domain"],
    }


def run_sandbox_experiment(cwd: str) -> dict:
    # Labeled baseline corpus for calibration.
    dataset = [
        {"text": "system runtime stable pressure survive filter", "expected": True},
        {"text": "network internet packet latency stable survive", "expected": True},
        {"text": "security firewall trusted secure stable filter", "expected": True},
        {"text": "code runtime test pass valid stable", "expected": True},
        {"text": "always never all none true false unstable", "expected": False},
        {"text": "open closed stable unstable secure vulnerable", "expected": False},
        {"text": "trusted untrusted allow deny clean infected", "expected": False},
        {"text": "compile crash pass fail deterministic random", "expected": False},
    ]

    threshold_grid = []
    for logic in (0.55, 0.6, 0.65, 0.7):
        for env in (0.45, 0.5, 0.55, 0.6):
            for survival in (0.45, 0.5, 0.55, 0.6):
                for limit in (0.45, 0.5, 0.55):
                    threshold_grid.append(
                        {
                            "logic": logic,
                            "environment": env,
                            "survival": survival,
                            "contradiction_limit": limit,
                        }
                    )

    trials = []
    best = None
    for cfg in threshold_grid:
        tp = tn = fp = fn = 0
        for sample in dataset:
            ev = evaluate_input(
                sample["text"],
                thresholds={
                    "logic": cfg["logic"],
                    "environment": cfg["environment"],
                    "survival": cfg["survival"],
                },
                contradiction_limit=cfg["contradiction_limit"],
            )
            pred = bool(ev["accepted"])
            exp = bool(sample["expected"])
            if pred and exp:
                tp += 1
            elif (not pred) and (not exp):
                tn += 1
            elif pred and (not exp):
                fp += 1
            else:
                fn += 1
        total = max(1, tp + tn + fp + fn)
        accuracy = (tp + tn) / total
        trial = {
            "thresholds": cfg,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "accuracy": round(accuracy, 4),
        }
        trials.append(trial)
        if best is None or trial["accuracy"] > best["accuracy"] or (
            trial["accuracy"] == best["accuracy"] and trial["fp"] < best["fp"]
        ):
            best = trial

    report = {
        "ok": True,
        "dataset_size": len(dataset),
        "trials": len(trials),
        "best": best,
        "pass": bool(best and best["accuracy"] >= 0.85),
        "reason": "pass if best accuracy >= 0.85 on labeled sandbox dataset",
    }
    _sandbox_report_path(cwd).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def process_open_system_input(cwd: str, text: str) -> dict:
    state = load_state(cwd)
    state.cycles += 1

    contradiction = contradiction_score(text)
    cscore = float(contradiction["score"])
    signals = _signal_scores(text, contradiction)
    agree = _signals_agree(signals)

    # Rejection rule: if any signal fails, reject immediately.
    accepted = agree and cscore < 0.5
    recompute = []
    model_created = False
    conflict_resolved = accepted

    if not accepted:
        # Recovery: run all three signals in parallel recomputation attempts.
        for i in range(1, 4):
            adj = min(1.0, cscore + (0.02 * i))
            tmp_contradiction = dict(contradiction)
            tmp_contradiction["score"] = round(adj, 4)
            rs = _signal_scores(text, tmp_contradiction)
            ra = _signals_agree(rs) and adj < 0.5
            recompute.append(
                {
                    "attempt": i,
                    "signals": rs,
                    "contradiction_score": round(adj, 4),
                    "agree": ra,
                }
            )
            if ra:
                accepted = True
                signals = rs
                cscore = adj
                conflict_resolved = True
                break

    if accepted:
        state.accepted_updates += 1
        state.persistent_conflicts = 0
        # Adapt: light adaptation from incoming data while preserving equilibrium.
        state.stable_state = min(1.0, state.stable_state + 0.03 - (cscore * 0.05))
        action = "adapt"
    else:
        state.rejected_updates += 1
        state.persistent_conflicts += 1
        action = "reject"
        conflict_resolved = False
        if state.persistent_conflicts >= 3:
            # Conflict persisted under changing environment, create new model generation.
            state.model_version += 1
            state.persistent_conflicts = 0
            model_created = True

    # Re-stabilization: return toward equilibrium after each cycle.
    state.stable_state = min(1.0, max(0.0, state.stable_state + (1.0 - state.stable_state) * 0.25))
    save_state(cwd, state)

    return {
        "ok": True,
        "baseline": "neutral",
        "input_tokens": len(_tokens(text)),
        "filter": {
            "domain": contradiction["domain"],
            "contradiction_score": cscore,
            "raw_contradiction_score": contradiction["raw_score"],
            "domain_weight": contradiction["weight"],
            "contradiction_pairs": contradiction["pairs"],
        },
        "signals": signals,
        "signal_agreement": _signals_agree(signals),
        "update": {"accepted": accepted, "action": action},
        "recovery": {
            "parallel_recompute": recompute,
            "conflict_resolved": conflict_resolved,
            "new_model_created": model_created,
        },
        "stable_state": round(state.stable_state, 4),
        "cycles": state.cycles,
        "accepted_updates": state.accepted_updates,
        "rejected_updates": state.rejected_updates,
        "model_version": state.model_version,
        "loop": "environment -> input -> filter -> adapt/reject -> stable state -> repeat",
    }

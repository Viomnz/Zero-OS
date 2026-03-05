from __future__ import annotations

import json
from pathlib import Path

try:
    from ai_from_scratch.prediction_simulation import simulate_candidate
except ModuleNotFoundError:
    from prediction_simulation import simulate_candidate


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _combined_confidence(critics: dict) -> float:
    logic = float(critics.get("logic", {}).get("confidence", 0.0))
    env = float(critics.get("environment", {}).get("confidence", 0.0))
    survival = float(critics.get("survival", {}).get("confidence", 0.0))
    return round((logic * 0.34) + (env * 0.33) + (survival * 0.33), 4)


def resolve_conflicts(
    cwd: str,
    prompt: str,
    distributed_report: dict,
    gate,
    arbitration: dict,
) -> dict:
    node_disagreement = not bool(distributed_report.get("agreement_pass", False))
    signal_conflict = not (
        bool(gate.critics.get("logic", {}).get("pass", False))
        == bool(gate.critics.get("environment", {}).get("pass", False))
        == bool(gate.critics.get("survival", {}).get("pass", False))
    )
    arbitration_winner = str(arbitration.get("winner", "")).strip() if arbitration.get("ok", False) else ""
    gate_output = str(gate.output or "").strip()
    reasoning_conflict = bool(arbitration_winner and gate_output and arbitration_winner != gate_output)

    gate_score = _combined_confidence(gate.critics)
    arb_score = float(arbitration.get("winner_score", 0.0)) if arbitration.get("ok", False) else 0.0

    chosen = gate_output
    method = "no_conflict"
    simulation = {"gate": {"pass": False, "forward_score": 0.0}, "arbitration": {"pass": False, "forward_score": 0.0}}

    if node_disagreement or signal_conflict or reasoning_conflict:
        method = "weighted_consensus"
        if arbitration_winner and arb_score > gate_score:
            chosen = arbitration_winner
        elif gate_output:
            chosen = gate_output
        elif arbitration_winner:
            chosen = arbitration_winner

        # Simulation comparison tie-break if both are available and close.
        if gate_output and arbitration_winner and abs(arb_score - gate_score) <= 0.08:
            sim_gate = simulate_candidate(prompt, gate_output)
            sim_arb = simulate_candidate(prompt, arbitration_winner)
            simulation = {"gate": sim_gate, "arbitration": sim_arb}
            method = "simulation_comparison"
            chosen = arbitration_winner if sim_arb.get("forward_score", 0.0) >= sim_gate.get("forward_score", 0.0) else gate_output

    out = {
        "ok": True,
        "conflicts": {
            "node_disagreement": node_disagreement,
            "signal_conflict": signal_conflict,
            "reasoning_conflict": reasoning_conflict,
        },
        "scores": {"gate_score": gate_score, "arbitration_score": round(arb_score, 4)},
        "method": method,
        "chosen_output": chosen,
        "simulation": simulation,
    }
    (_runtime(cwd) / "conflict_resolution.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


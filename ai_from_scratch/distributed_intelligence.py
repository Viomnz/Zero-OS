from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from ai_from_scratch.internal_zero_reasoner import InternalReasoningResult, run_internal_reasoning
except ModuleNotFoundError:
    from internal_zero_reasoner import InternalReasoningResult, run_internal_reasoning


@dataclass
class DistributedReasoningResult:
    selected_gate: InternalReasoningResult
    report: dict


def _node_workspace(cwd: str, node_name: str) -> str:
    node_root = Path(cwd).resolve() / ".zero_os" / "distributed_nodes" / node_name
    node_root.mkdir(parents=True, exist_ok=True)
    return str(node_root)


def run_distributed_reasoning(
    cwd: str,
    prompt: str,
    candidates: list[str],
    node_count: int = 3,
    agreement_threshold: float = 0.67,
) -> DistributedReasoningResult:
    count = max(1, min(9, int(node_count)))
    threshold = max(0.5, min(1.0, float(agreement_threshold)))
    node_names = [f"node_{i+1}" for i in range(count)]

    node_results: list[tuple[str, InternalReasoningResult]] = []
    for idx, node in enumerate(node_names):
        # Slight candidate rotation to reduce same-order bias across nodes.
        if candidates:
            rot = idx % len(candidates)
            node_candidates = candidates[rot:] + candidates[:rot]
        else:
            node_candidates = candidates
        gate = run_internal_reasoning(_node_workspace(cwd, node), prompt, node_candidates, max_attempts=9)
        node_results.append((node, gate))

    accepted_nodes = [n for n, g in node_results if g.accepted]
    failed_nodes = [n for n, g in node_results if not g.accepted]
    agreement_ratio = len(accepted_nodes) / max(1, len(node_results))
    agreement_pass = agreement_ratio >= threshold

    # Node-level selection: prefer first accepted node, else best fallback from node_1.
    selected_gate = next((g for _, g in node_results if g.accepted), node_results[0][1])
    recompute_triggered = False
    if not agreement_pass and len(accepted_nodes) >= 1:
        # Low agreement but survivable majority not reached: treat as recompute-isolation event.
        recompute_triggered = True

    report = {
        "node_count": len(node_results),
        "agreement_threshold": threshold,
        "agreement_ratio": round(agreement_ratio, 4),
        "agreement_pass": agreement_pass,
        "accepted_nodes": accepted_nodes,
        "failed_nodes": failed_nodes,
        "isolated_nodes": failed_nodes,
        "replacement_plan": [f"spawn_{n}_replacement" for n in failed_nodes],
        "recompute_triggered": recompute_triggered,
        "final_selected_node": next((n for n, g in node_results if g is selected_gate), node_results[0][0]),
        "nodes": [
            {
                "name": n,
                "accepted": g.accepted,
                "fallback_mode": g.fallback_mode,
                "attempts": g.attempts,
                "model_generation": g.model_generation,
            }
            for n, g in node_results
        ],
    }
    return DistributedReasoningResult(selected_gate=selected_gate, report=report)

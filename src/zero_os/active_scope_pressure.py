from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PressureCandidate:
    pressure_id: str
    expected_contradiction_yield: float
    independence_score: float
    ambiguity_reduction: float
    consequence_weight: float
    scope_expansion_value: float
    resource_cost: float
    discovery_fit: float | None = None


def select_next_scope_pressure(candidates: Iterable[PressureCandidate]) -> PressureCandidate | None:
    """Choose the next independent pressure without using discovery-fit score.

    Tiny Zero v4.x invariant: contested authority should trigger stronger,
    independent evidence collection rather than weaker certification standards.
    The discovery-fit field is deliberately ignored even when present.
    """
    rows = list(candidates)
    if not rows:
        return None

    def score(item: PressureCandidate) -> tuple[float, str]:
        cost = max(0.01, float(item.resource_cost))
        value = (
            2.0 * float(item.expected_contradiction_yield)
            + 2.0 * float(item.independence_score)
            + float(item.ambiguity_reduction)
            + float(item.consequence_weight)
            + float(item.scope_expansion_value)
        ) / cost
        return value, item.pressure_id

    return max(rows, key=score)

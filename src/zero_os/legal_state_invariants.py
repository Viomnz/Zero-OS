from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Any


@dataclass(frozen=True)
class Invariant:
    invariant_id: str
    description: str
    critical: bool = True


@dataclass(frozen=True)
class InvariantResult:
    invariant_id: str
    passed: bool
    detail: str


def evaluate_invariants(
    state: Mapping[str, Any],
    invariants: Iterable[tuple[Invariant, Callable[[Mapping[str, Any]], bool]]],
) -> tuple[InvariantResult, ...]:
    results: list[InvariantResult] = []
    for invariant, predicate in invariants:
        try:
            passed = bool(predicate(state))
            detail = "satisfied" if passed else "illegal_state_reachable_or_present"
        except Exception as exc:
            passed = False
            detail = f"invariant_evaluation_failed:{type(exc).__name__}"
        results.append(InvariantResult(invariant.invariant_id, passed, detail))
    return tuple(results)


def promotion_blocked_by_invariants(
    invariant_definitions: Iterable[Invariant],
    results: Iterable[InvariantResult],
) -> bool:
    critical = {item.invariant_id for item in invariant_definitions if item.critical}
    failed = {item.invariant_id for item in results if not item.passed}
    return bool(critical.intersection(failed))

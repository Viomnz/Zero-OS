from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class CapabilityEdge:
    principal_id: str
    scope: str
    required_for_objective: bool = False
    required_for_correction: bool = False
    removable: bool = True


@dataclass(frozen=True)
class CapabilityCompileResult:
    deployable: bool
    retained: tuple[CapabilityEdge, ...]
    removed: tuple[CapabilityEdge, ...]
    blocking_edges: tuple[CapabilityEdge, ...]
    reason: str


def compile_least_capability(edges: Iterable[CapabilityEdge]) -> CapabilityCompileResult:
    retained: list[CapabilityEdge] = []
    removed: list[CapabilityEdge] = []
    blocking: list[CapabilityEdge] = []

    for edge in edges:
        necessary = edge.required_for_objective or edge.required_for_correction
        if necessary:
            retained.append(edge)
            continue
        if edge.removable:
            removed.append(edge)
        else:
            blocking.append(edge)

    if blocking:
        return CapabilityCompileResult(
            False,
            tuple(retained),
            tuple(removed),
            tuple(blocking),
            "safe_deployment_denial_unnecessary_nonremovable_capability",
        )
    return CapabilityCompileResult(True, tuple(retained), tuple(removed), tuple(), "least_capability_compiled")

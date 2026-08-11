from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class EvidenceRequest:
    question: str
    target_scope: str
    preferred_method_family: str
    avoid_lineages: tuple[str, ...]
    expected_information_gain: str


def generate_evidence_requests(
    *,
    contested_scopes: Iterable[str],
    existing_method_families: Iterable[str] = (),
    existing_lineages: Iterable[str] = (),
) -> tuple[EvidenceRequest, ...]:
    used_methods = {str(x) for x in existing_method_families if str(x)}
    avoid = tuple(sorted({str(x) for x in existing_lineages if str(x)}))
    preferred_order = ("empirical_runtime", "formal_model", "adversarial_simulation", "independent_implementation")
    requests: list[EvidenceRequest] = []
    for scope in sorted({str(x) for x in contested_scopes if str(x)}):
        method = next((item for item in preferred_order if item not in used_methods), "novel_independent_method")
        requests.append(
            EvidenceRequest(
                question=f"What observation would discriminate whether scope {scope!r} is actually supported?",
                target_scope=scope,
                preferred_method_family=method,
                avoid_lineages=avoid,
                expected_information_gain="high",
            )
        )
        used_methods.add(method)
    return tuple(requests)

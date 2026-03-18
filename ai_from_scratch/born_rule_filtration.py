from __future__ import annotations

import json
from dataclasses import asdict, dataclass


DEFAULT_INTENSITY_PAIRS: tuple[tuple[float, float], ...] = (
    (0.5, 0.5),
    (0.25, 0.75),
    (0.2, 0.3),
    (1.0 / 3.0, 1.0 / 6.0),
    (0.1, 0.2),
)

DEFAULT_COMPOSITION_PAIRS: tuple[tuple[float, float], ...] = (
    (0.5, 0.5),
    (0.25, 0.75),
    (0.2, 0.3),
    (0.8, 0.9),
    (1.0 / 3.0, 2.0 / 3.0),
)

DEFAULT_EXPONENT_CANDIDATES: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)


@dataclass(frozen=True)
class CandidateCheck:
    amplitude_exponent: float
    intensity_exponent: float
    additive_error: float
    composition_error: float
    normalization_error: float
    total_error: float


def _checked_exponent(exponent: float) -> float:
    value = float(exponent)
    if value <= 0.0:
        raise ValueError("amplitude exponent must be positive")
    return value


def _checked_intensity(intensity: float) -> float:
    value = float(intensity)
    if value < 0.0 or value > 1.0:
        raise ValueError("intensity must be within [0, 1]")
    return value


def amplitude_probability(amplitude: complex | float, amplitude_exponent: float = 2.0) -> float:
    exponent = _checked_exponent(amplitude_exponent)
    return float(abs(complex(amplitude)) ** exponent)


def intensity_probability(intensity: float, amplitude_exponent: float = 2.0) -> float:
    exponent = _checked_exponent(amplitude_exponent) / 2.0
    return float(_checked_intensity(intensity) ** exponent)


def filtration_conditions() -> dict:
    return {
        "phase_blindness": "Probability is invariant under phase and depends only on branch intensity.",
        "coarse_grain_additivity": "Orthogonal sub-branches combine by addition of probabilities.",
        "serial_compositionality": "Independent sequential filters multiply.",
        "normalization": "Impossible branches map to 0 and certainty maps to 1.",
        "continuity": "Small intensity changes cannot create discontinuous probability jumps.",
    }


def evaluate_candidate_exponent(
    amplitude_exponent: float,
    intensity_pairs: tuple[tuple[float, float], ...] = DEFAULT_INTENSITY_PAIRS,
    composition_pairs: tuple[tuple[float, float], ...] = DEFAULT_COMPOSITION_PAIRS,
) -> CandidateCheck:
    exponent = _checked_exponent(amplitude_exponent)

    additive_error = 0.0
    for left, right in intensity_pairs:
        combined = intensity_probability(left + right, exponent)
        split = intensity_probability(left, exponent) + intensity_probability(right, exponent)
        additive_error = max(additive_error, abs(combined - split))

    composition_error = 0.0
    for left, right in composition_pairs:
        combined = intensity_probability(left * right, exponent)
        serial = intensity_probability(left, exponent) * intensity_probability(right, exponent)
        composition_error = max(composition_error, abs(combined - serial))

    normalization_error = max(
        abs(intensity_probability(0.0, exponent) - 0.0),
        abs(intensity_probability(1.0, exponent) - 1.0),
    )

    return CandidateCheck(
        amplitude_exponent=float(exponent),
        intensity_exponent=float(exponent / 2.0),
        additive_error=float(additive_error),
        composition_error=float(composition_error),
        normalization_error=float(normalization_error),
        total_error=float(additive_error + composition_error + normalization_error),
    )


def derive_born_rule_from_filtration(
    exponent_candidates: tuple[float, ...] = DEFAULT_EXPONENT_CANDIDATES,
    tolerance: float = 1e-9,
) -> dict:
    candidates = tuple(float(item) for item in exponent_candidates)
    if not candidates:
        raise ValueError("at least one exponent candidate is required")

    reports = [evaluate_candidate_exponent(item) for item in candidates]
    reports_sorted = sorted(reports, key=lambda item: (item.total_error, abs(item.amplitude_exponent - 2.0)))
    winner = reports_sorted[0]

    passing = [
        item.amplitude_exponent
        for item in reports_sorted
        if item.additive_error <= tolerance
        and item.composition_error <= tolerance
        and item.normalization_error <= tolerance
    ]

    return {
        "conditions": filtration_conditions(),
        "derived_probability_law": "P(a) = |a|^2",
        "winner": asdict(winner),
        "passing_amplitude_exponents": passing,
        "born_rule_unique": passing == [2.0],
        "candidate_reports": [asdict(item) for item in reports_sorted],
        "proof_outline": [
            "Define G(s) as the branch probability assigned to intensity s = |a|^2.",
            "Coarse-grain additivity plus continuity forces G(s) to be linear on [0, 1].",
            "Normalization fixes G(0) = 0 and G(1) = 1, so G(s) = s.",
            "Therefore P(a) = G(|a|^2) = |a|^2.",
            "Any competing power law P(a) = |a|^p implies G(s) = s^(p/2), which violates additivity unless p = 2.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(derive_born_rule_from_filtration(), indent=2))

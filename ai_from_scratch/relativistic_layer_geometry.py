from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass


DEFAULT_SIGNAL_SPEED = 1.0
DEFAULT_SAMPLE_VELOCITY = 0.6
DEFAULT_EVENTS: tuple[tuple[float, float, float, float], ...] = (
    (1.0, 0.2, 0.0, 0.0),
    (1.5, 0.4, 0.1, 0.0),
    (2.0, 0.9, 0.3, 0.2),
    (3.0, 1.0, 0.0, 0.5),
)
DEFAULT_NULL_EVENTS: tuple[tuple[float, float, float, float], ...] = (
    (1.0, 1.0, 0.0, 0.0),
    (2.0, -2.0, 0.0, 0.0),
)


@dataclass(frozen=True)
class GeometryCandidateCheck:
    name: str
    null_error: float
    interval_error: float
    reciprocity_error: float
    total_error: float
    passes: bool


def _checked_signal_speed(c: float) -> float:
    value = float(c)
    if value <= 0.0:
        raise ValueError("signal speed must be positive")
    return value


def _checked_velocity(v: float, c: float) -> float:
    speed_limit = _checked_signal_speed(c)
    value = float(v)
    if abs(value) >= speed_limit:
        raise ValueError("velocity magnitude must stay below signal speed")
    return value


def minkowski_interval(event: tuple[float, float, float, float], c: float = DEFAULT_SIGNAL_SPEED) -> float:
    t, x, y, z = (float(item) for item in event)
    speed = _checked_signal_speed(c)
    return float((speed * t) ** 2 - x**2 - y**2 - z**2)


def lorentz_gamma(v: float, c: float = DEFAULT_SIGNAL_SPEED) -> float:
    velocity = _checked_velocity(v, c)
    speed = _checked_signal_speed(c)
    return float(1.0 / math.sqrt(1.0 - (velocity * velocity) / (speed * speed)))


def lorentz_boost(event: tuple[float, float, float, float], v: float, c: float = DEFAULT_SIGNAL_SPEED) -> tuple[float, float, float, float]:
    t, x, y, z = (float(item) for item in event)
    speed = _checked_signal_speed(c)
    velocity = _checked_velocity(v, speed)
    gamma = lorentz_gamma(velocity, speed)
    transformed_t = gamma * (t - (velocity * x) / (speed * speed))
    transformed_x = gamma * (x - velocity * t)
    return (float(transformed_t), float(transformed_x), float(y), float(z))


def galilean_boost(event: tuple[float, float, float, float], v: float, c: float = DEFAULT_SIGNAL_SPEED) -> tuple[float, float, float, float]:
    t, x, y, z = (float(item) for item in event)
    velocity = _checked_velocity(v, c)
    return (float(t), float(x - velocity * t), float(y), float(z))


def _null_error(
    transform,
    null_events: tuple[tuple[float, float, float, float], ...],
    v: float,
    c: float,
) -> float:
    error = 0.0
    speed = _checked_signal_speed(c)
    for event in null_events:
        transformed = transform(event, v, speed)
        error = max(error, abs(minkowski_interval(transformed, speed)))
    return float(error)


def _interval_error(
    metric,
    transform,
    events: tuple[tuple[float, float, float, float], ...],
    v: float,
    c: float,
) -> float:
    error = 0.0
    speed = _checked_signal_speed(c)
    for event in events:
        transformed = transform(event, v, speed)
        error = max(error, abs(metric(event, speed) - metric(transformed, speed)))
    return float(error)


def _reciprocity_error(
    transform,
    events: tuple[tuple[float, float, float, float], ...],
    v: float,
    c: float,
) -> float:
    error = 0.0
    speed = _checked_signal_speed(c)
    for event in events:
        transformed = transform(event, v, speed)
        recovered = transform(transformed, -v, speed)
        error = max(error, max(abs(a - b) for a, b in zip(event, recovered)))
    return float(error)


def evaluate_geometry_candidates(v: float = DEFAULT_SAMPLE_VELOCITY, c: float = DEFAULT_SIGNAL_SPEED) -> list[GeometryCandidateCheck]:
    speed = _checked_signal_speed(c)
    velocity = _checked_velocity(v, speed)

    candidates = (
        (
            "lorentzian_minkowski",
            minkowski_interval,
            lorentz_boost,
        ),
        (
            "galilean_absolute_time",
            minkowski_interval,
            galilean_boost,
        ),
    )

    reports: list[GeometryCandidateCheck] = []
    for name, metric, transform in candidates:
        null_error = _null_error(transform, DEFAULT_NULL_EVENTS, velocity, speed)
        interval_error = _interval_error(metric, transform, DEFAULT_EVENTS + DEFAULT_NULL_EVENTS, velocity, speed)
        reciprocity_error = _reciprocity_error(transform, DEFAULT_EVENTS, velocity, speed)
        total_error = null_error + interval_error + reciprocity_error
        reports.append(
            GeometryCandidateCheck(
                name=name,
                null_error=float(null_error),
                interval_error=float(interval_error),
                reciprocity_error=float(reciprocity_error),
                total_error=float(total_error),
                passes=bool(total_error <= 1e-9),
            )
        )
    return sorted(reports, key=lambda item: (item.total_error, item.name))


def derive_spacetime_from_classical_layer_geometry(
    v: float = DEFAULT_SAMPLE_VELOCITY,
    c: float = DEFAULT_SIGNAL_SPEED,
) -> dict:
    speed = _checked_signal_speed(c)
    velocity = _checked_velocity(v, speed)
    reports = evaluate_geometry_candidates(velocity, speed)
    winner = reports[0]
    passing = [item.name for item in reports if item.passes]

    return {
        "classical_layer_geometry": {
            "space": "Each update layer carries Euclidean spatial coordinates.",
            "time": "Successive layers are indexed by a uniform update interval dt.",
            "causality": f"Signals can move at most speed c = {speed} from one layer stack to the next.",
        },
        "conditions": {
            "homogeneity": "The same rule applies at every layer and position.",
            "isotropy": "No spatial direction is preferred.",
            "linearity": "Uniform relative motion maps straight worldlines to straight worldlines.",
            "reciprocity": "Boosting by v and then by -v returns the original event.",
            "signal_speed_invariance": "Maximal causal propagation speed c is identical in every inertial frame.",
        },
        "derived_metric": "ds^2 = c^2 dt^2 - dx^2 - dy^2 - dz^2",
        "derived_boost": {
            "x_prime": "gamma (x - v t)",
            "t_prime": "gamma (t - v x / c^2)",
            "gamma": "1 / sqrt(1 - v^2 / c^2)",
        },
        "winner": asdict(winner),
        "passing_geometries": passing,
        "lorentzian_unique": passing == ["lorentzian_minkowski"],
        "candidate_reports": [asdict(item) for item in reports],
        "proof_outline": [
            "Start with a classical layered geometry: spatial coordinates plus a uniform layer index.",
            "Impose a finite invariant signal speed c as the maximal one-layer propagation rate.",
            "Require inertial frame changes to be linear, reciprocal, homogeneous, and isotropic.",
            "Demand that null propagation x = plus/minus c t stays null in every inertial frame.",
            "These constraints force the Lorentz boost and therefore the Minkowski interval.",
            "Galilean time fails because it changes the null cone and breaks invariant signal speed.",
        ],
        "sample_velocity": float(velocity),
        "signal_speed": float(speed),
    }


if __name__ == "__main__":
    print(json.dumps(derive_spacetime_from_classical_layer_geometry(), indent=2))

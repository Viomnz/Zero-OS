from __future__ import annotations

from dataclasses import dataclass

from zero_os.hal import ComputeHAL, WorkloadSpec
from zero_os.performance import ComputeTier, HardwareInfo


@dataclass(frozen=True)
class ScheduleDecision:
    lane: str
    queue: str
    backend: str
    tier: ComputeTier
    reason: str


class SchedulerRouter:
    def __init__(self) -> None:
        self.hal = ComputeHAL()

    def route(self, lane: str, hw: HardwareInfo, tier: ComputeTier, profile: dict) -> ScheduleDecision:
        lane_norm = lane.strip().lower()
        spec = WorkloadSpec(
            lane=lane_norm,
            latency_sensitive=lane_norm == "interactive",
            distributed=lane_norm == "distributed" or tier in {"tier3", "tier4"},
            quantum_candidate=lane_norm == "quantum",
        )
        target = self.hal.allocate(spec, hw, tier)

        queue = "interactive"
        if lane_norm == "batch":
            queue = "batch"
        elif lane_norm == "distributed":
            queue = "cluster"
        elif lane_norm == "quantum":
            queue = "quantum"

        return ScheduleDecision(
            lane=lane_norm,
            queue=queue,
            backend=target.backend,
            tier=tier,
            reason=f"tier={tier}, fallback={profile.get('fallback', 'cpu-local')}",
        )

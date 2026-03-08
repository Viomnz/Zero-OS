from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from zero_os.performance import ComputeTier, HardwareInfo


@dataclass(frozen=True)
class WorkloadSpec:
    lane: str
    latency_sensitive: bool = False
    distributed: bool = False
    quantum_candidate: bool = False


@dataclass(frozen=True)
class ExecutionTarget:
    backend: str
    tier: ComputeTier
    notes: str


class ComputeBackend(Protocol):
    name: str

    def can_run(self, spec: WorkloadSpec, hw: HardwareInfo, tier: ComputeTier) -> bool:
        ...

    def target(self, tier: ComputeTier) -> ExecutionTarget:
        ...


class CpuBackend:
    name = "cpu-local"

    def can_run(self, spec: WorkloadSpec, hw: HardwareInfo, tier: ComputeTier) -> bool:
        return True

    def target(self, tier: ComputeTier) -> ExecutionTarget:
        return ExecutionTarget(backend=self.name, tier=tier, notes="Portable baseline backend")


class GpuBackend:
    name = "gpu-local"

    def can_run(self, spec: WorkloadSpec, hw: HardwareInfo, tier: ComputeTier) -> bool:
        return hw.gpu_count > 0 and tier in {"tier2", "tier3", "tier4"}

    def target(self, tier: ComputeTier) -> ExecutionTarget:
        return ExecutionTarget(backend=self.name, tier=tier, notes="CUDA/ROCm-capable acceleration")


class DistributedBackend:
    name = "distributed-cluster"

    def can_run(self, spec: WorkloadSpec, hw: HardwareInfo, tier: ComputeTier) -> bool:
        return bool(spec.distributed or tier in {"tier3", "tier4"}) and hw.distributed_ready

    def target(self, tier: ComputeTier) -> ExecutionTarget:
        return ExecutionTarget(backend=self.name, tier=tier, notes="Cluster scheduler adapter (Ray/Slurm/K8s)")


class QuantumBackend:
    name = "quantum-hybrid"

    def can_run(self, spec: WorkloadSpec, hw: HardwareInfo, tier: ComputeTier) -> bool:
        return bool(spec.quantum_candidate or tier == "tier4") and hw.quantum_ready

    def target(self, tier: ComputeTier) -> ExecutionTarget:
        return ExecutionTarget(backend=self.name, tier=tier, notes="Hybrid quantum-classical adapter")


class ComputeHAL:
    def __init__(self) -> None:
        self.backends: tuple[ComputeBackend, ...] = (
            QuantumBackend(),
            DistributedBackend(),
            GpuBackend(),
            CpuBackend(),
        )

    def allocate(self, spec: WorkloadSpec, hw: HardwareInfo, tier: ComputeTier) -> ExecutionTarget:
        for backend in self.backends:
            if backend.can_run(spec, hw, tier):
                return backend.target(tier)
        return CpuBackend().target(tier)

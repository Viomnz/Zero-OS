"""Performance and compute tier profiling."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

PerformanceProfile = Literal["low", "balanced", "high"]
ComputeTier = Literal["tier1", "tier2", "tier3", "tier4"]


@dataclass(frozen=True)
class HardwareInfo:
    cpu_cores: int
    memory_gb: float
    gpu_count: int = 0
    distributed_ready: bool = False
    quantum_ready: bool = False


def detect_hardware() -> HardwareInfo:
    cores = max(1, os.cpu_count() or 1)
    memory_gb = 4.0
    gpu_count = 0
    distributed_ready = False
    quantum_ready = False
    try:
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        memory_gb = round(status.ullTotalPhys / (1024 ** 3), 2)
    except Exception:
        memory_gb = 4.0

    # Lightweight feature flags for higher tiers.
    gpu_count = int(os.getenv("ZERO_OS_GPU_COUNT", "0") or 0)
    distributed_ready = os.getenv("ZERO_OS_DISTRIBUTED_READY", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    quantum_ready = os.getenv("ZERO_OS_QUANTUM_READY", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return HardwareInfo(
        cpu_cores=cores,
        memory_gb=memory_gb,
        gpu_count=max(0, gpu_count),
        distributed_ready=distributed_ready,
        quantum_ready=quantum_ready,
    )


def compute_tier_from_hardware(info: HardwareInfo) -> ComputeTier:
    if info.quantum_ready:
        return "tier4"
    if info.distributed_ready:
        return "tier3"
    if info.cpu_cores >= 8 and info.memory_gb >= 16:
        return "tier2"
    return "tier1"


def legacy_profile_from_tier(tier: ComputeTier) -> PerformanceProfile:
    if tier == "tier1":
        return "low"
    if tier == "tier2":
        return "high"
    return "high"


def profile_from_hardware(info: HardwareInfo) -> PerformanceProfile:
    # Backward-compatible profile view derived from compute tier.
    return legacy_profile_from_tier(compute_tier_from_hardware(info))


def effective_profile(setting: str, info: HardwareInfo) -> tuple[ComputeTier, PerformanceProfile]:
    normalized = setting.lower().strip()
    auto_tier = compute_tier_from_hardware(info)
    if normalized == "auto":
        return auto_tier, legacy_profile_from_tier(auto_tier)
    if normalized in {"tier1", "tier2", "tier3", "tier4"}:
        tier = normalized  # type: ignore[assignment]
        return tier, legacy_profile_from_tier(tier)  # type: ignore[arg-type]
    if normalized in {"low", "balanced", "high"}:
        # Legacy setting remains supported.
        return auto_tier, normalized  # type: ignore[return-value]
    return auto_tier, legacy_profile_from_tier(auto_tier)

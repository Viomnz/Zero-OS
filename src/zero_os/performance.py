"""Performance profiling for low-end to high-end PCs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

PerformanceProfile = Literal["low", "balanced", "high"]


@dataclass(frozen=True)
class HardwareInfo:
    cpu_cores: int
    memory_gb: float


def detect_hardware() -> HardwareInfo:
    cores = max(1, os.cpu_count() or 1)
    memory_gb = 4.0
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
    return HardwareInfo(cpu_cores=cores, memory_gb=memory_gb)


def profile_from_hardware(info: HardwareInfo) -> PerformanceProfile:
    if info.cpu_cores <= 2 or info.memory_gb < 4:
        return "low"
    if info.cpu_cores >= 8 and info.memory_gb >= 16:
        return "high"
    return "balanced"


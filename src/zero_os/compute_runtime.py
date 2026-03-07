from __future__ import annotations

import json
from pathlib import Path

from zero_os.performance import detect_hardware, effective_profile
from zero_os.scheduler import SchedulerRouter


def _default_profiles() -> dict:
    return {
        "tier1": {"fallback": "cpu-local"},
        "tier2": {"fallback": "gpu-local"},
        "tier3": {"fallback": "distributed-cluster"},
        "tier4": {"fallback": "quantum-hybrid"},
    }


def load_compute_profiles(cwd: str) -> dict:
    path = Path(cwd).resolve() / "zero_os_config" / "compute_profiles.yaml"
    if not path.exists():
        return _default_profiles()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return _default_profiles()


def initialize_compute_runtime(cwd: str, profile_setting: str) -> dict:
    hw = detect_hardware()
    tier, profile = effective_profile(profile_setting, hw)
    profiles = load_compute_profiles(cwd)
    scheduler = SchedulerRouter()

    decisions = {}
    for lane in ("interactive", "batch", "distributed", "quantum"):
        decision = scheduler.route(lane=lane, hw=hw, tier=tier, profile=profiles.get(tier, {}))
        decisions[lane] = {
            "queue": decision.queue,
            "backend": decision.backend,
            "reason": decision.reason,
        }

    payload = {
        "schema_version": 1,
        "tier": tier,
        "profile": profile,
        "hardware": {
            "cpu_cores": hw.cpu_cores,
            "memory_gb": hw.memory_gb,
            "gpu_count": hw.gpu_count,
            "distributed_ready": hw.distributed_ready,
            "quantum_ready": hw.quantum_ready,
        },
        "profiles": profiles,
        "scheduler": decisions,
    }

    runtime = Path(cwd).resolve() / ".zero_os" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "compute_runtime.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return payload

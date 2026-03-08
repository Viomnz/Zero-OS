"""Performance profile capability."""

from __future__ import annotations

from zero_os.performance import compute_tier_from_hardware, detect_hardware, effective_profile
from zero_os.state import get_profile_setting, set_profile_setting
from zero_os.types import Result, Task


class ProfileCapability:
    name = "profile"

    def can_handle(self, task: Task) -> bool:
        return task.text.lower().strip().startswith("profile ")

    def run(self, task: Task) -> Result:
        text = task.text.lower().strip()
        if text == "profile show":
            info = detect_hardware()
            setting = get_profile_setting(task.cwd)
            tier = compute_tier_from_hardware(info)
            active_tier, active = effective_profile(setting, info)
            return Result(
                self.name,
                (
                    f"Profile setting: {setting}\n"
                    f"Auto compute tier: {tier}\n"
                    f"Active compute tier: {active_tier}\n"
                    f"Active profile: {active}\n"
                    "Hardware: "
                    f"cpu_cores={info.cpu_cores}, memory_gb={info.memory_gb}, "
                    f"gpu_count={info.gpu_count}, distributed_ready={info.distributed_ready}, "
                    f"quantum_ready={info.quantum_ready}"
                ),
            )
        if text.startswith("profile set "):
            target = text.replace("profile set ", "", 1).strip()
            try:
                value = set_profile_setting(task.cwd, target)
            except ValueError:
                return Result(
                    self.name,
                    "Supported profiles: auto, low, balanced, high, tier1, tier2, tier3, tier4",
                )
            return Result(self.name, f"Profile setting updated: {value}")
        return Result(
            self.name,
            "Profile commands:\n- profile show\n- profile set auto|low|balanced|high|tier1|tier2|tier3|tier4",
        )

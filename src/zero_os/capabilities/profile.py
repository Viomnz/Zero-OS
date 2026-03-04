"""Performance profile capability."""

from __future__ import annotations

from zero_os.performance import detect_hardware, profile_from_hardware
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
            auto = profile_from_hardware(info)
            setting = get_profile_setting(task.cwd)
            active = auto if setting == "auto" else setting
            return Result(
                self.name,
                (
                    f"Profile setting: {setting}\n"
                    f"Active profile: {active}\n"
                    f"Hardware: cpu_cores={info.cpu_cores}, memory_gb={info.memory_gb}"
                ),
            )
        if text.startswith("profile set "):
            target = text.replace("profile set ", "", 1).strip()
            try:
                value = set_profile_setting(task.cwd, target)
            except ValueError:
                return Result(self.name, "Supported profiles: auto, low, balanced, high")
            return Result(self.name, f"Profile setting updated: {value}")
        return Result(
            self.name,
            "Profile commands:\n- profile show\n- profile set auto|low|balanced|high",
        )


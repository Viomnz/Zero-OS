"""Single highway router for Zero OS."""

from __future__ import annotations

from zero_os.capabilities.agent import AgentCapability
from zero_os.capabilities.code import CodeCapability
from zero_os.capabilities.memory import MemoryCapability
from zero_os.capabilities.mode import ModeCapability
from zero_os.capabilities.profile import ProfileCapability
from zero_os.capabilities.system import SystemCapability
from zero_os.capabilities.web import WebCapability
from zero_os.core import CORE_POLICY, CorePolicy, run_survival_protocols
from zero_os.performance import detect_hardware, profile_from_hardware
from zero_os.plugins import load_plugins
from zero_os.state import get_mode
from zero_os.state import get_profile_setting
from zero_os.types import Capability, Result, Task


class Highway:
    """One path in, one routing decision, one unified result."""

    def __init__(self, cwd: str = ".") -> None:
        self.core: CorePolicy = CORE_POLICY
        self._cwd = cwd
        self._plugin_capabilities: tuple[Capability, ...] = load_plugins(cwd)
        self._non_agent_capabilities: tuple[Capability, ...] = (
            ModeCapability(),
            ProfileCapability(),
            CodeCapability(),
            WebCapability(),
            SystemCapability(),
            MemoryCapability(),
            *self._plugin_capabilities,
        )
        self.capabilities: tuple[Capability, ...] = (
            AgentCapability(self._dispatch_non_agent),
            *self._non_agent_capabilities,
        )

    def dispatch(self, text: str, cwd: str = ".") -> Result:
        if self.core.authentication_required:
            return Result("core", "Authentication is required by policy.")
        mode = get_mode(cwd)
        profile_setting = get_profile_setting(cwd)
        auto_profile = profile_from_hardware(detect_hardware())
        active_profile = auto_profile if profile_setting == "auto" else profile_setting
        task = Task(
            text=text,
            cwd=cwd,
            mode=mode,
            performance_profile=active_profile,
            recursion_depth=0,
        )
        survival_state, survival_msg = run_survival_protocols(self.core, task)
        if survival_state != "ok":
            return Result("core", survival_msg)
        for capability in self.capabilities:
            if capability.can_handle(task):
                return capability.run(task)

        return Result(
            capability="fallback",
            summary=(
                "No lane matched this task yet. Add a capability or expand keywords."
            ),
        )

    def _dispatch_non_agent(self, text: str, cwd: str) -> Result:
        mode = get_mode(cwd)
        profile_setting = get_profile_setting(cwd)
        auto_profile = profile_from_hardware(detect_hardware())
        active_profile = auto_profile if profile_setting == "auto" else profile_setting
        task = Task(
            text=text,
            cwd=cwd,
            mode=mode,
            performance_profile=active_profile,
            recursion_depth=1,
        )
        survival_state, survival_msg = run_survival_protocols(self.core, task)
        if survival_state != "ok":
            return Result("core", survival_msg)
        for capability in self._non_agent_capabilities:
            if capability.can_handle(task):
                return capability.run(task)
        return Result("fallback", f"No lane matched: {text}")

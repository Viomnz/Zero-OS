from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from zero_os.capability_lease import current_capability_lease


@dataclass(frozen=True)
class ProcessDecision:
    allowed: bool
    reason: str
    executable: str
    required_scope: str


PROCESS_SCOPES = {
    "python": "process:python",
    "python3": "process:python",
    "pytest": "process:test",
    "git": "process:git",
    "gh": "process:github_cli",
    "docker": "process:container",
    "podman": "process:container",
    "systemctl": "process:service_control",
    "launchctl": "process:service_control",
    "powershell": "process:shell",
    "pwsh": "process:shell",
    "cmd": "process:shell",
    "bash": "process:shell",
    "sh": "process:shell",
    "zsh": "process:shell",
}


def classify_executable(executable: str) -> str:
    name = Path(str(executable or "")).name.lower()
    return PROCESS_SCOPES.get(name, "process:unclassified")


def authorize_process(executable: str) -> ProcessDecision:
    exe = Path(str(executable or "")).name.lower()
    required_scope = classify_executable(executable)
    if required_scope == "process:unclassified":
        return ProcessDecision(False, "unclassified_process_family", exe, required_scope)
    lease = current_capability_lease()
    if lease is None:
        return ProcessDecision(False, "capability_lease_missing", exe, required_scope)
    if not lease.active():
        return ProcessDecision(False, "capability_lease_expired", exe, required_scope)
    if required_scope not in lease.scopes:
        return ProcessDecision(False, "process_scope_missing", exe, required_scope)
    return ProcessDecision(True, "scoped_process_authority", exe, required_scope)

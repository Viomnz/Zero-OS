from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class IssuerMode(str, Enum):
    IN_PROCESS_DEVELOPMENT = "IN_PROCESS_DEVELOPMENT"
    SEPARATE_PROCESS = "SEPARATE_PROCESS"
    OS_PROTECTED = "OS_PROTECTED"
    HARDWARE_BACKED = "HARDWARE_BACKED"


@dataclass(frozen=True)
class IssuerBoundaryStatus:
    mode: IssuerMode
    private_key_exposed_to_runtime: bool
    separate_process: bool
    separate_os_identity: bool
    hardware_backed: bool
    production_authority_permitted: bool
    demonstrated_scope: tuple[str, ...]
    unresolved_scope: tuple[str, ...]


class AuthorityIssuerBackend(Protocol):
    def status(self) -> IssuerBoundaryStatus: ...


def assess_issuer_boundary(
    mode: IssuerMode,
    *,
    private_key_exposed_to_runtime: bool,
    separate_process: bool = False,
    separate_os_identity: bool = False,
    hardware_backed: bool = False,
) -> IssuerBoundaryStatus:
    demonstrated = ["signed_authority_artifacts", "exact_claim_action_scope_binding"]
    unresolved = []

    if private_key_exposed_to_runtime:
        unresolved.append("runtime_can_access_issuer_private_key")
    if not separate_process:
        unresolved.append("issuer_not_process_isolated")
    if not separate_os_identity:
        unresolved.append("issuer_not_os_identity_isolated")
    if not hardware_backed:
        unresolved.append("issuer_key_not_hardware_backed")

    if separate_process:
        demonstrated.append("process_boundary")
    if separate_os_identity:
        demonstrated.append("os_identity_boundary")
    if hardware_backed:
        demonstrated.append("hardware_key_boundary")

    production = (
        mode in {IssuerMode.OS_PROTECTED, IssuerMode.HARDWARE_BACKED}
        and not private_key_exposed_to_runtime
        and separate_process
        and separate_os_identity
    )
    if mode == IssuerMode.HARDWARE_BACKED:
        production = production and hardware_backed

    return IssuerBoundaryStatus(
        mode=mode,
        private_key_exposed_to_runtime=private_key_exposed_to_runtime,
        separate_process=separate_process,
        separate_os_identity=separate_os_identity,
        hardware_backed=hardware_backed,
        production_authority_permitted=production,
        demonstrated_scope=tuple(demonstrated),
        unresolved_scope=tuple(unresolved),
    )


def current_software_issuer_status() -> IssuerBoundaryStatus:
    """Truthful status for the current v9 software implementation.

    The HMAC issuer is useful against trivial artifact forgery but shares the
    runtime's privilege domain. It therefore cannot certify production root-of-
    trust isolation.
    """
    return assess_issuer_boundary(
        IssuerMode.IN_PROCESS_DEVELOPMENT,
        private_key_exposed_to_runtime=True,
        separate_process=False,
        separate_os_identity=False,
        hardware_backed=False,
    )

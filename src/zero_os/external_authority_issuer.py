from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from zero_os.authority_issuer_boundary import IssuerBoundaryStatus, IssuerMode, assess_issuer_boundary
from zero_os.authority_root_of_trust import AuthorityAttestation


@dataclass(frozen=True)
class ExternalIssuerDescriptor:
    issuer_id: str
    transport: str
    endpoint: str
    public_key_path: str
    separate_process: bool
    separate_os_identity: bool
    hardware_backed: bool
    private_key_unavailable_to_runtime: bool

    @property
    def production_ready(self) -> bool:
        return bool(
            self.separate_process
            and self.separate_os_identity
            and self.private_key_unavailable_to_runtime
        )


class ExternalIssuerTransport(Protocol):
    def request_attestation(self, payload: dict[str, Any]) -> dict[str, Any]: ...


def descriptor_path(cwd: str) -> Path:
    return Path(cwd).resolve() / ".zero_os" / "authority_root" / "external_issuer.json"


def load_external_issuer_descriptor(cwd: str) -> ExternalIssuerDescriptor | None:
    path = descriptor_path(cwd)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace") or "{}")
        descriptor = ExternalIssuerDescriptor(
            issuer_id=str(raw.get("issuer_id", "")),
            transport=str(raw.get("transport", "")),
            endpoint=str(raw.get("endpoint", "")),
            public_key_path=str(raw.get("public_key_path", "")),
            separate_process=bool(raw.get("separate_process", False)),
            separate_os_identity=bool(raw.get("separate_os_identity", False)),
            hardware_backed=bool(raw.get("hardware_backed", False)),
            private_key_unavailable_to_runtime=bool(raw.get("private_key_unavailable_to_runtime", False)),
        )
    except (ValueError, TypeError, OSError):
        return None
    if not descriptor.issuer_id or not descriptor.transport or not descriptor.endpoint or not descriptor.public_key_path:
        return None
    return descriptor


def assess_external_issuer(cwd: str) -> IssuerBoundaryStatus:
    descriptor = load_external_issuer_descriptor(cwd)
    if descriptor is None:
        return assess_issuer_boundary(
            IssuerMode.IN_PROCESS_DEVELOPMENT,
            private_key_exposed_to_runtime=True,
            separate_process=False,
            separate_os_identity=False,
            hardware_backed=False,
        )
    mode = IssuerMode.HARDWARE_BACKED if descriptor.hardware_backed else IssuerMode.OS_PROTECTED
    return assess_issuer_boundary(
        mode,
        private_key_exposed_to_runtime=not descriptor.private_key_unavailable_to_runtime,
        separate_process=descriptor.separate_process,
        separate_os_identity=descriptor.separate_os_identity,
        hardware_backed=descriptor.hardware_backed,
    )


def request_external_attestation(
    cwd: str,
    *,
    transport: ExternalIssuerTransport,
    constitutional_payload: dict[str, Any],
) -> AuthorityAttestation:
    descriptor = load_external_issuer_descriptor(cwd)
    if descriptor is None or not descriptor.production_ready:
        raise PermissionError("production external issuer boundary is not configured")
    response = transport.request_attestation({
        "issuer_id": descriptor.issuer_id,
        "request": dict(constitutional_payload),
    })
    try:
        attestation = AuthorityAttestation(**dict(response.get("attestation") or {}))
    except (TypeError, ValueError) as exc:
        raise PermissionError("external issuer returned invalid attestation") from exc
    if attestation.issuer_id != descriptor.issuer_id:
        raise PermissionError("external issuer identity mismatch")
    return attestation


def external_issuer_status(cwd: str) -> dict[str, Any]:
    descriptor = load_external_issuer_descriptor(cwd)
    boundary = assess_external_issuer(cwd)
    return {
        "configured": descriptor is not None,
        "descriptor": asdict(descriptor) if descriptor is not None else None,
        "boundary": {
            "mode": boundary.mode.value,
            "private_key_exposed_to_runtime": boundary.private_key_exposed_to_runtime,
            "separate_process": boundary.separate_process,
            "separate_os_identity": boundary.separate_os_identity,
            "hardware_backed": boundary.hardware_backed,
            "production_authority_permitted": boundary.production_authority_permitted,
            "demonstrated_scope": list(boundary.demonstrated_scope),
            "unresolved_scope": list(boundary.unresolved_scope),
        },
    }

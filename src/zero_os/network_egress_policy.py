from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse

from zero_os.capability_lease import active_lease


@dataclass(frozen=True)
class EgressDecision:
    allowed: bool
    reason: str
    host: str
    scheme: str
    requires_credential_scope: bool = False


def _is_local_or_private_host(host: str) -> bool:
    h = str(host or "").strip().lower()
    if h in {"localhost", "localhost.localdomain"} or h.endswith(".local"):
        return True
    try:
        addr = ip_address(h)
        return bool(addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved)
    except ValueError:
        return False


def evaluate_egress(url: str, *, headers: dict[str, str] | None = None, write: bool = False) -> EgressDecision:
    parsed = urlparse(str(url or ""))
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"https", "http"}:
        return EgressDecision(False, "unsupported_network_scheme", host, scheme)
    if not host:
        return EgressDecision(False, "network_host_missing", host, scheme)

    lease = active_lease()
    if lease is None:
        return EgressDecision(False, "capability_lease_missing", host, scheme)

    required_scope = "network:write" if write else "network:read"
    if required_scope not in lease.scopes:
        return EgressDecision(False, "network_scope_missing", host, scheme)

    # Destination binding is optional only for legacy leases. New leases should
    # carry host:<hostname> or host:* explicitly. A specific host cannot be reused.
    host_scope = f"host:{host}"
    if "host:*" not in lease.scopes and host_scope not in lease.scopes:
        return EgressDecision(False, "destination_scope_missing", host, scheme)

    header_names = {str(k).strip().lower() for k in dict(headers or {})}
    credential_bearing = bool({"authorization", "proxy-authorization", "x-api-key", "api-key"} & header_names)
    if credential_bearing and "credential:transmit" not in lease.scopes:
        return EgressDecision(False, "credential_transmit_scope_missing", host, scheme, True)

    # Private/local destinations need an explicit local-network scope to reduce
    # SSRF-style authority expansion from public network permission.
    if _is_local_or_private_host(host) and "network:local" not in lease.scopes:
        return EgressDecision(False, "local_network_scope_missing", host, scheme, credential_bearing)

    return EgressDecision(True, "scoped_egress_allowed", host, scheme, credential_bearing)

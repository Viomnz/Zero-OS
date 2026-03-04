"""Immutable Zero-OS core policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CorePolicy:
    """Core behavior that cannot be changed at runtime."""

    immutable_core: bool
    authentication_required: bool
    policy_name: str


CORE_POLICY = CorePolicy(
    immutable_core=True,
    authentication_required=False,
    policy_name="zero-os-immutable-no-auth",
)


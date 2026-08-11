from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LinuxBrokerProfile:
    runtime_user: str
    broker_user: str
    protected_store: str
    broker_socket: str
    private_key_store: str

    def validate(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.runtime_user or not self.broker_user:
            reasons.append("linux_broker_identity_missing")
        if self.runtime_user == self.broker_user:
            reasons.append("linux_runtime_and_broker_user_must_differ")
        for value, name in (
            (self.protected_store, "protected_store"),
            (self.broker_socket, "broker_socket"),
            (self.private_key_store, "private_key_store"),
        ):
            if not str(value).startswith("/"):
                reasons.append(f"{name}_must_be_absolute")
        return tuple(reasons)

    def systemd_hardening_requirements(self) -> dict[str, str]:
        return {
            "User": self.broker_user,
            "NoNewPrivileges": "yes",
            "PrivateTmp": "yes",
            "ProtectSystem": "strict",
            "ProtectHome": "yes",
            "PrivateDevices": "yes",
            "ProtectKernelTunables": "yes",
            "ProtectKernelModules": "yes",
            "ProtectKernelLogs": "yes",
            "ProtectControlGroups": "yes",
            "RestrictSUIDSGID": "yes",
            "RestrictNamespaces": "yes",
            "LockPersonality": "yes",
            "MemoryDenyWriteExecute": "yes",
            "CapabilityBoundingSet": "",
            "AmbientCapabilities": "",
            "RestrictAddressFamilies": "AF_UNIX",
        }


def compare_systemd_properties(profile: LinuxBrokerProfile, observed: dict[str, str]) -> dict:
    reasons = list(profile.validate())
    required = profile.systemd_hardening_requirements()
    for key, expected in required.items():
        actual = str(observed.get(key, "")).strip()
        if actual.lower() != str(expected).lower():
            reasons.append(f"systemd_property_mismatch:{key}")
    return {
        "ok": not reasons,
        "status": "LINUX_BROKER_PROFILE_VERIFIED" if not reasons else "LINUX_BROKER_PROFILE_NOT_VERIFIED",
        "reasons": reasons,
        "authority_granted": False,
        "required_properties": required,
    }

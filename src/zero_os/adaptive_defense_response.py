from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DefenseResponse:
    level: str
    allow_operation: bool
    preserve_evidence: bool
    snapshot_before_action: bool
    reduce_capabilities: bool
    quarantine: bool
    destructive_action: bool
    reason: str


def choose_defense_response(*, disposition: str, reversible: bool, blast_radius: str) -> DefenseResponse:
    disposition = str(disposition or "deny").lower()
    blast = str(blast_radius or "local").lower()
    if disposition == "allow":
        return DefenseResponse("normal", True, False, False, False, False, False, "authority_survived")
    if disposition == "monitor":
        return DefenseResponse("monitor", True, True, False, False, False, False, "minor_anomaly")
    if disposition == "restrict":
        return DefenseResponse("restrict", False, True, bool(reversible), True, False, False, "meaningful_contradiction")
    if disposition == "quarantine":
        return DefenseResponse("quarantine", False, True, bool(reversible), True, True, False, "strong_compromise_evidence")
    destructive = blast in {"critical", "system"} and not reversible
    return DefenseResponse("deny", False, True, bool(reversible), True, False, destructive, "authority_missing_or_revoked")

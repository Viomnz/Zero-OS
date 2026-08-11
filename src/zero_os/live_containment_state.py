from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProcessContainmentState:
    process_identity: str
    authority_state: str = "ACTIVE"
    protected_data_export_allowed: bool = True
    protected_key_release_allowed: bool = True
    monitoring_level: int = 0
    investigation_required: bool = False
    quarantine_eligible: bool = False
    contradictions: list[str] = field(default_factory=list)

    def apply_decoy_contradiction(self, reason: str) -> None:
        self.authority_state = "CONTESTED"
        self.protected_data_export_allowed = False
        self.protected_key_release_allowed = False
        self.monitoring_level = max(self.monitoring_level, 2)
        self.investigation_required = True
        self.quarantine_eligible = True
        if reason not in self.contradictions:
            self.contradictions.append(reason)

    def clear_after_independent_investigation(self, *, cleared: bool, evidence_ref: str) -> tuple[bool, str]:
        if not cleared:
            return False, "containment_not_cleared"
        if not evidence_ref:
            return False, "independent_clearance_evidence_missing"
        self.authority_state = "RESTRICTED"
        self.monitoring_level = max(self.monitoring_level, 1)
        self.investigation_required = False
        self.quarantine_eligible = False
        return True, "containment_reduced_but_authority_not_fully_restored"


@dataclass
class LiveContainmentRegistry:
    processes: dict[str, ProcessContainmentState] = field(default_factory=dict)

    def get(self, process_identity: str) -> ProcessContainmentState:
        if process_identity not in self.processes:
            self.processes[process_identity] = ProcessContainmentState(process_identity=process_identity)
        return self.processes[process_identity]

    def contest(self, process_identity: str, reason: str) -> ProcessContainmentState:
        state = self.get(process_identity)
        state.apply_decoy_contradiction(reason)
        return state


def containment_invariants() -> dict:
    return {
        "decoy_touch_cannot_expand_authority": True,
        "export_revocation_is_immediate": True,
        "key_release_revocation_is_immediate": True,
        "clearance_requires_independent_evidence": True,
        "clearance_does_not_restore_full_authority": True,
    }

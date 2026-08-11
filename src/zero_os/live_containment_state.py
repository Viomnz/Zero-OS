from __future__ import annotations

from dataclasses import dataclass, field

from zero_os.process_identity_evidence import KernelProcessIdentityEvidence, verify_kernel_process_identity


@dataclass
class ProcessContainmentState:
    process_identity: str
    authority_state: str = "UNVERIFIED"
    protected_data_export_allowed: bool = False
    protected_key_release_allowed: bool = False
    monitoring_level: int = 0
    investigation_required: bool = True
    quarantine_eligible: bool = False
    contradictions: list[str] = field(default_factory=list)
    revision: int = 1
    identity_verified: bool = False
    identity_provenance: tuple[str, ...] = field(default_factory=tuple)

    def _advance(self) -> None:
        self.revision = max(1, int(self.revision)) + 1

    def apply_decoy_contradiction(self, reason: str) -> None:
        self.authority_state = "CONTESTED"
        self.protected_data_export_allowed = False
        self.protected_key_release_allowed = False
        self.monitoring_level = max(self.monitoring_level, 2)
        self.investigation_required = True
        self.quarantine_eligible = True
        if reason not in self.contradictions:
            self.contradictions.append(reason)
        self._advance()

    def clear_after_independent_investigation(self, *, cleared: bool, evidence_ref: str) -> tuple[bool, str]:
        if not cleared:
            return False, "containment_not_cleared"
        if not evidence_ref:
            return False, "independent_clearance_evidence_missing"
        self.authority_state = "RESTRICTED"
        self.monitoring_level = max(self.monitoring_level, 1)
        self.investigation_required = False
        self.quarantine_eligible = False
        # Sensitive export and key release deliberately remain revoked. A separate
        # authority process must re-earn them after clearance.
        self.protected_data_export_allowed = False
        self.protected_key_release_allowed = False
        self._advance()
        return True, "containment_reduced_but_sensitive_authority_not_restored"


@dataclass
class LiveContainmentRegistry:
    processes: dict[str, ProcessContainmentState] = field(default_factory=dict)

    def get(self, process_identity: str) -> ProcessContainmentState:
        """Return state without treating a caller-supplied identity as trusted.

        Unknown identities are materialized only as fail-closed UNVERIFIED state.
        """
        identity = str(process_identity or "").strip()
        if identity not in self.processes:
            self.processes[identity] = ProcessContainmentState(process_identity=identity)
        return self.processes[identity]

    def register(self, process_identity: str) -> ProcessContainmentState:
        """Legacy registration path. Plain strings never establish clean identity."""
        return self.get(str(process_identity))

    def register_kernel_evidence(self, evidence: KernelProcessIdentityEvidence) -> ProcessContainmentState:
        verification = verify_kernel_process_identity(evidence)
        if not verification.accepted:
            raise PermissionError(";".join(verification.reasons) or verification.status)

        identity = verification.process_identity
        state = self.processes.get(identity)
        if state is None:
            state = ProcessContainmentState(
                process_identity=identity,
                authority_state="ACTIVE",
                protected_data_export_allowed=True,
                protected_key_release_allowed=True,
                investigation_required=False,
                identity_verified=True,
                identity_provenance=verification.provenance,
            )
            self.processes[identity] = state
            return state

        identity_changed = (not state.identity_verified) or state.identity_provenance != verification.provenance
        state.identity_verified = True
        state.identity_provenance = verification.provenance
        # Identity verification may establish that an otherwise untouched UNVERIFIED
        # record refers to a real process. It must never clear a contradiction,
        # restriction, quarantine, or revocation.
        if state.authority_state == "UNVERIFIED" and not state.contradictions:
            state.authority_state = "ACTIVE"
            state.protected_data_export_allowed = True
            state.protected_key_release_allowed = True
            state.investigation_required = False
            identity_changed = True
        if identity_changed:
            state._advance()
        return state

    def current(self, process_identity: str) -> ProcessContainmentState | None:
        return self.processes.get(str(process_identity))

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
        "containment_revision_advances_on_state_change": True,
        "sensitive_authority_must_be_reearned_after_clearance": True,
        "plain_string_registration_fails_closed": True,
        "process_identity_requires_kernel_bound_evidence": True,
        "identity_verification_cannot_clear_contradictions": True,
    }

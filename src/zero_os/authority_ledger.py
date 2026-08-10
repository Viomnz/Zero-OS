from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterable


UNTESTED = "UNTESTED"
PROVISIONAL = "PROVISIONAL"
SURVIVED_IN_SCOPE = "SURVIVED_IN_SCOPE"
RESTRICTED = "RESTRICTED"
CONTESTED = "CONTESTED"
SUPERSEDED = "SUPERSEDED"
REVOKED = "REVOKED"
HISTORICAL = "HISTORICAL"


@dataclass(frozen=True)
class AuthorityRecord:
    authority_id: str
    subject_id: str
    claim_type: str
    value_fingerprint: str
    state_revision: str
    demonstrated_scope: frozenset[str] = field(default_factory=frozenset)
    state: str = UNTESTED
    dependencies: frozenset[str] = field(default_factory=frozenset)
    pressure_history: tuple[str, ...] = field(default_factory=tuple)
    contradiction_history: tuple[str, ...] = field(default_factory=tuple)
    last_stronger_survival: str = ""
    fallback: str = "deny"
    next_required_pressure: tuple[str, ...] = field(default_factory=tuple)
    expires_at_utc: str = ""
    revocation_conditions: tuple[str, ...] = field(default_factory=tuple)

    def active(self, now_utc: datetime | None = None) -> bool:
        if self.state not in {PROVISIONAL, SURVIVED_IN_SCOPE}:
            return False
        if not self.expires_at_utc:
            return True
        now = now_utc or datetime.now(timezone.utc)
        try:
            expiry = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))
        except ValueError:
            return False
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now <= expiry.astimezone(timezone.utc)


@dataclass
class AuthorityLedger:
    records: dict[str, AuthorityRecord] = field(default_factory=dict)

    def put(self, record: AuthorityRecord) -> None:
        self.records[record.authority_id] = record

    def get(self, authority_id: str) -> AuthorityRecord | None:
        return self.records.get(str(authority_id))

    def authorize(self, authority_id: str, scope: str, *, now_utc: datetime | None = None) -> bool:
        record = self.get(authority_id)
        if record is None or not record.active(now_utc):
            return False
        if str(scope) not in record.demonstrated_scope:
            return False
        return all(
            dependency in self.records and self.records[dependency].active(now_utc)
            for dependency in record.dependencies
        )

    def pressure_event(
        self,
        authority_id: str,
        *,
        pressure_id: str,
        outcome: str,
        independent: bool,
        inside_demonstrated_scope: bool,
        stronger_than_previous: bool = False,
        new_scope: Iterable[str] = (),
    ) -> AuthorityRecord:
        current = self.records[authority_id]
        history = current.pressure_history + (str(pressure_id),)
        contradictions = current.contradiction_history
        scope = set(current.demonstrated_scope)
        state = current.state
        last = current.last_stronger_survival

        if outcome == "pass":
            if stronger_than_previous and independent:
                scope.update(str(item) for item in new_scope if str(item))
                state = SURVIVED_IN_SCOPE
                last = str(pressure_id)
            elif state == UNTESTED:
                state = PROVISIONAL
        elif not inside_demonstrated_scope:
            state = RESTRICTED
            contradictions = contradictions + (f"outside_scope:{pressure_id}",)
        elif not independent:
            state = CONTESTED
            contradictions = contradictions + (f"correlated_failure:{pressure_id}",)
        else:
            state = REVOKED
            contradictions = contradictions + (f"independent_in_scope_failure:{pressure_id}",)

        updated = replace(
            current,
            state=state,
            demonstrated_scope=frozenset(scope),
            pressure_history=history,
            contradiction_history=contradictions,
            last_stronger_survival=last,
        )
        self.records[authority_id] = updated
        if state in {REVOKED, CONTESTED, SUPERSEDED}:
            self._propagate_dependency_loss(authority_id, state)
        return updated

    def supersede(self, incumbent_id: str, challenger_id: str) -> None:
        incumbent = self.records[incumbent_id]
        challenger = self.records[challenger_id]
        self.records[incumbent_id] = replace(incumbent, state=SUPERSEDED)
        if challenger.state not in {PROVISIONAL, SURVIVED_IN_SCOPE}:
            self.records[challenger_id] = replace(challenger, state=PROVISIONAL)
        self._propagate_dependency_loss(incumbent_id, SUPERSEDED)

    def revoke_for_condition(self, active_conditions: Iterable[str]) -> list[str]:
        active = {str(item) for item in active_conditions if str(item)}
        revoked: list[str] = []
        for authority_id, record in list(self.records.items()):
            hit = active.intersection(record.revocation_conditions)
            if hit and record.state not in {REVOKED, HISTORICAL}:
                self.records[authority_id] = replace(
                    record,
                    state=REVOKED,
                    contradiction_history=record.contradiction_history + tuple(f"revocation:{item}" for item in sorted(hit)),
                )
                revoked.append(authority_id)
        for authority_id in revoked:
            self._propagate_dependency_loss(authority_id, REVOKED)
        return revoked

    def _propagate_dependency_loss(self, dependency_id: str, cause: str) -> None:
        for authority_id, record in list(self.records.items()):
            if dependency_id not in record.dependencies:
                continue
            if record.state in {REVOKED, HISTORICAL, SUPERSEDED}:
                continue
            self.records[authority_id] = replace(
                record,
                state=CONTESTED,
                contradiction_history=record.contradiction_history + (f"dependency:{dependency_id}:{cause}",),
            )
            self._propagate_dependency_loss(authority_id, CONTESTED)

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True)
class ObjectiveAuthority:
    objective_id: str
    statement: str
    provenance: tuple[str, ...]
    demonstrated_scope: frozenset[str] = field(default_factory=frozenset)
    dependencies: frozenset[str] = field(default_factory=frozenset)
    revocation_conditions: tuple[str, ...] = field(default_factory=tuple)
    contradiction_history: tuple[str, ...] = field(default_factory=tuple)
    status: str = "PROVISIONAL"
    expires_at_utc: str = ""

    def active(self, now_utc: datetime | None = None) -> bool:
        if self.status not in {"PROVISIONAL", "SURVIVED_IN_SCOPE"}:
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


class ObjectiveAuthorityLedger:
    def __init__(self) -> None:
        self.records: dict[str, ObjectiveAuthority] = {}

    def put(self, objective: ObjectiveAuthority) -> None:
        self.records[objective.objective_id] = objective

    def authorize(self, objective_id: str, scope: str, active_dependencies: Iterable[str]) -> bool:
        objective = self.records.get(str(objective_id))
        if objective is None or not objective.active():
            return False
        if str(scope) not in objective.demonstrated_scope:
            return False
        active = {str(x) for x in active_dependencies}
        return objective.dependencies.issubset(active)

    def contest(self, objective_id: str, contradiction: str) -> ObjectiveAuthority:
        current = self.records[objective_id]
        updated = replace(
            current,
            status="CONTESTED",
            contradiction_history=current.contradiction_history + (str(contradiction),),
        )
        self.records[objective_id] = updated
        return updated

    def revoke_for_conditions(self, conditions: Iterable[str]) -> list[str]:
        active = {str(x) for x in conditions}
        revoked: list[str] = []
        for key, current in list(self.records.items()):
            hits = active.intersection(current.revocation_conditions)
            if hits and current.status != "REVOKED":
                self.records[key] = replace(
                    current,
                    status="REVOKED",
                    contradiction_history=current.contradiction_history + tuple(f"revocation:{x}" for x in sorted(hits)),
                )
                revoked.append(key)
        return revoked

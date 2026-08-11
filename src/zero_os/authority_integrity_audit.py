from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

from zero_os.authority_ledger import (
    AuthorityLedger,
    PROVISIONAL,
    SURVIVED_IN_SCOPE,
    REVOKED,
    SUPERSEDED,
    HISTORICAL,
)


@dataclass(frozen=True)
class AuthorityIntegrityFinding:
    authority_id: str
    failure: str
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def _dependency_cycles(ledger: AuthorityLedger) -> list[tuple[str, ...]]:
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, stack: list[str], seen: set[str]) -> None:
        if node in stack:
            start = stack.index(node)
            cycle = tuple(stack[start:] + [node])
            rotations = [cycle[i:-1] + cycle[:i] + (cycle[i],) for i in range(len(cycle) - 1)]
            cycles.add(min(rotations))
            return
        if node in seen:
            return
        seen.add(node)
        record = ledger.get(node)
        if record is None:
            return
        for dependency in record.dependencies:
            visit(dependency, stack + [node], seen.copy())

    for authority_id in ledger.records:
        visit(authority_id, [], set())
    return sorted(cycles)


def audit_authority_integrity(ledger: AuthorityLedger) -> dict:
    findings: list[AuthorityIntegrityFinding] = []
    active_states = {PROVISIONAL, SURVIVED_IN_SCOPE}

    for authority_id, record in ledger.records.items():
        if not authority_id.strip():
            findings.append(AuthorityIntegrityFinding(authority_id, "missing_authority_id", "authority id is blank"))
        if not record.subject_id.strip():
            findings.append(AuthorityIntegrityFinding(authority_id, "missing_subject", "active claim cannot be bound to a subject"))
        if not record.claim_type.strip():
            findings.append(AuthorityIntegrityFinding(authority_id, "missing_claim_type", "claim type is blank"))
        if not record.value_fingerprint.strip():
            findings.append(AuthorityIntegrityFinding(authority_id, "missing_value_fingerprint", "claim value is not exact-bound"))
        if not record.state_revision.strip():
            findings.append(AuthorityIntegrityFinding(authority_id, "missing_state_revision", "authority is not bound to a state revision"))
        if record.state in active_states and not record.demonstrated_scope:
            findings.append(AuthorityIntegrityFinding(authority_id, "active_scope_empty", "active authority has no demonstrated scope"))
        for dependency in record.dependencies:
            if dependency not in ledger.records:
                findings.append(AuthorityIntegrityFinding(authority_id, "missing_dependency", dependency))
            else:
                dependency_state = ledger.records[dependency].state
                if record.state in active_states and dependency_state in {REVOKED, SUPERSEDED, HISTORICAL}:
                    findings.append(
                        AuthorityIntegrityFinding(
                            authority_id,
                            "active_depends_on_inactive_authority",
                            f"{dependency}:{dependency_state}",
                        )
                    )

    for cycle in _dependency_cycles(ledger):
        detail = " -> ".join(cycle)
        for authority_id in set(cycle[:-1]):
            findings.append(AuthorityIntegrityFinding(authority_id, "authority_dependency_cycle", detail))

    return {
        "status": "PASS" if not findings else "BLOCK_AUTHORITY",
        "authority_records": len(ledger.records),
        "finding_count": len(findings),
        "findings": [item.to_dict() for item in findings],
        "authority_integrity_permitted": not findings,
        "rule": "authority dependencies must themselves retain valid scoped authority and may not form self-supporting cycles",
    }

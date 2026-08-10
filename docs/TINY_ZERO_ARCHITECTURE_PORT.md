# Tiny Zero Architecture Port into Zero-OS

This port adapts surviving Pure Logic mechanisms from the newer Tiny Zero research line into Zero-OS without merging the two projects.

## Source architecture retained

The port keeps these Tiny Zero invariants:

1. Discovery selects a nominee; discovery strength never certifies scope.
2. Authority belongs to individual claims/mechanisms, not whole versions.
3. Authority has explicit states: UNTESTED, PROVISIONAL, SURVIVED_IN_SCOPE, RESTRICTED, CONTESTED, SUPERSEDED, REVOKED, HISTORICAL.
4. In-scope independent failure revokes authority and reopens dependent authority.
5. Correlated/weak failure contests authority rather than being ignored or treated as fully independent.
6. Repeating old or weak tests cannot expand demonstrated scope.
7. Stronger independent pressure may expand scope only when the new scope itself survives.
8. Contested authority triggers additional independent pressure instead of weaker standards.
9. A challenger can supersede an incumbent verifier or mechanism.
10. The final action boundary must validate exact subject, exact claim value, exact state revision, exact scope, fresh authority, independent evidence, dependencies, and revocation state.

## Zero-OS adaptations

### Authority Ledger

`authority_ledger.py` stores authority per claim/mechanism and propagates dependency loss selectively. One failed verifier does not globally collapse unrelated authority.

### Evidence Binding

`evidence_binding.py` binds evidence to:

- subject identity;
- claim type;
- canonical value fingerprint;
- state revision;
- demonstrated scope.

Evidence independence is not accepted from caller labels alone. Shared source lineage or shared method families collapse into the same independence group.

### Final Action Authority

`final_action_authority.py` contains a last-step authorization function for mutating actions. Discovery confidence is deliberately absent from its API.

A mutating action is denied when:

- the authority record is missing or inactive;
- exact-claim evidence is missing;
- evidence does not have enough independent groups;
- contradictory exact-claim evidence exists;
- the claim value changed;
- the state revision changed;
- scope was not demonstrated;
- an authority dependency is inactive;
- expiration or a revocation condition invalidated authority.

### Active Scope Pressure

`active_scope_pressure.py` selects the next test for contested scope using contradiction yield, evidence independence, ambiguity reduction, consequence, scope-expansion value, and resource cost. Discovery-fit is intentionally ignored.

## Repairs included

- Claim expiration is now enforced by `authority_required()`.
- `claim_from_dict()` is restored so the invariant investigator can import correctly.
- Unknown action kinds are denied by default rather than inheriting `safe_auto`.

## Still not complete

The final action authority module exists, but every legacy mutation path has not yet been mechanically rewired through it. That is the next migration boundary. The architecture must not claim executor-wide enforcement until the actual runtime executor is routed through this gate and executable tests confirm the path.

# Zero-OS Pure Logic Enforcement Epoch v3

## Objective

Move Pure Logic from architecture modules into enforceable entrypoint-to-sink behavior across the whole repository.

This epoch does not treat `src/zero_os` as the security boundary. Zero-OS also contains Python in `ai_from_scratch`, `tools`, setup/build scripts, platform adapters, native integration helpers, and other locations. Sensitive operations in those paths count against promotion.

## Major architecture change

Epoch v2 introduced a capability model. Epoch v3 introduces capability leases and sink-side checks.

The intended chain is:

```text
identity / provenance
  -> dynamic trust
  -> requested capability
  -> Pure Logic capability decision
  -> short-lived scoped capability lease
  -> legacy operation
  -> sink-side scope check
  -> external effect
```

A high-level permission check is not enough. A low-level network, credential, or filesystem primitive must also see the required live scope.

## Capability leases

`capability_lease.py` provides process-context-local, short-lived leases. A lease contains only the scopes granted for the current operation and cannot expand itself.

A lease for `network:fetch` does not imply `credential:read`, `filesystem:write`, or any other capability.

## Sink enforcement

`secure_primitives.py` adds checked network, credential, filesystem-read, and filesystem-write primitives. `net_client.py`, a shared Zero-OS network path, is migrated to the checked network primitive and now fails closed without a matching capability lease.

This is deliberate defense in depth. A planner or caller cannot safely rely on a single upstream boolean if a deeper helper can still reach the external sink directly.

## Whole-repository audit

`whole_repo_capability_audit.py` scans every Python file outside excluded dependency/build directories. It identifies static candidates for:

- network access;
- process execution;
- filesystem mutation;
- credential/secret reads.

It records the containing function and whether an identified Pure Logic mediator appears in that function.

This auditor is intentionally conservative and incomplete. It is a static Python AST pressure tool, not a proof of total runtime coverage.

## Promotion rule

`enforcement_promotion_gate.py` combines the v2 native-cyber gate with the whole-repository sink audit.

Promotion is blocked when any identified sensitive sink is unmediated or identified coverage is below 100%.

Thirty clean files cannot compensate for one direct credential or network bypass.

Even perfect identified static coverage produces at most:

`PROVISIONAL_ENFORCED_STATIC_SCOPE`

It does not certify dynamic dispatch, native code, dependencies, firmware, hardware, runtime verifier independence, or unmodeled behavior.

## Remediation queue

`enforcement_remediation_queue.py` converts audit findings into a machine-readable migration queue. Priority is:

1. credential reads;
2. network access;
3. process execution;
4. filesystem mutation.

The preferred repair strategy is shared-primitive or shared-entrypoint migration. Per-file exceptions should be avoided because they recreate the patch-by-patch architecture this epoch is meant to replace.

## Known unresolved class

Direct process execution remains a major repository-wide migration class. The connector safety layer rejected a generic process-execution wrapper during this change, so v3 records direct process sinks as blockers rather than hiding them behind an unreviewed generic execution primitive.

This is a failure record, not a success claim.

## Promotion invariant

No identified sensitive operation may reach a real sink merely because identity, confidence, planner score, installation trust, historical behavior, or a previous permission check looked acceptable.

Authority must still be current at the point where the system touches reality.

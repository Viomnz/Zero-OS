# Zero-OS Native Adaptive Cyber Defense Epoch

## Objective

Move Zero-OS from mutation-only Pure Logic enforcement toward an operating-system-style capability architecture where security is part of ordinary execution.

The central rule is:

> A valid identity or successful authentication does not imply current operational authority.

Authority remains provisional, scoped, evidence-dependent, and revocable.

## Architecture

```text
identity / provenance
        ↓
trust node
        ↓
requested capability
        ↓
canonical capability registry
        ↓
demonstrated scope ∩ current grants
        ↓
contradictions / anomaly / evidence freshness / tenant boundary
        ↓
dynamic capability authority
        ↓
allow / monitor / restrict / quarantine / deny
        ↓
operation
        ↓
runtime observation
        ↓
security immune loop
        ↓
trust reduction / failure preservation / root-cause investigation / stronger retest
```

Mutations remain governed by the existing final-action authority and single-use execution-ticket kernel. The new capability layer does not consume mutation tickets early.

## What changed

### Canonical capability registry

The registry covers both mutations and non-mutating but security-relevant access, including:

- local observation and status;
- browser inspection;
- network fetch and verification;
- API reads/workflows;
- GitHub reads;
- credential reads;
- filesystem reads;
- cross-tenant reads;
- tool invocation;
- IPC;
- device access;
- all previously registered mutation classes.

Unknown capabilities fail closed.

### Dynamic trust graph

A principal no longer has a permanent trusted/untrusted bit. Trust nodes carry demonstrated scopes and runtime state:

- NORMAL
- MONITORED
- RESTRICTED
- QUARANTINED
- REVOKED

Contradictions and anomalies can reduce effective capability immediately. Scope can expand only after stronger pressure is explicitly recorded.

### Dynamic capability authority

For sensitive operations, authority depends on:

- identity verification;
- current demonstrated scope;
- fresh evidence;
- tenant boundary consistency;
- contradiction severity;
- anomaly level;
- trust-node state.

A valid identity with the wrong scope is denied. A high-severity contradiction can restrict or quarantine an otherwise valid principal.

### Adaptive defense hierarchy

Responses are ordered to preserve information and reversibility when possible:

1. allow;
2. monitor;
3. restrict;
4. quarantine;
5. deny.

The architecture preserves evidence and prefers snapshot/restriction before destructive response when the situation allows it.

### Security immune loop

A meaningful contradiction now maps to an explicit defensive-learning sequence:

```text
contradiction
→ reduce trust/capability
→ preserve evidence
→ investigate root cause
→ search same pattern elsewhere
→ require stronger retest
```

This is the Investigation and Survival Laws applied to cyber defense rather than a signature-only response.

### Pre-production least-capability compiler

Unnecessary removable capabilities are stripped before deployment. An unnecessary capability that cannot be removed becomes a safe deployment denial rather than being silently accepted.

This separates:

- can the architecture be made least-capability under allowed transformations?
- should it receive deployment authority?

### Repository-wide capability audit

The static auditor searches for identified sensitive sinks such as:

- filesystem mutation;
- process execution;
- network reads/writes;
- credential access;
- tool invocation;
- tenant access;
- deployment/install/repair/upgrade primitives.

A function containing such a sink must include an authority guard. Identified unmediated sinks block promotion.

### Native cyber promotion gate

Promotion requires both:

- 100% identified mutation mediation; and
- 100% identified sensitive-capability mediation.

One bypass cannot be averaged away by many safe files.

Even perfect static coverage can only produce `PROVISIONAL_NATIVE_CYBER_STATIC_SCOPE`.

## What this does not prove

This epoch does not establish that Zero-OS is secure or unhackable. The static audit does not certify:

- dynamic dispatch;
- generated code;
- native extensions;
- third-party dependency behavior;
- concurrency interleavings;
- firmware or hardware;
- side channels;
- supply-chain compromise;
- real-world independence of identity/verifier evidence.

Those remain explicit unresolved scope.

## Next pressure campaign

The next campaign should run the full repository through this capability audit, migrate every identified direct sensitive sink behind the gateway, then attack the resulting architecture with fresh cases covering credential theft, context poisoning, identity spoofing, cross-tenant access, verifier compromise, runtime drift, rollback failure, dependency poisoning, and compromised telemetry.

No new Master Law is required for those attack families. They are pressure against the six laws and their technical mechanisms.

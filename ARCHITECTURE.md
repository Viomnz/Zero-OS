# Zero OS Architecture

## Goal
Zero OS is a local-first operating/runtime architecture in which reality outranks every internal representation. The governing core is runtime-protected but revision-capable: ordinary agents cannot rewrite it, while stronger independently verified replacements may be promoted through the Protected Correction Plane.

## Six Master Laws
1. Reality — nothing internal is reality; every claim, model, objective, verifier, memory, architecture and law remains challengeable.
2. Survival — authority remains only while it survives stronger pressure within demonstrated scope.
3. Investigation — meaningful contradictions trigger causal investigation, repair, preserved failure history and stronger retest.
4. Plurality — viable hypotheses and methods remain represented until evidence separates, restricts, merges or leaves them unresolved.
5. Path — among surviving paths, prefer the currently justified objective with the least unnecessary irreversible damage.
6. Resource — verification and action budgets scale with consequence, urgency, reversibility and information gain.

The laws are foundational but provisional. They do not receive exemption from Reality Law.

## Constitutional Runtime Flow
1. Observation and provenance collection
2. Reality Ledger update
3. Discovery Plane generates/ranks candidate interpretations
4. Plurality Store preserves viable alternatives
5. Independent Scope Plane tries to falsify representational scope
6. Contested scope triggers Active Evidence Investigation
7. Identity/Trust Authority evaluates the acting principal
8. Objective Authority Ledger evaluates whether the objective itself retains authority
9. Capability/Authority Ledger verifies exact requested scope, dependencies, expiry and revocation
10. Legal-State Invariant Engine checks forbidden states
11. Resource Law allocates verification depth
12. Reversible Executor performs only bounded authorized operations
13. Independent Outcome Verifier checks actual result using evidence not controlled by the acting subsystem
14. Contradictions/revocations propagate through authority dependencies
15. Architecture Promotion Authority may promote stronger replacements only through the Protected Correction Plane

## Discovery Is Not Authority
Discovery can identify the strongest current explanation. It cannot certify that its representation is complete.

`best candidate -> scope pressure -> demonstrated scope -> provisional authority`

Discovery confidence, consensus, memory frequency and verifier self-reporting cannot override failed or contested scope certification.

Consensus may help select an action under uncertainty. It is not an epistemic truth certificate.

## Protected Correction Plane
The governing core, authority kernel, capability kernel, correction plane and release-promotion policy are protected from ordinary runtime modification.

They are not epistemically immutable.

A candidate replacement must provide provenance, executable/formal invariant checks, adversarial pressure evidence, independent evaluation, compatibility analysis, canary deployment and a rollback path. The proposer cannot be the sole evaluator.

Principle: **Protected from arbitrary modification, never protected from justified correction.**

## Identity and Capability
Zero OS does not use a single global `authentication_required` switch as its authority model.

Low-consequence local reads may require minimal identity evidence. Privileged actions require progressively stronger identity provenance, demonstrated scope, trust state, fresh evidence, expiry/revocation checks and exact capability authority.

A valid credential does not grant unlimited authority.

## Native Adaptive Cyber Defense
Security is part of ordinary execution authority. Runtime contradictions can reduce capability, restrict network/credential/tenant access, quarantine principals and trigger investigation before a known malware signature exists.

The defensive hierarchy prefers monitoring, restriction, sandboxing, snapshotting, quarantine and rollback before unnecessary destruction when evidence and consequences permit.

## Reality and Authority Ledgers
Important decisions carry provenance, assumptions, dependencies, requested scope, demonstrated scope, contradiction state, expiry and revocation semantics.

Memory may guide search or priors. Memory is not independent evidence by itself.

Objectives have their own authority ledger and may be contested or revoked independently of execution competence.

## Independent Outcome Verification
The subsystem performing a consequential action may report telemetry, but it may not be the sole authority declaring success. High/critical consequence actions require independent outcome evidence according to Resource Law budget.

## Legal-State Invariants
Critical components define forbidden states explicitly. Promotion is blocked when critical invariants fail or cannot be evaluated. Passing known tests establishes only the demonstrated model scope; it does not prove all illegal states are unreachable in reality.

## Highway Lanes
- `agent` for planning and multi-step execution
- `system` for operations and control commands
- `code` for workspace code actions
- `web` for internet tasks
- `api` and `browser` utility lanes
- `memory` for persistent memory
- `plugins/*` for extensions

All consequential lanes must ultimately converge on the same authority and capability boundaries.

## Core Data Paths
- Source: `src/`, `ai_from_scratch/`
- Runtime: `.zero_os/runtime/`
- Production state: `.zero_os/production/`
- Trust keys: `.zero_os/keys/`
- Backups and quarantine: `.zero_os/backup/`, `.zero_os/quarantine/`

## Stability Meaning
Stable interfaces and versioned contracts are allowed and desirable. Stability does not mean truth is frozen.

Zero OS may freeze a compatibility surface for a release while retaining an isolated, independently verified correction path for defects in the architecture itself.

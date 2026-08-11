# Zero-OS Pure Logic Authority Kernel v5

## Purpose

This epoch replaces the old constitutional assumptions `immutable_core=True`, `authentication_required=False`, and consensus-led epistemic control with a single Pure Logic authority model.

The core is now **runtime-protected and revision-capable**.

Protection prevents arbitrary runtime modification. Revision capability preserves Reality Law: a stronger architecture may replace the current one only through isolated correction, independent evaluation, pressure testing, canary deployment and rollback.

## Constitutional stack

1. Reality Ledger
2. Discovery Plane
3. Plurality preservation
4. Independent Scope Plane
5. Active Evidence Investigator
6. Identity/Trust Authority
7. Objective Authority Ledger
8. Claim/Capability Authority Ledger
9. Legal-State Invariant Engine
10. Resource Law Budget
11. Reversible Executor
12. Independent Outcome Verifier
13. Protected Correction Plane
14. Architecture Promotion Authority

## Authority law

No single internal score grants consequential authority.

The following are explicitly insufficient by themselves:

- discovery score;
- consensus;
- memory frequency;
- planner confidence;
- verifier self-report;
- authentication success;
- successful completion reported by the actor itself;
- previous production status.

Consequential authority requires exact scoped claims whose dependencies, objective authority, identity evidence, expiry, revocation state, contradictions and legal-state requirements survive together.

## Discovery and scope

Discovery selects the strongest current explanation. Scope certification is a separate process that attempts to falsify the explanation language.

A discovery winner with no independent scope pressure remains contested even with a score of 1.0.

When scope is contested, the Active Evidence Investigator asks for discriminating evidence from method families and lineages not already dominating the evidence base. The standard is not weakened merely because evidence is inconvenient to obtain.

## Identity

Zero-OS no longer treats authentication as a global true/false project policy.

Identity authority is capability- and consequence-sensitive.

A low-risk local operation may require minimal identity evidence. High and critical actions require strong identity evidence plus demonstrated action scope. A valid identity does not imply unrestricted capability.

## Objectives

Execution competence does not certify that an objective deserves authority.

Objectives have independent provenance, scope, expiry, dependency, contradiction and revocation semantics. A technically executable action is denied when the objective itself lacks authority.

## Protected Correction Plane

Protected targets include the core policy, authority kernel, authority ledger, capability kernel, correction plane and release-promotion policy.

Normal runtime writers receive no authority to rewrite these targets.

Architecture revision requires:

- provenance;
- executable/formal invariant evidence;
- adversarial pressure;
- independent evaluators distinct from the proposer;
- compatibility analysis;
- canary reference;
- rollback reference.

This is not proof of correctness. It is the minimum contract for allowing a candidate into isolated canary evaluation.

## Resource Law

Verification depth scales with consequence and irreversibility. Critical actions require stronger independent evidence, reversible paths where possible, legal-state checks and independent outcome verification.

Urgency can alter investigation strategy but does not erase critical verification requirements.

## Independent outcome verification

The acting subsystem cannot be the sole verifier of its own success. For high/critical consequence actions, separate evidence sources must verify the resulting state. Correlated lineage is tracked rather than treating differently named outputs as automatically independent.

## Architecture promotion

Promotion is veto-based for critical failures.

One identified authority bypass, one identified capability bypass, failed critical invariant, missing independent outcome evidence, or a correction-plane violation blocks promotion. Clean modules cannot average away a critical bypass.

Even successful promotion is stated only as `PROVISIONAL_PROMOTION_IN_DEMONSTRATED_SCOPE` with unresolved scope preserved explicitly.

## Current limitation

This epoch establishes constitutional mechanisms and replaces the old core semantics, but it does not prove every legacy execution path is already mediated by this kernel. The previous whole-repository capability and transport audits remain required inputs to promotion.

Formal verification is also not yet complete. `legal_state_invariants.py` provides an invariant enforcement interface, not a proof that all illegal states are unreachable. Actual model checking/proof tooling remains a P1 integration target.

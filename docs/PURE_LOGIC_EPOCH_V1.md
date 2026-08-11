# Zero-OS Pure Logic Architecture Epoch v1

## Objective

Replace local confidence/readiness/trust gates with one repository-wide rule:

> No identified state-changing path deserves execution authority unless fresh authority is bound to the exact subject, claim value, state revision, action scope, dependencies, and independent evidence that survived contradiction pressure.

This epoch is an architectural migration, not a claim that Zero-OS is secure or fully Pure-Logic-complete.

## Six Master Laws

1. **Reality** — no internal observation, model, score, memory, verifier, objective, architecture, or law is reality.
2. **Survival** — authority is provisional and survives only within demonstrated scope under stronger recursive pressure.
3. **Investigation** — meaningful contradiction triggers causal investigation, repair, preserved failure history, and stronger retest.
4. **Plurality** — viable alternatives remain alive until evidence separates, restricts, merges, or leaves them unresolved.
5. **Path** — among surviving paths, pursue the justified objective with the least unnecessary irreversible damage.
6. **Resource** — allocate investigation/action by consequence, urgency, reversibility, information gain, and real cost.

The laws themselves receive no permanent exemption from Reality or Survival.

## Architecture after this epoch

```text
observations / telemetry / user / code / memory
                  |
                  v
          discovery / Zero AI LLM
          proposals only; authority=0
                  |
                  v
             exact Claim
 subject + value + state revision + requested scope
                  |
                  v
       independent evidence binding
 lineage + method family + contradictions
                  |
                  v
           Authority Ledger
 dependencies + scope + pressure + expiry + revocation
                  |
                  v
       authority graph integrity audit
 missing/cyclic/revoked dependencies block authority
                  |
                  v
         final action authority
 discovery confidence is not an input
                  |
                  v
     short-lived single-use ticket
                  |
                  v
       Pure Logic runtime kernel
 canonical mutation registry + exact action scope
                  |
                  v
             mutation sink
                  |
                  v
       post-action reality verification
```

## Large changes in this epoch

### 1. Canonical mutation registry

High-risk action types now have canonical names, required authority scope, risk class, rollback expectation, and external-side-effect status. Unknown mutation kinds fail closed.

### 2. Runtime kernel

The permission layer no longer consumes arbitrary tickets directly. Registered mutations route through `pure_logic_runtime_kernel.authorize_runtime_mutation`, which requires a fresh single-use ticket for the canonical mutation and exact registered scope.

Confidence, planner score, readiness, LLM output, memory weight, and self-reported verifier count do not appear in the kernel authority API.

### 3. Registry-bound final authority

Final authority can no longer mint a mutation ticket for a caller-invented weaker scope. The requested scope must equal the canonical mutation registry scope.

### 4. Authority graph integrity

Before a mutation is authorized, the authority graph is audited for:

- missing subjects;
- missing claim types;
- missing exact value fingerprints;
- missing state revisions;
- active authority with empty demonstrated scope;
- missing dependencies;
- active claims depending on revoked/superseded/historical authority;
- self-supporting dependency cycles.

### 5. Repository mutation coverage audit

An AST-based audit searches Zero-OS Python source for mutation candidates such as filesystem writes/deletes/moves, process execution, outbound POSTs, deploy/install/repair/recovery operations, and known mutation families.

A candidate is classified as mediated only when the containing function invokes an accepted authority boundary.

This is a heuristic static analysis tool, not a complete proof. Dynamic dispatch, native components, generated code, reflection, dependencies, concurrency, and runtime environment remain unresolved scope.

### 6. Promotion gate

Promotion is denied when any identified unmediated mutation candidate remains.

`99.9%` mutation coverage is not rounded into success.

Even `100%` identified static coverage produces only:

> `PROVISIONAL_STATIC_SCOPE`

It is not a global security or correctness claim.

## Core invariants

- discovery authority != scope authority
- proposal != execution authority
- confidence != evidence
- memory != independent evidence
- different labels != independent evidence
- finding authority != analysis-coverage authority
- passing known tests != general attack-family authority
- version promotion != permanent component authority
- repeated weak pressure != stronger survival
- active authority cannot depend on dead authority
- authority cannot certify itself through a dependency cycle
- unknown mutation != safe mutation
- a ticket for one mutation/scope cannot authorize another
- consumed ticket != reusable authority
- stale state revision != current authority
- expired authority != current authority

## Promotion criteria

The epoch is eligible for architecture promotion only after all of these are demonstrated in a fresh audit:

1. identified mutation mediation coverage = 100%;
2. zero identified unmediated privileged mutation sinks;
3. zero malformed or cyclic active authority dependencies;
4. zero confidence/readiness/memory/LLM paths that can grant mutation authority;
5. exact evidence/state binding survives replay and stale-state attacks;
6. dependency revocation propagates before dependent action;
7. security/code/runtime pressure cases survive without per-case authority patches;
8. a fresh audit distinct from the implementation path fails to find a bypass.

## Current boundary

This epoch significantly strengthens the architecture but does **not** certify complete mutation coverage yet. Legacy direct command paths still require repository-wide audit and migration. The audit is intentionally allowed to block promotion until they are mediated or explicitly proven read-only.

That is not an implementation failure. It is the required refusal to promote an architecture whose demonstrated scope is incomplete.

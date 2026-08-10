# Pure Logic Break Audit

This audit intentionally attacks Zero-OS assumptions without mutating production state. The goal is to find places where an internal representation can silently become authority.

## P0 failures

### 1. INTERNAL_METRIC_AUTHORITY

Break case: a subsystem defines a score, reaches the score's threshold, and treats that as proof of readiness.

Observed examples:
- `world_model.py` treats pressure as ready when `overall_score >= 100.0`.
- `zero_ai_evolution.py` computes fitness from internally selected components and targets, then uses the result to judge candidate quality.

Why this breaks Pure Logic: a score only proves that its own scoring function was satisfied. It does not establish that the scoring function covers reality.

Required repair:
- represent every metric with an explicit demonstrated scope;
- separate metric success from authority;
- require independent falsification before promotion;
- never make 100/100 a special truth state.

### 2. MEMORY_AS_EVIDENCE

Break case: previous successful tasks and policy memory reinforce a branch that repeats the same historical mistake.

Observed example:
- `memory_tier_filter.py` converts task memory, playbook memory, and policy memory into `evidence_weight`, `memory_confidence`, and branch support.

Why this breaks Pure Logic: memory is historical internal state. Repetition and past success can improve search priority but cannot independently verify present reality.

Required repair:
- rename memory support to prior/search bias;
- prohibit memory-derived weights from certifying claims or mutation scope;
- attach provenance, age, failure lineage, and contradiction state to every memory item;
- require fresh external or independently generated evidence for authority.

### 3. SELF_EVOLUTION_SELF_JUDGING

Break case: the evolution subsystem proposes a change, evaluates it with its own fitness function, and promotes when its own criteria improve.

Observed example:
- `zero_ai_evolution.py` defines targets, safe bounds, fitness components, readiness rules, proposals, canaries, and promotion history in the same subsystem family.

Why this breaks Pure Logic: proposer, evaluator, scope owner, and promoter share assumptions. A clean canary can still validate the wrong objective.

Required repair:
- split proposal, simulation, falsification, scope certification, and promotion into independent roles;
- require adversarial tests not selected by the proposer;
- retain old and candidate profiles until evidence separates them;
- add automatic rollback when post-promotion reality contradicts certification.

### 4. GOVERNOR_CONFIDENCE_THEATER

Break case: the governor assigns fixed confidence values such as 0.99, 0.98, 0.95, or 0.86 based primarily on which internal rule fired.

Observed example:
- `decision_governor.py` maps conditions directly to fixed confidence values and can recommend evolution, code-fix, runtime, or continuity actions.

Why this breaks Pure Logic: these numbers are labels, not calibrated probabilities or evidence-derived authority.

Required repair:
- remove confidence from authority decisions;
- separate `decision_priority`, `uncertainty`, `evidence_quality`, and `scope_authority`;
- permit confidence only as a heuristic ranking signal.

### 5. PROPERTY_SCOPE_EXPANSION

Break case: one verified implementation property expands into a broader operational claim.

Observed example:
- `ai_from_scratch/model.py` sets `production_grade = fully_native`.

Why this breaks Pure Logic: native implementation establishes implementation provenance, not production reliability, security, robustness, calibration, or safety.

Required repair:
- delete the implication;
- make production readiness a separate certification object with explicit dimensions and evidence.

## P1 failures

### 6. WORLD_MODEL_AS_WORLD

Break case: normalized summaries from internal subsystems are aggregated into a world model and then used by the governor as the decision surface.

Why this breaks Pure Logic: a world model is still a model. Freshness checks reduce staleness but do not establish correctness, completeness, or independence.

Required repair:
- every world-model claim needs provenance and scope;
- track observation versus inference versus policy versus prediction;
- preserve unresolved alternatives;
- add contradiction probes that can invalidate a domain even when it is fresh.

### 7. IDENTITY_CONTINUITY_AUTHORITY

Break case: `same_system` and `continuity_score` become gating facts across memory, evolution, world-model, and decision code.

Why this breaks Pure Logic: identity continuity is itself an inferred model. If its detector shares the same corrupted state it is checking, it can self-confirm.

Required repair:
- treat identity continuity as a contested claim with independent evidence;
- prevent continuity success from certifying unrelated capability or safety claims;
- test continuity detectors using corrupted, forked, replayed, and partially restored state.

### 8. PRESSURE_HARNESS_SCOPE_BLINDNESS

Break case: a pressure suite passes all known scenarios and the resulting score is treated as survivability evidence outside those scenarios.

Why this breaks Pure Logic: passing a finite test suite establishes only demonstrated test scope.

Required repair:
- attach exact scenario coverage to every pressure result;
- add withheld/fresh adversarial scenario generation;
- distinguish regression survival from scope certification;
- prohibit promotion when only familiar tests were used.

## Architectural repair target

Zero-OS should converge on this authority flow:

`observation -> claim/proposal -> provenance -> alternatives -> independent falsification -> demonstrated scope -> provisional authority -> bounded action -> post-action reality check -> preserve failure/correction`

The following must never create authority by themselves:

- confidence
- consensus
- memory frequency
- historical success
- a perfect internal score
- freshness
- passing proposer-selected tests
- native implementation
- identity continuity
- the fact that a component is called a verifier

## Required system-wide object

Every authority-bearing claim should eventually use one shared structure:

```text
Claim
  value
  source
  claim_type
  requested_scope
  demonstrated_scope
  provenance
  observations
  assumptions
  alternatives
  contradictions
  independent_evidence_groups
  falsification_attempts
  status: unknown | contested | provisional | rejected
  revocation_conditions
  observed_at
  expires_at
```

This is the primary migration target. Once authority is represented explicitly, legacy scores can remain useful as search heuristics without being confused with truth.

## Audit status

This is a static architectural break audit, not proof that every listed path is currently exploitable at runtime. The findings identify logical failure classes that the present code permits or strongly encourages. Each class requires focused regression tests and runtime pressure before promotion of a repair.

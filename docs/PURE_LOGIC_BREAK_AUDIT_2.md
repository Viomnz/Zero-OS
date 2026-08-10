# Pure Logic Break Audit 2

This audit attacks the current stacked Zero-OS architecture rather than assuming the new Pure Logic modules are correct.

## Critical failures

### 1. EXECUTOR_AUTHORITY_BYPASS

`governor_claim_gate.enforce_governor_authority()` exists, but `task_executor.py` still calls the legacy governor path and executes steps without routing the plan through the new claim authority gate.

Impact: the architecture can possess a correct authority gate that is not on the actual execution path. A decorative verifier has zero security value.

Required repair: make every mutating executor entry point fail closed unless it receives an authority token/claim for the exact mutation scope. The check must live at or below the final action boundary, not only in planners/governors.

### 2. SELF_DECLARED_INDEPENDENCE

`pure_logic_authority.py` treats distinct `independent_group` strings as independent evidence groups. Nothing proves those groups are operationally independent.

Impact: one compromised or correlated producer can submit evidence labeled `formal` and `empirical` and manufacture two-group authority.

Required repair: independence must itself be a claim backed by provenance and measured failure diversity/correlation. Caller-supplied labels cannot create independence.

### 3. EVIDENCE_SUBJECT_LAUNDERING

Authority certification checks evidence scope but does not bind evidence to the exact claim subject/value/version/environment.

Impact: evidence that supports `runtime:ready` for one runtime instance or state can be reused to certify another claim with the same scope string.

Required repair: evidence must carry subject identity, claim fingerprint, observation time, environment/version, and provenance. Certification must reject mismatched subjects.

### 4. EXPIRED_AUTHORITY_STILL_PERMITS

`Claim` contains `expires_at_utc`, but `authority_required()` does not evaluate expiration.

Impact: a once-valid claim can remain executable after its evidence has gone stale.

Required repair: authority checks must evaluate time, state revision, dependency revision, and explicit revocation conditions at the moment of use.

### 5. REVOCATION_IS_METADATA_ONLY

Claims store `revocation_conditions`, but no central revocation engine evaluates those conditions before authority is consumed.

Impact: the architecture says authority is revocable while continuing to accept claims after the revocation trigger occurs.

Required repair: implement active revocation and invalidation propagation. Changes in graph, dependency, identity, telemetry, or runtime state must invalidate dependent claims.

### 6. CODE_INVESTIGATOR_IMPORT_BREAK

`invariant_investigator.py` imports `claim_from_dict` from `pure_logic_claims`, but that function is not defined there.

Impact: the new invariant investigation module can fail at import time.

Required repair: remove the unused import or implement the intended conversion function, then add an import smoke test.

### 7. COVERAGE_CLAIM_SELF_CERTIFICATION RISK

The invariant investigator produces both the finding claim and the coverage claim from the same graph and same investigator.

Impact: discovery and coverage are structurally separated as objects, but not yet independent as evidence sources.

Required repair: coverage certification must be performed by a different mechanism using runtime traces, alternate parsers/static analyzers, dependency manifests, dynamic dispatch discovery, and adversarial omission tests.

### 8. SECURITY_BENCHMARK_ORACLE_RUNNER

`run_pressure_case()` accepts a `defensive_runner` that returns names of observed controls. A runner can simply return `case.expected_controls`, causing every mechanism case to pass without exercising Zero-OS.

Impact: the benchmark currently defines a test protocol, not a genuine system pressure test.

Required repair: bind cases to actual Zero-OS entry points, capture immutable execution evidence, and derive observed controls from traces/results rather than trusting the runner's declaration.

### 9. SECURITY_SCOPE_CERTIFICATION IS PLACEHOLDER LOGIC

`scope_certified` is computed as `mechanism_passed and not unresolved_scope` rather than passing through the Pure Logic authority system with independent evidence.

Impact: the benchmark uses the word certification without independent certification.

Required repair: benchmark scope results must become normal claims and use the same independent authority path as the rest of Zero-OS.

### 10. LEGACY BOOLEAN AUTHORITY SURFACE REMAINS LARGE

The repository still contains many consumers of `same_system`, `beneficial`, readiness flags, pressure scores, memory confidence, and planner confidence. The new claim layer only wraps selected paths.

Impact: authority migration is incomplete; legacy routes can remain semantically privileged even if new modules are correct.

Required repair: inventory every mutation-capable entry point and every authority-like boolean/score. Migrate or explicitly quarantine each one.

## Priority

P0: executor authority enforcement, evidence subject binding, verified evidence independence, expiration/revocation.

P1: real coverage certification, benchmark trace binding, invariant-investigator import repair.

P2: migrate remaining legacy booleans/scores, then strengthen domain-specific cyber mechanisms.

## Pure Logic conclusion

The current architecture has improved its vocabulary for authority faster than it has enforced authority at every physical execution boundary. The next phase should therefore stop adding abstractions and make the existing abstractions unavoidable.

The target invariant is:

> No state-changing action can occur unless the exact action, subject, scope, evidence freshness, and evidence independence survive a final authority check at the execution boundary.

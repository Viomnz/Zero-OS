# Zero-OS Pure Logic Break Epoch v7

This audit attacks the current v6 runtime-integration stack at its trust roots rather than adding another feature layer.

## P0 root failures

### 1. Authority-artifact forgery

`issue_capability_lease()` is a public function that creates a lease from arbitrary principal/scope strings. `classify_action()` later trusts any active lease containing the required scope. The lease carries a `source` label, but that label is merely a default string and is not cryptographically or causally bound to a constitutional decision.

Likewise, `issue_execution_ticket()` can create a runtime mutation ticket directly. `consume_execution_ticket()` checks action kind, expiry and consumption state, but does not prove that the ticket was minted by `final_action_authority` after v5 constitutional approval.

Therefore the current invariant is effectively:

`possession of a syntactically valid authority artifact -> authority`

The target invariant must be:

`unforgeable authority artifact <- attested constitutional decision + exact state + exact action + exact principal`

This is the highest-priority failure because every downstream gate assumes these artifacts are trustworthy.

### 2. Integration audit is not causal

`authority_runtime_integration_audit.py` parses each required file and then searches source text for required symbol names. This can be satisfied by dead code, comments, unused imports, or a branch that is never reachable from the actual sink.

Symbol presence is useful lint evidence. It cannot be architecture-promotion evidence.

Replace it with call-graph/data-flow evidence plus runtime trace assertions for consequential operations.

### 3. Security verifier independence is mostly logical, not privileged

Self-repair uses readiness and triad probes as distinct outcome evidence groups. They are different method labels, but they execute in the same Python process and consume software-controlled state under the same OS authority domain.

A compromised runtime can therefore corrupt both while the verifier reports two independent groups.

Independence needs explicit lineage plus privilege/process/device separation where consequence justifies it.

### 4. Cure Firewall success semantics are unsound

`run_cure_firewall_agent()` always returns `"ok": True` after computing failed/verification-failed issues. This lets callers treat a run with failed targets as mechanism success unless they inspect secondary fields.

The default target discovery also stops at 25 eligible files. A perfect score over that sample cannot represent whole-workspace survival.

Required repair:

- `ok` must derive from explicit required checks;
- report discovered/eligible/scanned counts and coverage ratio;
- scope the verdict to the exact target set;
- never call partial coverage `perfect` without a scope qualifier.

### 5. Antivirus feed signing key is deterministic

`_feed_key()` creates the feed key as SHA-256 of the key-file path string. This is deterministic and reproducible from source/layout knowledge; it is not a secret signing key.

A signed feed therefore does not establish publisher authenticity against a knowledgeable local attacker.

Required repair:

- generate cryptographically random key material or use OS/hardware-backed key storage;
- separate signing authority from runtime scanner authority;
- support key rotation/revocation;
- bind feed version/issuer/expiry and reject rollback.

### 6. Antivirus policy and suppressions are authority surfaces

Antivirus policy, threat-feed state and suppressions are writable state that controls detection and response. They need to be classified as security-policy mutations under the constitutional authority model. A malware process should not be able to weaken detection by changing thresholds, exclusions, response mode or suppressions through direct module access.

## P0 architectural consequence

Do not spend the next epoch adding more detectors.

Build an **Authority Root of Trust + Security Control Plane**:

1. unforgeable authority tokens/leases;
2. single privileged issuer boundary;
3. exact principal/action/state binding;
4. causal runtime attestation from issuer to sink;
5. security-policy mutations governed by the same authority kernel;
6. privileged correction/recovery domain separated from ordinary runtime;
7. call-graph + runtime-trace mediation proof;
8. independent verifier domains for critical outcomes.

## P1 after the root is repaired

- mediate direct process execution across Python/native/tooling code;
- extend whole-repository audit to native C#/PowerShell/build scripts;
- formalize legal state transitions and model-check critical authority/correction paths;
- replace sample-based security scores with explicit demonstrated-scope claims;
- run adversarial tests for stolen tokens, forged authority artifacts, compromised telemetry, verifier correlation, policy suppression, rollback attacks and native bypasses.

## Promotion rule

Zero-OS must not promote the architecture while any known path can manufacture its own authority artifact or while security-policy state can be changed outside the protected authority/correction plane.

Passing detector benchmarks does not compensate for a broken authority root.

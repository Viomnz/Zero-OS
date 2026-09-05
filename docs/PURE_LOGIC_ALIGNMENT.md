# Pure Logic implementation alignment

## Source and audit scope

Foundation: [the supplied 144-page PDF](../publication/Pure_Logic_Framework_Refined.pdf),
with exact identity in [the source manifest](../publication/pure_logic_source.json).
The prior 134-page PDF is preserved unchanged. Sections 285-287 are appended in
the supplied source and are part of the current foundation.

Base inspected: `44aa1ba` on `main`. This change traces the Zero Engine decision
plane from scan through certification to enforcement. It also inspects the
legacy governance, contradiction, resource, and execution modules named below.
Open PRs, including #35 and #36, are proposals and were not treated as merged
implementation. This is not an exhaustive audit of every repository module.

**Result:** Zero OS has a Pure Logic foundation and partial implementations.
It does not yet implement the full PDF across every execution path.

## Six Master Laws

| PDF requirement | Code and behavior inspected | Alignment / remaining work |
| --- | --- | --- |
| Reality: source, method, conditions, epistemic status (10, 19-20, 172-173) | `pure_logic_authority.py` stores source, group, scope, quality and support; parsing now rejects malformed evidence. | Partial. No complete authenticated Reality Ledger carrying conditions, Observed/Derived/Assumed/Proposed status and causal dependencies on this path. |
| Survival: provisional scope; no self-certification (11, 26-28, 175, 285.10-11) | `certify_scope` separates proposal from scope; checks independent groups per dimension; scope contradictions block certification. Executor now consumes the result. | Tested locally. Group labels remain assertions, not independent provenance proof. No complete pressure coverage, time/revision binding or live revocation infrastructure. |
| Investigation: cause, repair, preserved history, stronger retest (12-13, 176-179) | `contradiction_engine.py` identifies typed issues; executor now stores the denied proposal/authority and requests investigation. | Partial. Its bounded summary history is not a complete FailureRecord with cause, correction, external effects and stronger retest. Recording a hold does not complete investigation. |
| Plurality: preserve viable branches (14, 180) | `select_stable_branch` returns selected and discarded reviews; decision reports preserve candidates denied execution. | Partial. No demonstrated persistent lifecycle for Active/Dormant/Restricted/Contradicted/Merged/Reopened/Unresolved branches throughout runtime. |
| Path / Water Logic: choose justified lower-damage route (15-17, 181-182, 285.2, 285.6-7) | Decision plane excludes unauthorized paths; permits observation and explicit non-action. Maintenance has repair/verification choices. | Partial. Fixed subsystem priority is scheduling, not demonstrated minimization of unnecessary irreversible damage. Objective legitimacy, alternatives, inaction cost and external reversibility are not fully modeled here. |
| Resource: scale effort with stakes and delay (18, 183, 204) | One-mutation budget, due intervals; `ai_from_scratch/resource_constraint_layer.py` tracks approximate resource pressure. | Partial. Compute/energy estimates and fixed priorities are not a full information-gain, consequence and deferral-debt allocator. |

## Confirmed failure and repair

**Failure:** `decide_zero_engine` could reject all mutation candidates while
`subsystem_executor` independently chose a mutation using confidence. A direct
reproduction with `status=contested`, authority zero and confidence 1.0 still
called the enforcer once. This violates sections 56, 76, 202 and 285.10.

**Cause:** discovery ranking was repeated downstream of scope certification,
without consuming the authority result. The execution boundary bypassed the
previous authority separation.

**Repair:** filter due candidates by exact scope authority, scan failures and
explicit blockers; rank only survivors; check authority again before enforcement.
Missing/invalid/contested authority produces `control_state=zero`, preserves the
proposal, and does not call the enforcer. Unknown action names no longer inherit
read-only status. Status reports include authority and blocked-mutation counts.

**Stronger retest:** behavioral tests cover absent and contested authority,
wrong scope, NaN and string scores, malformed scope, unauthorized high-confidence
competition, unavailable scans, explicit blockers, due scheduling, unknown actions,
positive authorized execution, and the one-mutation limit. Evidence tests cover
Boolean coercion, source relabeling, proposer families, split scope evidence and
scope-specific contradiction. See `tests/test_pure_logic_execution.py`,
`tests/test_pure_logic_authority.py`, and `tests/test_zero_engine.py`.

## Canonical refinements and larger integration gaps

| PDF mechanisms | Current assessment in inspected paths |
| --- | --- |
| Distributed Correction Capacity; normative non-self-certification (285.1, 285.4) | Not established by in-process dictionaries or same-process gates. Distinct protected detection, challenge, revocation, enforcement and rollback channels require integration and testing. |
| Experience Harm Model; reflective preferences; objective legitimacy (285.2-4) | Foundation requirements; no complete action-bound assessment of affected agents, provenance, manipulation, challenge and action/inaction consequences on this path. |
| Non-Erasure Accounting; reversibility and deferral debt; necessary harm (285.5-7) | Backup availability is not evidence that external consequences are reversible. These dimensions are not fully represented in the inspected scheduler. |
| Non-coercive referee and separate execution authority (285.8) | Epistemic confidence does not grant this executor permission to mutate. Separate human/operational permission must remain an additional gate, not a substitute for scope evidence. No global referee claim is made. |
| Teaching-method adaptation (285.9) | Required when communication repeatedly fails; not validated by the decision-plane regression suite. |
| Discovery-scope separation; pressure coverage (285.10-11) | Bypass repaired and regression-tested in this plane. Broad test independence and attack-space coverage remain open. |
| Memory compression fidelity; metalogic comparison (285.12-13) | No full-vs-compressed causal decision comparison or independent cross-logic protocol was established in this audit. |
| Unknown/Unmapped, Logic/Ontology Foundry (21-23); graph revocation (55, 201); replay/RSI (58-60, 205, 208-209) | Existing experiments and module names do not establish complete integrated mechanisms. Fresh end-to-end evidence is required. |

## Operational boundary and next integration requirement

Built-in scans do not currently supply independent `authority_evidence` to the
decision engine. Previously the bypass concealed that gap. With the repair,
automatic backup, failover, revalidation and verification proposals wait for
evidence. Observation and state reporting continue. Scan functions can create
bookkeeping directories; the tested guarantee concerns mutation enforcer calls,
not a globally write-free scan.

The next integration must connect authenticated evidence for a specific subject,
action, target, revision, conditions and time window; preserve independent
permission; and revalidate live dependencies at the actual operation boundary.
Do not populate missing evidence from confidence, success counters, or claims
made by the proposing adapter. The generic runtime plane (`adapter.run`), direct
commands and native execution remain outside this patch's enforcement scope.

## Validation record

See the PR description for actual test totals and baseline failures. The Pure
Logic tests are now included in CI. Passing these tests demonstrates the listed
local behaviors; it does not certify complete machine-native Pure Logic or
protection against same-privilege adversaries.

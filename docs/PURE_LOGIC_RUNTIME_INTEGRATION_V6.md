# Zero-OS Pure Logic Runtime Integration v6

## Purpose

v5 introduced the constitutional Pure Logic Authority Kernel. v6 makes that authority causal at runtime instead of optional architecture.

The governing target is:

> No consequential operation may touch reality merely because a planner, governor, memory system, repair engine, or evolution engine recommends it.

A consequential operation must survive the relevant constitutional authority path at the point where capability or mutation authority is created.

## Runtime authority chain

For mutations:

1. exact claim + state revision;
2. exact independently supported evidence;
3. active Authority Ledger scope;
4. active Objective Authority;
5. identity provenance and consequence-sensitive authentication;
6. Resource Law verification budget;
7. legal-state and correction-plane checks;
8. v5 constitutional decision;
9. short-lived single-use execution ticket;
10. runtime-kernel ticket consumption;
11. sink-level acknowledgement for protected direct/background mutation implementations.

For sensitive non-mutating access:

1. identity/trust capability context;
2. exact capability scope;
3. v5 claim + objective authority for that scope;
4. Resource Law budget;
5. constitutional capability lease;
6. sink checks such as destination-bound egress and credential-transmit scope.

Low-risk observation/status capability may remain lightweight. It does not grant authority for privileged operations.

## Major migrations

### Mutation ticket minting

`final_action_authority.py` can no longer mint a mutation ticket from claim evidence alone. Missing constitutional request, objective ledger, or verification budget fails closed.

### Main executor

The existing action engine already routes through `classify_action()`. v6 changes that policy boundary so:

- registered mutations require the runtime mutation kernel and its v5-derived ticket;
- sensitive/high-risk reads require a live exact-scoped constitutional capability lease;
- a configured `safe_auto` label cannot substitute for constitutional authority.

### Self repair

`self_repair_run()` now requires a recent consumed `self_repair` ticket handoff at the actual repair implementation. This blocks daemon/background/direct calls that did not pass the runtime kernel.

Repair success is split into mechanism success and independent outcome verification. The repair actor cannot be its own only verifier.

### Source evolution

Proposal, simulation, review, and isolated canary remain possible without live source-mutation authority because they are investigation paths.

Live promotion now requires:

- a v5-authorized `self_upgrade` sink handoff;
- Protected Correction Plane eligibility for `zero_os_source`;
- isolated canary/invariant evidence;
- runtime-authority integration audit;
- scoped capability-bypass check on changed files;
- Architecture Promotion Authority;
- post-write verification and independent readback;
- rollback if post-write evidence contradicts the expected result.

Background source evolution may investigate and canary, but it cannot promote live source merely because its own canary passed.

### World model and governor

Legacy readiness/continuity/recovery booleans remain useful as observations. v6 projects them into Reality Ledger records with provenance, freshness, requested scope, demonstrated scope, and contradiction state before the governor uses them.

Governor confidence and priority are explicitly advisory. They grant zero authority.

### Memory

Memory weights remain useful for retrieval and branch prioritization. Every memory item now has `authority_weight = 0.0`, and the module exposes `memory_is_not_authority = True`.

Repeated remembered success cannot renew or create operational authority.

## Promotion rule

v6 adds `authority_runtime_integration_audit.py`. The architecture cannot be promoted if an identified critical/high integration path is missing.

Current identified requirements cover:

- constitutional mutation-ticket minting;
- executor-to-authority-policy dependency;
- sensitive capability lease enforcement;
- self-repair sink handoff and outcome verification;
- source-evolution correction/promotion authority;
- Reality Ledger projection at the governor boundary;
- non-authoritative memory semantics.

Even if all identified requirements pass, the result is only static integration evidence. It is not proof of complete runtime reachability or security.

## Explicit unresolved scope

v6 does not certify:

- every dynamic dispatch path;
- native/non-Python components;
- dependency internals;
- firmware or hardware;
- concurrency/interleaving behavior;
- formal illegal-state unreachability;
- real independence of all software verifiers;
- absence of unknown mutation/capability sinks.

Those remain future pressure and formal-verification targets.

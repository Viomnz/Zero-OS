# Zero-OS Pure Logic Root of Trust v8

## Purpose

v8 repairs the highest-leverage failure found in the v7 break audit: the objects representing authority were easier to forge than the constitutional reasoning that supposedly created them.

The new rule is:

> A lease or ticket is not authority because it has the right fields. It must carry a root-issuer attestation over the exact authority-bearing state, and the sink must verify that attestation before use.

## Authority artifact binding

The v8 attestation binds:

- issuer identity;
- artifact type and unique artifact id;
- principal identity;
- claim authority id;
- objective authority id;
- action/capability kind;
- subject id;
- state revision;
- exact scopes;
- issue time and expiry;
- unique nonce;
- constitutional decision status.

Any change to those fields invalidates the signature.

## Issuer semantics

The root issuer does not accept `allowed=True` from callers. It recomputes the Pure Logic constitutional decision using the ConstitutionalRequest, AuthorityLedger, ObjectiveAuthorityLedger, Resource Law verification budget, active dependencies, correction-plane result, and legal-state result.

Only a surviving constitutional decision can produce an attestation.

Legacy direct APIs `issue_capability_lease()` and `issue_execution_ticket()` now fail closed.

## Runtime verification

Capability policy verifies the issuer signature before accepting a sensitive lease. Execution-ticket consumption and sink acknowledgement verify the issuer signature and exact ticket-to-attestation binding before accepting mutation authority.

Manually inserting plausible ticket JSON therefore no longer creates usable authority without a valid issuer attestation.

## Security policy

Agent permission-policy mutation now requires a fresh consumed `policy_change` ticket handoff, preventing an ordinary caller from simply downgrading a sensitive action to a permissive tier.

## Cure Firewall scope semantics

Cure Firewall agent results now separate mechanism success from scope coverage. Reports include eligible targets, scanned targets, coverage ratio, unresolved target count, demonstrated scope, and scope-complete state. A bounded 25-file discovery run can no longer silently promote itself to a complete success verdict when more eligible files exist.

## Integration audit

The runtime integration audit no longer treats mere symbol/string presence as sufficient integration evidence. It parses Python ASTs and checks for required call edges such as constitutional decision, root issuance, attestation verification, ticket handoff, outcome verification, and architecture promotion.

This is stronger static evidence but still not full reachability proof.

## Explicit unresolved scope

v8 is a software root of trust, not a hardware root of trust. It does not certify resistance to a same-privilege hostile process that can steal the issuer key, rewrite the verifier, corrupt persisted authority ledgers, or subvert the Python runtime.

Still unresolved:

- separate issuer process / OS privilege domain;
- TPM/Secure Enclave/HSM-backed issuer key;
- runtime trace attestation proving issuer-to-sink reachability;
- native/C#/PowerShell/kernel mediation;
- true verifier independence across privilege domains;
- antivirus feed key migration from deterministic legacy derivation;
- protected antivirus suppressions/policy feed control;
- formal illegal-state unreachability.

Promotion must remain provisional until those scopes receive independent pressure.

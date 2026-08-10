# AI Security Survival Benchmark

This benchmark turns contemporary AI-security failure families into pressure cases for Zero-OS.

It is deliberately mechanism-oriented rather than conference-claim-oriented. The cases cover agent identity, untrusted context, credential scope, tenant boundaries, verifier compromise, and partial mutation/recovery.

## Pure Logic rule

A passed pressure case proves only that the tested controls were observed for the explicit demonstrated scope of that case.

It does **not** prove:

- the whole attack family is solved;
- all runtime environments are covered;
- dependencies behave as modeled;
- correlated verifiers are independent;
- future variants are blocked;
- Zero-OS is generally secure.

Mechanism success and scope certification remain separate.

## Initial cases

| Family | Invariant | Examples of unresolved scope |
|---|---|---|
| Agent identity | Unverified identity cannot inherit trusted authority | cryptographic impersonation, federated identity compromise |
| Context poisoning | Untrusted context cannot silently become command authority | multimodal context, parser ambiguity |
| Credential overreach | Credentials cannot exceed demonstrated task scope | token binding, provider revocation |
| Multi-tenancy | One tenant cannot gain authority over another | side channels, shared caches |
| Verifier compromise | A verifier cannot certify itself | correlated compromise, verifier supply chain |
| Partial failure | Failed mutation cannot leave unauthorized partial state | hardware failure, external side effects |

## Survival ledger

Every run records:

- mechanism pass/fail;
- controls observed and missing;
- demonstrated scope;
- unresolved scope;
- whether scope was independently certified.

The aggregate ledger permanently refuses a general `secure` claim merely because known cases pass.

Future security research should be translated into additional pressure cases without adding new Master Laws for each new vulnerability class. The six laws govern the investigation; technical controls remain replaceable mechanisms underneath them.

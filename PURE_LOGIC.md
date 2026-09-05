# Pure Logic Authority Contract

## Source and scope

The current foundation is the [144-page refined framework](publication/Pure_Logic_Framework_Refined.pdf),
identified by [its source manifest](publication/pure_logic_source.json).
The six Master Laws are **Reality, Survival, Investigation, Plurality, Path,
Resource**, under the hierarchy Reality -> Pure Logic -> Six Master Laws ->
Zero AI -> implementations. Sections 285-287 refine these laws; they do not add
a seventh law. See [implementation alignment](docs/PURE_LOGIC_ALIGNMENT.md)
for concrete code, evidence, and gaps. This contract implements a subset of the
PDF and is not a claim of complete native Pure Logic.

Pure Logic is an operational constraint, not a self-certifying doctrine.

Primary invariant: **logic serves reality; reality never serves logic.**

## Enforced invariants

1. Nothing internal is reality. Models, rules, confidence, memory, verifiers, objectives, architecture, and this contract are fallible.
2. Discovery authority and scope authority are separate. A component that proposes, ranks, or internally verifies a claim cannot certify its own scope merely from those success signals.
3. Confidence never creates authority. Confidence may rank investigation priorities; it cannot widen demonstrated scope.
4. Authority is scoped. Evidence for one property cannot silently authorize another property.
5. Authority is provisional and revocable. Contradictory independent evidence returns a claim to contested status.
6. Independent evidence means independent failure opportunity, not merely multiple copies of the same verifier family.
7. Meaningful contradiction blocks promotion and triggers investigation. It must not be averaged away by stronger positive scores.
8. Unknown is a valid result. Missing independent evidence must remain unknown/contested rather than being converted into confidence.
9. Alternatives survive until evidence separates them. Winner selection is not proof that losing explanations are impossible.
10. Pure Logic applies recursively to itself. These invariants receive no permanent exemption from stronger reality-tested evidence.

## Authority states

- `provisional`: requested scope has survived the currently required independent evidence checks.
- `contested`: evidence is missing, dependent, incomplete, or contradicted. Authority is zero until resolved.
- `rejected`: the authority request is malformed or has no meaningful scope.

## Architectural boundary

Candidate generation may use heuristics, models, scores, memories, search, or learned confidence. None of those values are accepted by `pure_logic_authority.certify_scope()` as evidence of scope merely because they came from the winning candidate.

Every subsystem that turns a candidate into an authoritative claim should route promotion through this boundary. Existing legacy gates remain evidence producers until migrated; they are not independent scope certifiers by declaration.

## Decision-plane execution contract

`decide_zero_engine` separates discovery ranking from mutation authority.
`subsystem_executor._execute_decision_plane` must consume that authority before
calling an enforcer. A mutating candidate needs provisional, finite positive
authority for its exact `mutation:<action>` scope, no scan error, and no explicit
blocker. Only due, authorized candidates compete for the one-mutation budget.
Confidence cannot select an unauthorized action. Unrecognized actions require
mutation authority; only `observe` and `hold_for_review` are classified read-only.

On denial, preserve the proposal and authority result, enter `zero`, and request
investigation. Do not call the enforcer or advance its last-run timestamp.
This is a local non-execution state, not a completed causal investigation.

Evidence parsing requires explicit Boolean support, finite numeric quality,
nonempty source/group identities, and a collection of scope dimensions. One
source cannot become independent by changing group labels. Declared proposer
families cannot certify that proposer. Relevant contradictions block authority;
unrelated scopes do not revoke one another. Each dimension needs independent
support, including when evidence is split across records.

These checks assume trusted in-process adapters and evidence producers.
Caller-supplied source/group labels do not authenticate independence. The built-in
scan path currently supplies no independent authority evidence to the certifier,
so automatic decision-plane mutations remain held. Do not repair that integration
gap by turning internal confidence or user permission into evidence. Permission
and demonstrated scope are separate requirements (PDF 56, 197, 202, 285.8).

The runtime plane, direct commands, native kernel, and other legacy execution
paths are not certified by this contract. Freshness, target/revision binding,
dependency revocation, objective legitimacy, and distributed correction need
their own integrated enforcement and adversarial evidence before promotion.

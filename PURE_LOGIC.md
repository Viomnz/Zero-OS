# Pure Logic Authority Contract

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

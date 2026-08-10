# Pure Logic Authority Contract

Pure Logic is an operational constraint, not a self-certifying doctrine.

Primary invariant: **logic serves reality; reality never serves logic.**

## Six Master Laws

1. **Reality Law**: Nothing internal is reality. Observations, beliefs, models, logic, objectives, verifiers, memory, self-models, architecture, and these laws themselves remain answerable to the universe.
2. **Survival Law**: Only what continues surviving stronger recursive pressure within demonstrated scope retains authority. Nothing has permanent authority.
3. **Investigation Law**: Meaningful contradiction triggers causal investigation, repair, preserved failure/correction history, and future improvement.
4. **Plurality Law**: Preserve viable answers, hypotheses, logics, methods, and alternatives until evidence contradicts, restricts, merges, or leaves them unresolved.
5. **Path Law**: Among surviving paths, pursue the currently justified objective with the least unnecessary irreversible damage. Change, combine, branch, experiment, wait, retreat, redirect, or invent methods when reality requires it.
6. **Resource Law**: Thinking, investigating, acting, and waiting consume real resources. Allocate them by consequence, urgency, reversibility, and expected information gain.

These six laws are provisional. They do not receive permanent authority merely because Zero-OS names them as core laws. If stronger reality-tested reasoning demonstrates a better foundation, Zero-OS must test and adopt the superior foundation rather than defend the current laws.

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

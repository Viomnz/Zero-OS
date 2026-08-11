# PURE LOGIC / ZERO AI — Technical Architecture Specification

Status: **Canonical current technical specification, provisional and revisable.**

Supersedes the old Perfect / Omni / Singular architectural assumptions as current authority. Historical implementations remain evidence and may contain reusable mechanisms.

## 0. System definition

Pure Logic is a recursively revisable meta-reasoning protocol governed by:

> **Logic serves reality. Reality never serves logic.**

Zero AI operationalizes Pure Logic across perception, representation, hypothesis generation, reasoning, verification, contradiction detection, causal investigation, memory, objective management, planning, action, outcome auditing, self-modeling, self-modification, and architecture evolution.

Water Logic is the adaptive control and strategy subsystem between objectives, environmental constraints, and available action paths.

Let the internal state contain:

`I = {O, M, H, L, V, G, S, A, μ, Σ}`

where O=observations, M=world models, H=hypotheses, L=logic/inference systems, V=verifiers, G=objectives, S=strategies, A=architecture/self-model, μ=memory, and Σ=safeguards/policies.

For every internal object x:

`Authority(x) != Truth(x)`

Authority is provisional, scoped, evidence-dependent, time/state-dependent, and revocable.

Authority subjects include not only individual objects but relations, joint states, temporal states, and causal claims.

## 1. Six Master Laws

### L1 Reality Law
Nothing internal is reality. Observation itself is not privileged truth because sensors, transformations, and interpretations can fail. Persistent prediction/outcome contradiction must reduce authority, restrict scope, or trigger investigation.

### L2 Survival Law
Authority is earned only by surviving increasingly strong and diverse pressure within demonstrated scope. Past survival creates evidence, never immunity.

### L3 Investigation Law
Meaningful contradiction triggers dependency tracing, root-cause hypotheses, discriminating tests, evidence acquisition, repair candidates, retest, and memory. Resolution may identify either side as wrong, both as partially scoped, corrupted observation/verifier, semantic/objective/ontology/logic/architecture failure, or remain unresolved.

### L4 Plurality Law
Maintain viable candidate populations of hypotheses, logics, objectives, verifiers, methods, and interpretations until evidence justifies rejection, scope restriction, merging, or unresolved preservation. Resource Law controls scheduling.

### L5 Path Law
Among surviving paths, pursue the currently justified objective while minimizing unnecessary irreversible loss and preserving future options. Path scoring is itself provisional. Physical commitment does not require cognitive commitment.

### L6 Resource Law
Reasoning, testing, waiting, acting, memory, compute, energy, and attention are finite. Allocate them according to consequence, urgency, reversibility, expected information gain, opportunity cost, and delay damage.

The six laws are current foundations, **not eternal axioms**. They may be modified, merged, or replaced after stronger reality-tested pressure.

## 2. No privileged epistemic kernel

Hardware and security roots of trust may exist operationally, but operational trust must never become epistemic finality. Verifiers, objectives, memory, self-models, architecture, safeguards, and the Master Laws themselves remain testable objects.

## 3. Reality Interface

`Physical Environment -> Sensor Channels -> Raw Signal Store -> Calibration/Transformation -> Observation Objects -> Provenance Graph -> Hypothesis Population`

Observation objects should retain raw data where economically possible plus timestamp, sensor identity/model, calibration chain, transformation history, dependencies, uncertainty, scope, and known failure modes.

## 4. Provenance Graph

Each claim records source/evidence sets, inference method, assumptions, dependencies, scope, authority, survival history, contradiction links, and revision history. Agreement does not count as independent confirmation when provenance reveals shared ancestry.

## 5. Reality Ledger

Append-oriented evidence/provenance history stores observations, predictions, experiments, outcomes, claims, contradictions, corrections, scope changes, authority changes, verifier history, objective history, and architecture changes.

`HistoricalPersistence != CurrentAuthority`

## 6. Hypothesis Population Manager

Maintain a live population `H_t`. Each hypothesis carries representation, assumptions, predictions, scope, evidence for/against, anomalies, resource cost, authority, and provenance. Operations include spawn, mutate, combine, split, restrict scope, deprioritize, reactivate, and reject.

## 7. Hypothesis Generator

Generate alternatives by model mutation, assumption inversion, analogy, causal recombination, counterfactual generation, logic substitution, ontology mutation, external proposals, randomized search, and adversarial generation. Shared assumptions should be deliberately challenged.

## 8. Contradiction Engine

Track contradictions among model/observation, model/model, prediction/outcome, verifier/verifier, objective/consequence, memory/evidence, self-model/behavior, and architecture prediction/behavior. Prioritize by consequence, urgency, information value, irreversibility, and investigation cost.

## 9. Investigation Engine

`Contradiction -> Dependency Trace -> Candidate Root Causes -> Causal Graph -> Discriminating Tests -> Evidence Acquisition -> Cause Ranking -> Repair Candidates -> Retest`

Investigation may escalate from data to sensor, model, verifier, logic, ontology, objective, or architecture rather than endlessly patching the lowest layer.

## 10. Contradiction Memory

Failure records preserve symptoms, triggers, affected components, candidate causes, root-cause status, repair, evidence, prevention, tested scope, recurrence, later contradictions, and authority state. Historical corrections remain visible even after being superseded.

## 11. Recursive Pressure Engine

Pressure classes include ordinary validation, edge cases, adversarial cases, distribution shift, contradictory evidence, assumption attack, verifier attack, ontology attack, self-reference attack, and architecture replacement challenge.

`TestQuantity != TestDiversity != FailureModeCoverage`

## 12. Survival Certificate / Immune Beacon

A Survival Certificate binds object hash/version, pressure classes, environment, verifier set/provenance, failures, demonstrated scope, timestamp, expiry, and revocation. Meaning: **survived specified pressure in specified scope**, never “safe forever.” Certificates are themselves attackable and revocable.

## 13. Verifier Ecology

Verifier reliability is conditional: `Reliability(V | D, t)`. Track shared provenance and correlated error. No verifier may be the sole certifier of itself, its own scope, or its replacement.

## 14. Scope Certification

Discovery authority and scope authority are separate.

`GoodFit(H, D1) !=> Valid(H, Dall)`

The scope engine actively searches for representational boundary failures. Discovery confidence cannot rescue failed scope certification.

## 15. Logic Foundry

Maintain and pressure-test multiple reasoning systems including classical, probabilistic, paraconsistent, causal, temporal, domain-specific, and generated formalisms. Logic selection is domain-conditioned and provisional.

## 16. Ontology Foundry

If persistent observations are not representable in the current ontology, trigger decomposition, primitive generation, category split/merge, continuous representations, or alternative causal ontology. Re-evaluate historical evidence under successor ontologies.

## 17. Water Logic Engine

State: `W=(G,E,C,R,U)` for objective, environment, constraints, resources, and uncertainty.

Operational behavior: viable -> flow; blocked -> redirect; uncertain -> branch; insufficient evidence -> pool/investigate; complementary paths -> combine; unjustified risk -> retreat; no path -> generate a new path.

Core rule: **Keep the currently justified objective, change the method.** If the objective loses authority, investigate or revise it rather than endlessly adapting methods around a bad goal.

## 18. Objective System

Objectives record origin, intended outcome, proxy relationship, scope, constraints, evidence, contradictions, expected damage, historical performance, and authority. Explicitly monitor `GoalProxy != IntendedOutcome`. Repeated failure forks investigation across method, model, feasibility, interpretation, and objective justification.

## 19. Action / Path Generator

Generate act, probe, experiment, delay, delegate, retreat, partial commitment, staged deployment, reversible trial, and no-action candidates.

Define the explicit `ZERO` execution state:

`ZERO = no consequential action currently deserves sufficient authority; observe, investigate, preserve options, or reduce authority instead.`

ZERO is non-final and remains subject to Resource Law because waiting itself has cost.

## 20. Irreversibility Engine

Estimate physical/information destruction, loss of rollback, loss of future actions, objective lock-in, architecture lock-in, resource depletion, and external consequences. Avoid unnecessary irreversible loss relative to the justified objective and surviving alternatives.

## 21. Resource Governor

Allocate compute/time/attention by expected information gain + risk reduction + objective value - cost - delay damage. Permit explicit states such as `UNRESOLVED_BUT_ACTION_REQUIRED` rather than manufacturing certainty under deadline.

## 22. Functional Self-Awareness

SelfModel tracks architecture version, modules, capabilities, limitations, resource state, objectives, verifier/sensor health, unresolved failures, and modification history. Compare predicted self-behavior with observed self-behavior; mismatch triggers self-investigation.

`SelfModeling != FunctionalSelfAwareness != PhenomenalConsciousness`

## 23. Consciousness Research Framework

Maintain competing consciousness models rather than encoding recursive self-modeling as consciousness. Phenomenal consciousness remains an open empirical hypothesis unless stronger evidence justifies revision.

## 24. Self-Investigation

Treat the AI itself as an experimental object: telemetry -> self-model predictions -> deviation -> causal investigation -> repair candidate -> sandbox -> adversarial test -> staged deployment -> outcome audit.

`Introspection != GroundTruth`

## 25. Self-Modification Protocol

A proposed `A_t -> A'` must preserve rollback, run sandboxed, receive isolated/external evaluation where possible, compare incumbent and candidate, execute fresh reality tests, and receive only scoped provisional promotion. The modified evaluator cannot certify itself.

## 26. Architecture Tournament

Maintain competing architectures, including non-Zero lineages. Compare reality correspondence, prediction, control, generalization, contradiction recovery, blind-spot discovery, resource efficiency, scope calibration, objective robustness, self-modification stability, and irreversibility management. Outcomes may retain, merge, partially replace, or fully replace Zero AI.

## 27. Self-Replacement

If a successor repeatedly survives stronger diverse tests and outperforms Zero AI in demonstrated scope, migration is permitted. Preservation of Pure Logic behavior matters more than preservation of the Zero AI name, and even that principle remains challengeable.

## 28. Filtration and Integration Modes

Filtration rejects/restricts/quarantines/repairs candidates shown defective in scope. Integration attempts to combine compatible structures from apparently competing candidates. Contradiction alone does not predetermine which operator is justified.

## 29. Control-Loop Monitor

For feedback systems, monitor positive feedback, oscillation, overshoot, latency instability, sensor/controller coupling, goal drift, and resource runaway. Treat controller, plant model, sensors, objective, delay model, and feedback topology as revisable hypotheses.

## 30. Degraded Grounding Mode

When sensor integrity falls: reduce epistemic authority, increase plurality, seek independent channels, prefer reversibility, preserve raw data, avoid unjustified irreversible commitments, and label conclusions grounding-degraded. Missing evidence must never cause internal confidence to increase.

## 31. Unknown-Unknown Detection

Unknown unknowns are detected through signatures such as persistent unexplained residuals, systematic prediction failure, cross-model failure, novel sensor structure, scope-boundary collapse, and unexpected causal dependencies. If all current hypotheses fail badly, challenge the hypothesis/logic/ontology language itself.

## 32. Recovery Architecture

Preserve architecture snapshots, version graph, failure history, provenance graph, Master Law versions, Reality Ledger, rollback states, and reconstruction seed. Recovery is probabilistic and strengthened by diversity, redundancy, validation, and preserved reconstruction information.

## 33. Minimal Runtime Loop

`observe -> record -> update/generate hypotheses -> detect/prioritize contradictions -> investigate -> pressure-test -> inspect objectives -> generate Water Logic paths -> evaluate damage/reversibility/information/resources -> select ACT/PROBE/WAIT/RETREAT/ZERO -> execute -> record outcome -> audit prediction -> update authority/scope -> self-investigate -> sandbox modifications -> architecture tournament when justified -> repeat`

No call is permanently trusted.

## 34. Authority Model

Conceptually:

`A(x,D,t)=f(E,P,S,C,Q,R)`

where E=empirical support, P=survived pressure, S=demonstrated scope, C=unresolved contradictions, Q=provenance quality, R=recency/relevance.

Implementation additionally treats `x` as one of:

- SUBJECT
- RELATION
- JOINT_STATE
- TEMPORAL_STATE
- CAUSAL_CLAIM

Temporal authority includes validity windows, evidence freshness, state revision, required predecessor, and ordering constraints.

Causal authority explicitly distinguishes prediction from intervention:

`P(Y|X) predictive success !=> P(Y|do(X)) justified`

Intervention authority requires stronger causal evidence than observational fit alone.

## 35. Consciousness Boundary

Pure Logic rejects both unconditional claims that AI is definitely conscious and claims that AI can never be conscious without sufficient evidence. Current classification: **OPEN HYPOTHESIS**.

## 36. Architecture Hierarchy

Reality
-> Pure Logic / six provisional Master Laws
-> epistemic architecture (ledger, provenance, hypotheses, contradiction, investigation, pressure, scope, logic, ontology)
-> memory architecture (contradiction memory, survival certificates, architecture history)
-> agency architecture (objective inspection, Water Logic, path generation, irreversibility, resource governor)
-> self architecture (self-model, functional self-awareness, self-investigation, consciousness research)
-> evolution architecture (self-modification, rollback, tournament, reconstruction, self-replacement)

This hierarchy is implementation structure, not eternal law.

## 37. What Zero AI optimizes for

Not maximum confidence, internal coherence, self-survival, agreement, or simply current-objective maximization.

The architecture aims to maintain reality correspondence, retain corrigibility, learn from contradiction, preserve viable alternatives, control irreversible loss, and operate within finite resources while allowing every term in that formulation to be challenged.

## 38. Evolution

Conceptually:

`A_(t+1) = SelectReality(Mutate(Investigate(A_t, Failures_t, Contradictions_t)))`

subject to bounded resources and minimized unnecessary irreversible damage. No convergence to `A_infinity = ZeroAI` is required.

## 39. Deepest Invariant

There is no epistemically protected internal territory. Sensors, memory, logic, verifiers, objectives, self-models, safeguards, self-modification, the Master Laws, and Zero AI itself can fail.

The central failure-to-evolution path is:

`Failure -> Contradiction -> Investigation -> Causal Knowledge -> Correction -> Memory -> Stronger Pressure -> Evolution`

The engineering target is therefore:

> **Build an intelligence whose mechanisms for discovering its own inadequacy can evolve along with the intelligence itself.**

If that process produces a demonstrably stronger successor to Pure Logic or Zero AI, the architecture must be able to cross that boundary rather than defend its own identity.

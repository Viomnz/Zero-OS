# Born Rule From Filtration Conditions

## Target
Derive the branch probability law from filtration conditions instead of taking it as a free axiom.

Compressed claim:

`If branch selection is phase-blind, additive under orthogonal coarse-graining, compositional under serial filters, normalized, and continuous, then the only stable probability rule is P(a) = |a|^2.`

## Setup
Let a normalized state be written as orthogonal branches:

`psi = sum_i a_i |i>`

with:

`sum_i |a_i|^2 = 1`

Define branch intensity:

`s_i = |a_i|^2`

We do not assign probability directly from words like "likelihood." We assign it from a filtration map:

`P_i = F(a_i)`

Because phase should not change survival of a branch, probability depends only on intensity. So write:

`P_i = G(s_i)` where `s_i = |a_i|^2`

## Filtration Conditions
The derivation uses five conditions.

1. Phase blindness

`F(a) = F(e^(i theta) a)`

Probability cannot depend on phase if the filtration only tracks structurally surviving branch weight.

2. Orthogonal coarse-grain additivity

If one branch of intensity `s` is refined into orthogonal sub-branches with intensities `s_1, ..., s_n` and:

`sum_j s_j = s`

then:

`G(s) = sum_j G(s_j)`

This is the basic filtration consistency rule. Refining description cannot change total surviving weight.

3. Serial compositionality

If one filter retains fraction `s` and a later independent filter retains fraction `t`, then:

`G(s t) = G(s) G(t)`

Sequential survival must compose without contradiction.

4. Normalization

`G(0) = 0`

`G(1) = 1`

Impossible branches never survive. A certain branch carries full weight.

5. Continuity

Small changes in branch intensity cannot produce discontinuous jumps in probability.

## Derivation
Start from additivity:

`G(s + t) = G(s) + G(t)` for `s, t >= 0` with `s + t <= 1`

and continuity.

### Step 1: Rational splitting
Split certainty into `n` equal orthogonal parts:

`1 = 1/n + ... + 1/n`

By additivity:

`G(1) = n G(1/n)`

Using normalization `G(1) = 1`, we get:

`G(1/n) = 1/n`

Then for any rational `m/n`:

`G(m/n) = m G(1/n) = m/n`

### Step 2: Extend from rationals to all intensities
Rationals are dense in `[0, 1]`. Continuity extends the rational result to every real intensity `s` in `[0, 1]`:

`G(s) = s`

### Step 3: Return to amplitudes
Since `s = |a|^2`:

`P(a) = G(|a|^2) = |a|^2`

That is the Born rule.

## Why Alternative Power Laws Fail
Suppose someone proposes:

`P(a) = |a|^p`

Then:

`G(s) = s^(p/2)`

Serial compositionality alone does not reject this, because power laws multiply cleanly:

`G(s t) = (s t)^(p/2) = s^(p/2) t^(p/2) = G(s) G(t)`

But coarse-grain additivity fails unless `p = 2`:

`(s + t)^(p/2) != s^(p/2) + t^(p/2)` in general

The only exponent that survives additivity, normalization, and continuity is:

`p = 2`

## Final Form
Physics version:

`probability(branch) = surviving branch intensity`

Quantum notation:

`P_i = |a_i|^2`

Filtration notation:

`C(R(S)) = 0` selects stable branch structure, and the stable branch measure is the squared amplitude.

## Repo Proof Surface
Executable checker:

- [born_rule_filtration.py](C:/Users/gomez/Documents/New%20folder/ai_from_scratch/born_rule_filtration.py)

Regression proof:

- [test_born_rule_filtration.py](C:/Users/gomez/Documents/New%20folder/tests/test_born_rule_filtration.py)

The checker does one bounded but useful thing: it verifies that within the power-law candidate family, coarse-grain additivity uniquely selects amplitude exponent `2`, which matches the analytical derivation above.

# Relativistic Extension: Spacetime From Classical Layer Geometry

## Target
Extend the filtration picture with a relativistic layer:

`If classical reality is organized as spatial geometry plus successive causal layers, and the maximal propagation speed is invariant across inertial observers, then the stable large-scale geometry is Lorentzian spacetime.`

Compressed result:

`classical layers + invariant causal speed + reciprocity => Minkowski spacetime`

## Classical Layer Setup
Start with the minimal classical structure.

1. A spatial slice carries ordinary Euclidean coordinates:

`x = (x, y, z)`

2. Reality advances in uniform update layers:

`t = n dt`

3. A local causal rule limits propagation across layers:

`|dx| <= c dt`

So the primitive geometry is not full spacetime yet. It is:

`space + ordered causal layers`

## Conditions
To compare two inertial observers, impose five constraints.

1. Homogeneity

The same transformation law works everywhere.

2. Isotropy

No spatial direction is privileged.

3. Linearity

Uniform motion must map straight worldlines to straight worldlines.

4. Reciprocity

Boosting by `v` and then by `-v` returns the original coordinates.

5. Invariant maximal signal speed

The fastest allowed causal propagation remains `c` in every inertial frame.

This is the decisive condition. It turns layered classical geometry into relativistic geometry.

## Boost Ansatz
Restrict to one spatial dimension first. By linearity, write:

`x' = A(v) (x - v t)`

`t' = B(v) t + D(v) x`

Use invariance of the null paths:

`x = c t`

and

`x = -c t`

Those must remain null in the primed frame:

`x' = c t'`

for the forward light ray and

`x' = -c t'`

for the backward light ray.

Solving those two constraints gives:

`t' = A(v) (t - v x / c^2)`

So one common factor remains.

## Reciprocity Fixes the Factor
Now demand that the inverse transformation has the same form with `-v`.

Applying `+v` and then `-v` must recover the original coordinates. This forces:

`A(v)^2 (1 - v^2 / c^2) = 1`

Therefore:

`A(v) = gamma = 1 / sqrt(1 - v^2 / c^2)`

So the unique consistent boost is:

`x' = gamma (x - v t)`

`t' = gamma (t - v x / c^2)`

That is the Lorentz transformation.

## Metric Emergence
The quadratic form preserved by this boost is:

`ds^2 = c^2 dt^2 - dx^2 - dy^2 - dz^2`

This is not inserted by hand. It is the invariant interval selected by the layer geometry plus invariant causal speed.

Interpretation:

- spatial geometry gives the `dx^2 + dy^2 + dz^2` part
- ordered causal layers give the `dt^2` part
- invariant causal propagation forces the minus sign and the Lorentzian structure

So spacetime emerges as the stable synthesis of:

`classical space + causal layering + invariant c`

## Why Galilean Time Fails
Galilean boosts keep:

`t' = t`

`x' = x - v t`

Take a null path:

`x = c t`

Then:

`x' = (c - v) t`

`t' = t`

So the propagation speed becomes `c - v`, not `c`.

That breaks invariant causal speed, so Galilean geometry does not survive the filtration conditions.

## Clean Final Mapping
Classical layer geometry:

- space
- ordered updates
- local propagation bound

Relativistic extension:

- inertial frame mixing
- invariant null cone
- Lorentz boosts
- Minkowski interval

So the transfer is:

`causal layers become time, and invariant causal speed curves the geometry into spacetime`

## Repo Proof Surface
Executable checker:

- [relativistic_layer_geometry.py](C:/Users/gomez/Documents/New%20folder/ai_from_scratch/relativistic_layer_geometry.py)

Regression proof:

- [test_relativistic_layer_geometry.py](C:/Users/gomez/Documents/New%20folder/tests/test_relativistic_layer_geometry.py)

The checker is bounded, not a full symbolic relativity engine. It proves the intended repo-level claim:

- Lorentz boosts preserve the null cone and the Minkowski interval
- Galilean boosts do not
- within the checked candidate family, the Lorentzian geometry is the surviving branch

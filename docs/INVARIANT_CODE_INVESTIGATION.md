# Invariant-Driven Code Investigation

Zero-OS should not equate textual coverage with behavioral understanding.

The investigation pipeline is:

`repository -> code reality graph -> invariants -> reachable violation paths -> findings -> independent finding certification -> independent coverage certification -> repair -> regression test`

## Core rule

Finding authority and analysis-scope authority are separate.

A discovered bug path may be genuine while the analysis still has incomplete coverage. Conversely, finding no path is not proof that no path exists.

## Code Reality Graph

Nodes may represent files, functions, classes, state, permissions, external dependencies, data sources, privileged sinks, and mutations.

Edges may represent calls, reads, writes, authenticates, authorizes, trusts, validates, mutates, executes, imports, dispatches, or runtime observations.

## Invariants

Examples:

- untrusted input cannot reach privileged execution without authorization
- one detector cannot grant quarantine authority
- failed mutation cannot leave partial privileged state
- LLM output cannot directly execute commands
- self-modification cannot increase its own authority
- evidence for one scope cannot authorize another scope

## Coverage dimensions

Textual scanning is not enough. Analysis may separately track syntax, call-path, data-flow, state-space, dependency, runtime, concurrency, permission, and security-property coverage.

Any unresolved dynamic dispatch, runtime hook, plugin path, reflection path, generated code, native boundary, or external dependency keeps the relevant coverage claim contested until separately demonstrated.

## Pure Logic status

All findings and coverage results begin non-authoritative. They become provisional only through independent scope certification. Internal confidence, number of files scanned, number of tests passed, or graph size cannot create authority by themselves.

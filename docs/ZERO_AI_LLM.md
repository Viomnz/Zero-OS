# Zero AI LLM Layer

Zero-OS may use an LLM as a high-bandwidth proposal and discovery engine. The LLM is not an authority source.

## Role

The LLM may generate:
- hypotheses
- alternative explanations
- candidate plans
- assumptions
- proposed tests
- requested scope

The LLM may not grant:
- truth authority
- scope authority
- safety authority
- production readiness
- identity authority
- mutation permission
- self-evolution promotion

## Pure Logic boundary

The required flow is:

`observations -> LLM proposal -> contradiction/falsification -> independent scope certification -> provisional authority -> bounded action -> post-action reality check`

The following flow is forbidden:

`LLM confidence or fluency -> authority`

Every LLM proposal has `authority = 0.0` and `authority_status = proposal_only`. Requested scope is a request for investigation, never demonstrated scope.

## Backends

Default backend: offline deterministic mock. This keeps tests and local operation independent from external model availability.

Optional backend: OpenAI Responses API. Configure:

- `ZERO_AI_LLM_BACKEND=openai`
- `OPENAI_API_KEY=...`
- optional `ZERO_AI_LLM_MODEL=...`

The model name is configuration, not architecture. Changing to a stronger model must not change its authority level.

## Six-law mapping

- Reality: LLM output is internal representation, not reality.
- Survival: proposals retain authority only after surviving independent pressure within demonstrated scope.
- Investigation: contradictions trigger tests and causal investigation rather than score averaging.
- Plurality: alternatives are preserved until evidence separates them.
- Path: the LLM may propose methods; action selection remains downstream and bounded.
- Resource: LLM calls are optional resources and should be used when information gain justifies their cost.

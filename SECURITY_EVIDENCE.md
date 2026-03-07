# Security Evidence (User/Client Witness)

## Evidence Scope
This document provides reproducible evidence for Zero OS security behavior **within this repository scope**.
It is not a claim of absolute real-world invulnerability.

## What Is Being Validated
- Triad security model:
  - Zero AI
  - Cure Firewall
  - Antivirus
- Built-in smart logic reasoning and governance:
  - `zero_ai_gate_smart_logic_v1`
  - `zero_ai_internal_smart_logic_v1`
  - `cure_firewall_smart_logic_v1`
  - `antivirus_smart_logic_v1`
- Recovery and hardening controls.

## Reproducible Commands
Run from repository root.

### 1. Adversarial Triad Stress + Security Suites
```powershell
python -m unittest -v tests.test_triad_adversarial_stress tests.test_quantum_virus_curefirewall tests.test_antivirus_system tests.test_internal_zero_reasoner tests.test_zero_ai_gate
```

### 2. Full Highway Security/Operations Routing
```powershell
python -m unittest -q tests.test_highway
```

### 3. Benchmark Stack (repeatable)
```powershell
python tools/benchmark_security_stack.py --preset medium --seed 1337
```

### 4. Maturity + Harmony + Security Profile
```powershell
python src/main.py "maturity status"
python src/main.py "zero ai harmony"
python src/main.py "zero ai security status"
```

## Generated Artifacts
- Benchmark artifacts:
  - `security/artifacts/security_benchmark.json`
  - `security/artifacts/security_benchmark.md`
- Runtime security/governance artifacts:
  - `.zero_os/runtime/smart_logic_policy.json`
  - `.zero_os/runtime/false_positive_review.jsonl`
  - `.zero_os/runtime/false_positive_decisions.jsonl`
  - `.zero_os/runtime/zero_ai_harmony.json`
  - `.zero_os/runtime/zero_ai_recovery_report.json` (after recovery run)

## Claim Language (Client-Safe)
Use:
- "Reproducible security evidence from adversarial simulations and deterministic test suites."
- "High codebase maturity and hardening controls in this repository scope."
- "Continuous verification via unit/integration/adversarial tests and benchmark artifacts."

Avoid:
- "100% secure"
- "Unhackable"
- "Guaranteed protection against all attacks"

## Current Positioning
- Codebase maturity can reach 100% by project-defined checks.
- Real-world security remains probabilistic; ongoing testing and operations are required.

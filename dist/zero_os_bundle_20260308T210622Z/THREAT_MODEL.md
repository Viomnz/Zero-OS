# Zero OS Threat Model

## Scope
This model covers local runtime, daemon processing, command execution, queue handling, and dashboard APIs.

## Assets
- Reasoning pipeline integrity
- Trusted baseline files
- Local signing keys and beacon integrity
- Runtime task queue and outputs
- System command and unified executor path

## Threat Classes
1. Malicious prompt injection
2. Queue flooding and duplicate spam
3. Unauthorized command escalation
4. Runtime state corruption
5. Trusted file tamper
6. Signal drift leading to unsafe decisions
7. Data growth denial by oversized logs

## Existing Controls
- Security integrity gate blocks known dangerous patterns
- Channel-aware authorization for restricted prefixes
- Core rule verification before reasoning
- Signal reliability checks and allow-execution gating
- Calibration and degradation detection
- Auto merge queue dedup
- AI files smart cleanup
- Integrity baseline restore for critical files
- Sandbox policy for command prefix allow and deny

## Residual Risks
- Unknown novel malicious prompt forms not in current patterns
- Misconfiguration of sandbox allow policy
- Local host compromise outside app scope
- False reject or false accept near threshold boundaries

## Risk Rating Approach
- High: can execute destructive operations or bypass integrity
- Medium: can degrade reliability, throughput, or data quality
- Low: cosmetic or non-critical behavior drift

## Detection and Response
1. Runtime logs in `.zero_os/runtime/zero_ai_output.txt`
2. Security events in `.zero_os/runtime/security_events.jsonl`
3. Health checks through `daemon_ctl.py health`
4. Trusted baseline rebuild through `daemon_ctl.py baseline`
5. Containment and restore via daemon integrity guard

## Hardening Backlog
1. Expand malicious pattern sets and fuzz tests
2. Add signed command policy snapshots
3. Add rate limits per source channel
4. Add dashboard auth option for shared environments
5. Add structured red-team test suite in CI


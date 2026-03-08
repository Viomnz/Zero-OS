# Top User Choice Plan (30/60/90)

## Mission
Make Zero OS the safest and easiest default for everyday users while keeping advanced power features.

## Pillars
1. Reliability first
2. Safe defaults by default
3. Fast/simple UX for non-technical users
4. Clear trust and recovery guarantees
5. Predictable zero-loss updates

## 30 Days (Stabilize)
- Reliability
  - Keep CI gate green on every PR.
  - Enforce blocker policy: no merge if security gates fail.
  - Track crash-free command execution rate in runtime telemetry.
- Safe defaults
  - `guarded` mode, `net strict`, `mark strict`, enterprise policy lock ON by default.
  - Keep shell/terminal/powershell deny rails unless explicitly approved.
- UX
  - Publish a minimal command set for new users (`status`, `fix all now`, `resilience status`).
  - Ensure all failure responses include one next command.
- Trust/recovery
  - Run immutable trust backup at least daily.
  - Verify trust recovery path weekly.
- Updates
  - Require pre-update snapshot and rollback record for each update apply.

Exit metrics:
- CI pass rate >= 99%
- No unrecoverable startup failures
- Mean Time to Recover from simulated incident <= 10 minutes

## 60 Days (Harden + Simplify)
- Reliability
  - Add long-run stress tests (overload, bot bursts, degraded network).
  - Add command success SLO by lane (system/web/api/shell).
- Safe defaults
  - Add high-risk action approval flow for non-owner roles.
  - Tighten critical action signature expiry windows.
- UX
  - Add beginner-safe command aliases and plain-language responses.
  - Add guided runbook command that prints incident steps.
- Trust/recovery
  - Add tamper-evident trust backup verification report.
  - Add restore drill automation and report artifact.
- Updates
  - Add canary apply + automatic rollback when health checks fail.

Exit metrics:
- Runtime command success >= 99.5% on stable paths
- False-positive quarantine on source paths = 0
- Recovery drill success >= 99%

## 90 Days (Scale + Confidence)
- Reliability
  - Publish weekly reliability report with trend lines.
  - Add chaos scenarios (disk pressure, process churn, network outage).
- Safe defaults
  - Integrate optional external EDR/SIEM/IAM health checks into failover policy.
  - Add immutable audit export in every release checklist.
- UX
  - One-command health check for non-technical users.
  - Improve dashboard with top 3 actions and risk summary.
- Trust/recovery
  - Cross-copy immutable trust backup to secondary location profile.
  - Signed restore verification artifact after each recovery.
- Updates
  - Deterministic release channel policy (`stable`, `canary`) with rollback SLA.

Exit metrics:
- User incident resolution without manual file edits >= 95%
- Zero data-loss in update rollback drills
- External integration outage failover validated weekly

## Non-negotiables
- Never disable baseline safeguards by default.
- Never apply updates without snapshot + rollback path.
- Never quarantine critical runtime source paths automatically.
- Always provide a deterministic recovery command.

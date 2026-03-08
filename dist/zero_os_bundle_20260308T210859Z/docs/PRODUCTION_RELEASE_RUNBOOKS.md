# Production Release Runbooks

## Scope

This runbook covers native packaging, backend deployment, incident response, rollback, secrets, certificates, and abuse/failure testing for the Zero runtime ecosystem.

## Release Flow

1. Run `native store release prepare version=<v> channel=<stable|beta|canary>`.
2. Verify rollback checkpoint exists:
   - `native store rollback checkpoint name=pre-<v>`
3. Build native artifacts:
   - `native store build windows app=ZeroStore version=<v>`
   - `native store build linux app=ZeroStore version=<v>`
   - `native store build macos app=ZeroStore version=<v>`
   - `native store build mobile app=ZeroStore version=<v>`
4. Verify CI artifact uploads for Windows, Linux, and macOS jobs.
5. Rotate certificates or signing identities if required:
   - `native store cert rotate name=<new-cert>`
6. Update secrets only through managed command paths:
   - `native store secret set name=<name> value=<value>`
7. Run stress validation:
   - `native store stress test traffic=1000 abuse=200 failures=40`
8. Review backend health:
   - `native store backend status`

## Backend Ops

- Initialize DB: `native store backend init`
- Issue scoped token: `native store backend token issue id=<id> scope=<scope>`
- Create user: `native store backend user create id=<id> email=<email> tier=<tier>`
- Charge payment: `native store backend charge id=<id> user=<user> amount=<n> currency=<code>`
- Record auditable event: `native store backend event kind=<name> json=<json>`

## Desktop Client Ops

- Generate shell: `native store desktop scaffold`
- Generate production packaging metadata: `native store desktop package app=<name> version=<v>`
- Validate updater, install service manifest, OS registration, and crash reporter outputs under `build/native_store_prod/desktop_production/`

## Incident Handling

1. Open incident:
   - `native store incident open severity=<sev> summary=<text>`
2. Contain blast radius:
   - disable affected channel
   - restore previous rollback checkpoint
   - revoke active token/certificate if compromise suspected
3. Restore service:
   - `native store rollback restore name=<checkpoint>`
4. Capture postmortem artifacts:
   - stress report
   - CI artifacts
   - backend event log

## Failure and Abuse Testing

- Run overload/abuse/failure simulation:
  - `native store stress test traffic=<n> abuse=<n> failures=<n>`
- Review generated report under `.zero_os/native_store/ops/stress_report.json`
- Gate release on acceptable drop rate and recovery target

## Rollback Rules

- Every release candidate needs a named checkpoint before packaging
- Roll back immediately on signing failure, package corruption, or install regression
- Do not rotate secrets/certs during an active unresolved incident without recording the action in incident notes

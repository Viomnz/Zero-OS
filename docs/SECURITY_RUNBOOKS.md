# Security Runbooks

## Incident Triage (High/Critical)
1. Run `enterprise security status`
2. Run `zero ai agent monitor triad balance`
3. Run `antivirus status`
4. If critical findings exist, run `antivirus agent run . auto_quarantine=true`
5. Verify: `antivirus quarantine list`
6. Run integrity checks: `cure firewall agent run pressure 90`
7. If integrity drift is detected, restore affected files:
   - `cure firewall restore <path>`
   - or `antivirus restore <id>`
8. Emit SOC event: `enterprise siem emit critical incident-active`

## Ransomware Response
1. `enterprise rollback run ransomware`
2. `self repair run`
3. `triad balance run`
4. `enterprise siem emit critical ransomware-response-complete`

## Policy Hardening Lock
1. `enterprise policy lock apply`
2. `security harden apply`
3. `enterprise rollout set prod`
4. Confirm: `enterprise rollout status`

## External Integration Bring-up
1. SIEM:
   - `enterprise integration set siem on provider=<name> endpoint=<webhook>`
   - `enterprise integration probe siem`
2. IAM:
   - `enterprise integration set iam on provider=<name> endpoint=<tenant_or_api>`
   - `enterprise integration probe iam`
3. EDR:
   - `enterprise integration set edr on provider=<name> endpoint=<api>`
   - `enterprise integration probe edr`
4. Zero Trust:
   - `enterprise integration set zerotrust on provider=<name> endpoint=<policy_url>`
   - `enterprise integration probe zerotrust`

## Adversarial Validation Gate
1. Local gate: `python tools/security_gate.py`
2. CI gate: `.github/workflows/ci.yml` automatically runs gate on PR/push.

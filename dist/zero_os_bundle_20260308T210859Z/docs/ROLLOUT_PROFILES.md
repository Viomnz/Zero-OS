# Controlled Rollout Profiles

Profiles are defined in `zero_os_config/security_rollout_profiles.json`.

## Environments
- `dev`: enterprise controls mostly permissive for development velocity.
- `stage`: hardened behavior with broader auto-containment.
- `prod`: strictest containment and signed-action requirements.

## Apply Flow
1. `enterprise rollout set <dev|stage|prod>`
2. `enterprise policy lock apply`
3. `security harden apply`
4. `enterprise security status`

## Verification
- `enterprise integration status`
- `enterprise validate adversarial`
- `python tools/security_gate.py`

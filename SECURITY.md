# Zero OS Security Policy

## Scope
This project is open source by design.
Code is public.
Runtime trust material is private.

## Private Data Rules
Never commit these paths:
- `.zero_os/keys/`
- `.zero_os/runtime/`
- `.zero_os/quarantine/`
- `.zero_os/backup/`
- `.zero_os/audit.log`
- `.zero_os/revocations.json`
- `.zero_os/net_policy.json`
- `.env` and `.env.*`

These files contain signing keys, runtime state, integrity baselines, event chains, quarantine evidence, or local policy.

## Trust Model
- Source code is reviewable by everyone.
- Trust decisions are local and signed.
- Reputation entries use signatures.
- Cure Firewall beacons use signatures.
- Integrity baselines are generated locally.

## Security Modes
- `strict_reputation_mode=0`:
  monitor mode.
  Unknown files produce alerts but do not hard-stop by reputation alone.
- `strict_reputation_mode=1`:
  enforcement mode.
  Unknown or low-reputation files escalate to high severity and can trigger containment.

## Recommended Operator Flow
1. Pull latest code.
2. Run tests.
3. Rebuild baseline: `python ai_from_scratch/daemon_ctl.py baseline`.
4. Run security report: `python ai_from_scratch/daemon_ctl.py security`.
5. Trust approved files with score:
   `python ai_from_scratch/daemon_ctl.py trust-file --file <path> --score 80 --level trusted --note "reviewed"`
6. Start daemon only after health and security are acceptable.

## Reporting Security Issues
If you find a vulnerability:
1. Do not publish exploit details immediately.
2. Share a minimal reproducible report with:
   - affected file/path
   - impact
   - reproduction steps
   - suggested fix
3. Wait for a patch window before public disclosure.

## Non-Goals
- No claim of perfect security.
- No external cloud dependency required for core local protection.
- No offensive behavior in security core.

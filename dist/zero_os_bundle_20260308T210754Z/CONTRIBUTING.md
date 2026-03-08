# Contributing to Zero-OS

## Rules Before Opening a Pull Request
You must run both checks locally and include results in your PR description.

1. Run tests:
```powershell
python -m unittest discover -s tests -p "test_*.py"
```

2. Run security gate:
```powershell
.\zero_os_launcher.ps1 security-agent
```

PRs that skip tests or security-agent are not accepted.

## Required PR Checklist
- [ ] Tests pass
- [ ] Security report reviewed
- [ ] No keys or runtime artifacts committed
- [ ] If policy changed, explain why
- [ ] If security core changed, include risk notes

## Never Commit
- `.zero_os/keys/*`
- `.zero_os/runtime/*`
- `.zero_os/quarantine/*`
- `.zero_os/backup/*`
- `.env` and `.env.*`

## Recommended Flow
1. Pull latest.
2. Make focused changes.
3. Run tests.
4. Run security-agent.
5. Open PR with outputs and summary.

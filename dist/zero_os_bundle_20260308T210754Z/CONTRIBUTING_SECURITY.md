# Contributing Security Guide

## Purpose
This file defines safe extension rules for contributors working on Zero OS security-critical paths.

## Security-Critical Paths
- `ai_from_scratch/daemon.py`
- `ai_from_scratch/daemon_ctl.py`
- `ai_from_scratch/security_integrity_layer.py`
- `ai_from_scratch/internal_zero_reasoner.py`
- `src/zero_os/capabilities/system.py`
- `src/zero_os/production_core.py`
- `src/zero_os/cure_firewall.py`

Changes in these files require tests and explicit risk notes in PR.

## Required Before PR
1. Run tests:
```powershell
python -m unittest discover -s tests -p "test_*.py"
```
2. Run daemon health:
```powershell
python ai_from_scratch/daemon_ctl.py health
```
3. Run security report:
```powershell
python ai_from_scratch/daemon_ctl.py security
```

## Guarded File Rule
When editing guarded files while daemon is active:
1. Stop daemon
2. Apply edits
3. Run tests
4. Rebuild baseline

Commands:
```powershell
python ai_from_scratch/daemon_ctl.py stop
python -m unittest discover -s tests -p "test_*.py"
python ai_from_scratch/daemon_ctl.py baseline
```

## Safe Extension Rules
1. Keep all command execution paths behind sandbox checks.
2. Do not bypass security integrity gate for prompt processing.
3. Do not disable baseline integrity checks.
4. Keep new APIs local by default.
5. Add tests for every new security-facing command or layer.

## Never Commit
- `.zero_os/keys/*`
- `.zero_os/runtime/*`
- `.zero_os/quarantine/*`
- `.zero_os/backup/*`
- `.env` and `.env.*`

## PR Security Notes Template
Include this section in PR body:
- Threat class addressed
- New controls introduced
- Known tradeoffs
- Test evidence
- Rollback plan


# Zero OS implementation foundation

Use the current PDF identified by `publication/pure_logic_source.json` when
changing reasoning, authority, verification, memory, planning, or execution.
`PURE_LOGIC.md` is the implementation contract; `docs/PURE_LOGIC_ALIGNMENT.md`
maps the PDF to implemented behavior and remaining gaps. Earlier PDFs and open
pull requests are historical/proposed work, not evidence of deployed behavior.

Preserve the six Master Laws and the hierarchy Reality -> Pure Logic -> Six
Master Laws -> Zero AI -> implementations. Framework authority remains provisional.
Do not promote discovery confidence, internal consistency, a score of 100, or
agreement among dependent verifiers into scope or execution authority.

For relevant changes, cite PDF section numbers in the change description,
update the alignment record if behavior changes, and run:

```
python -m pytest -q tests/test_pure_logic_authority.py tests/test_pure_logic_execution.py tests/test_pure_logic_source.py tests/test_zero_engine.py
```

Also follow `CONTRIBUTING.md`. On systems without PowerShell, its security-agent
command is `python ai_from_scratch/daemon_ctl.py security`, the same underlying
command called by `Daemon-Security` in `zero_os_launcher.ps1`.

Never describe missing integration or simulated evidence as a complete native
implementation. Preserve failures and the scope of each validation result.

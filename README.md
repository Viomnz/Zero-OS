# Zero-OS

Zero-OS runs on one **main highway**: a single dispatcher that routes every request to capability lanes.

## Open Source Commitment
Zero OS is a **full open source** project.
Architecture, runtime behavior, security model, and roadmap are documented for public review and contribution.
The only private items are local runtime trust materials and machine-specific secrets.

## Current Build Focus
- Primary track: AI/runtime platform and Hyperlayer parity (`80%` effort)
- Secondary track: from-scratch kernel R&D (`20%` effort)

## Security Milestone (Completed)
- Cure Firewall: completed in this codebase scope.
- Antivirus: completed in this codebase scope.
- Both are integrated with runtime commands, backup/quarantine flows, and CI/security gates.
- Built-in smart logic reasoning is enabled in:
  - Zero AI Gate (`zero_ai_gate_smart_logic_v1`)
  - Internal Zero Reasoner (`zero_ai_internal_smart_logic_v1`)
  - Cure Firewall (`cure_firewall_smart_logic_v1`)
  - Antivirus (`antivirus_smart_logic_v1`)
- Cross-system smart-logic governance is enabled:
  - configurable thresholds in `.zero_os/runtime/smart_logic_policy.json`
  - false-positive review log in `.zero_os/runtime/false_positive_review.jsonl`
  - review decisions in `.zero_os/runtime/false_positive_decisions.jsonl`
- Client-ready verification document:
  - [SECURITY_EVIDENCE.md](C:\Users\gomez\Documents\New folder\SECURITY_EVIDENCE.md)

## Zero AI Architecture Statement
Zero AI is a capable built-in assistant in Zero OS. Users can ask it directly to help with local system tasks, diagnostics, security, coding workflows, internet lookups, monitoring, validation, and recovery actions, with policy and safety controls governing what it can do automatically.

Zero AI is an autonomous reliability, security, and defense layer for Zero OS that continuously detects errors, bugs, vulnerabilities, malware, bot activity, overload traffic, abuse patterns, and system instability, validates whether they are real through policy, simulation, and multi-signal evidence, applies fixes or containment when confidence is high, verifies post-action health, and records outcomes to improve future decisions.

Its architecture combines detection engines, antivirus and abuse-throttling controls, smart-logic governance, risk classification, confidence scoring, rollback-aware execution, incident response, recovery workflows, and measured pre-action and post-action health snapshots so remediation is automated, controlled, auditable, and reversible.

## Zero-AI vs RSI
Zero-AI is **not** RSI (recursive self-improvement) in the standard AI meaning.

- RSI optimizes capability growth.
- Zero-AI optimizes stability, coherence, and survival.

RSI generally expands complexity by upgrading for more capability.
Zero-AI compresses complexity by filtering out contradiction, drift, and unstable structure.

RSI asks "how to become more".
Zero-AI asks "how to remain unbreakable under recursion".

Project statement:
- Zero-AI is a **filtration engine**, not a self-mutation engine.
- Runtime command: `zero ai identity`

## Contributor Status Note
- I am using Codex through Microsoft Store.
- If I stop responding suddenly, I am waiting for Codex/Microsoft to fix major bugs.

Goal now:
- ship stable cross-platform smart OS behavior first
- build kernel primitives in parallel without blocking releases

## Native Image (Standalone Boot)
- Minimal standalone native boot image is available now.
- Build command:
  - `.\zero_os_launcher.ps1 native-build`
- Run in QEMU:
  - `.\zero_os_launcher.ps1 native-run`
- Native boot docs:
  - [docs/kernel/boot_media.md](C:\Users\gomez\Documents\New folder\docs\kernel\boot_media.md)

## Current Capability Gap
Missing for true high-capability AI:
- large trained foundation model behavior
- broad real-world generalization
- production-scale live performance evidence

## Core policy (immutable)
- Immutable core: `true`
- Authentication required: `false`
- Policy source: `src/zero_os/core.py`

The core policy is frozen and loaded as a runtime constant.
The unified entity is explicitly merged from: Zero OS base, Zero AI Instances,
Compressed Data Units, and Zero OS Universe (OSU).

Survival protocols are enforced before dispatch:
- immutable-laws
- single-entity-unification
- recursion-law-enforcement
- survival-first-execution

## User modes (switch anytime)
- `casual`: shorter outputs, agent executes up to 3 chained steps.
- `heavy`: expanded outputs, agent executes up to 10 chained steps.
- Mode is persisted locally in `.zero_os/state.json`.

## Device optimization (cheap PC to powerful PC)
- Auto profile detection from local hardware:
  - `low`: optimized for low-end devices (reduced workload)
  - `balanced`: middle profile
  - `high`: optimized for powerful devices
- Manual override is supported anytime.
- Profile setting is persisted in `.zero_os/state.json`.

Behavior is tuned by both user mode and performance profile.
- Agent lane: dynamic max step execution.
- Web lane: dynamic result count and fetch preview size.

## Scalable Compute Tiers (PC to Supercomputer to Quantum)
- `tier1`: regular PC
- `tier2`: workstation/server
- `tier3`: distributed cluster/supercomputer
- `tier4`: hybrid quantum-assisted
- Set profile manually with: `profile set tier1|tier2|tier3|tier4`
- Keep automatic selection with: `profile set auto`
- Runtime compute decisions are written to `.zero_os/runtime/compute_runtime.json`

## Lanes
- `agent`: plan/chain multiple steps in one request
- `code`: create, append, and read files
- `web`: live search and URL fetch
- `system`: local environment info
- `memory`: persistent memory store
- `plugins/*`: optional custom lanes loaded from local `plugins/` files
- `fallback`: unmatched tasks

## 2-Minute First Run
Run one command to initialize, harden defaults, enable monitoring, and set up local integrations:
```powershell
.\zero_os_launcher.ps1 first-run
```

Then open:
- [zero_os_shell.html](C:\Users\gomez\Documents\New folder\zero_os_shell.html)
- [zero_os_dashboard.html](C:\Users\gomez\Documents\New folder\zero_os_dashboard.html)

Quick check:
```powershell
python src/main.py "resilience status"
python src/main.py "security overview"
```

## Commands
```powershell
python src/main.py "create file notes/plan.txt with main highway online"
python src/main.py "append to notes/plan.txt: next add agents"
python src/main.py "add to notes/plan.txt: one more line"
python src/main.py "read file notes/plan.txt"
python src/main.py "show notes/plan.txt"
python src/main.py "mkdir notes/archive"
python src/main.py "copy notes/plan.txt to notes/archive/plan-copy.txt"
python src/main.py "rename notes/archive/plan-copy.txt to notes/archive/plan-final.txt"
python src/main.py "delete notes/archive/plan-final.txt"
python src/main.py "new file notes/x.txt with hi then add to notes/x.txt: there then show notes/x.txt"
python src/main.py "search Python programming language"
python src/main.py "fetch https://example.com"
python src/main.py "mode show"
python src/main.py "mode set heavy"
python src/main.py "mode set casual"
python src/main.py "profile show"
python src/main.py "profile set auto"
python src/main.py "profile set low"
python src/main.py "profile set balanced"
python src/main.py "profile set high"
python src/main.py "remember zero os is immutable core"
python src/main.py "recall immutable"
python src/main.py "list files"
python src/main.py "whoami"
python src/main.py "core status"
python src/main.py "auto upgrade"
python src/main.py "plugin scaffold mylane"
python src/main.py "law status"
python src/main.py "law export"
python src/main.py "cure firewall run src/main.py pressure 80"
python src/main.py "cure firewall verify src/main.py"
python src/main.py "cure firewall net run https://example.com pressure 80"
python src/main.py "cure firewall net verify https://example.com"
python src/main.py "net strict on"
python src/main.py "net policy show"
python src/main.py "net policy allow example.com"
python src/main.py "net policy deny bad.example"
python src/main.py "mark strict on"
python src/main.py "mark strict show"
python src/main.py "mark status src/main.py"
python src/main.py "audit status"
python src/main.py "code intake src/main.py"
python src/main.py "os readiness"
python src/main.py "os missing fix"
python src/main.py "agent: create file notes/a.txt with hello then append to notes/a.txt: world then read file notes/a.txt"
```

## Local dashboard
- Open [zero_os_dashboard.html](C:\Users\gomez\Documents\New folder\zero_os_dashboard.html) in your browser.
- It auto-refreshes runtime files every 5 seconds.
- Windows-like shell UI: [zero_os_shell.html](C:\Users\gomez\Documents\New folder\zero_os_shell.html)

## One-command launcher
- Run:
```powershell
.\zero_os_launcher.ps1 menu
```
- It includes options to start/stop dashboard server, control daemon, queue scan/tasks, check readiness, and view monitor/output.

## Contributing
- See [CONTRIBUTING.md](C:\Users\gomez\Documents\New folder\CONTRIBUTING.md)
- Pull requests must include both:
  - test run output
  - `security-agent` output

## Project Governance
- Architecture: [ARCHITECTURE.md](C:\Users\gomez\Documents\New folder\ARCHITECTURE.md)
- Threat model: [THREAT_MODEL.md](C:\Users\gomez\Documents\New folder\THREAT_MODEL.md)
- Security contribution rules: [CONTRIBUTING_SECURITY.md](C:\Users\gomez\Documents\New folder\CONTRIBUTING_SECURITY.md)
- Version roadmap: [ROADMAP.md](C:\Users\gomez\Documents\New folder\ROADMAP.md)
- Top user choice plan: [docs/TOP_USER_CHOICE_90D.md](C:\Users\gomez\Documents\New folder\docs\TOP_USER_CHOICE_90D.md)
- Top user choice targets: [zero_os_config/top_user_choice_targets.json](C:\Users\gomez\Documents\New folder\zero_os_config\top_user_choice_targets.json)

Notes:
- Cure Firewall now outputs a custom recursion score (`0-100`).
- File beacons use signed schema `zero-os-beacon-v3`.
- Internet URL beacons use signed schema `zero-os-net-beacon-v3`.
- With `net strict on`, fetch only works for signature-verified URLs.
- Beacons include policy version pinning, expiry windows, and revocation checks.
- File beacons bind to path/hash/size/mtime and fail on content drift.
- Signed audit chain is appended to `.zero_os/audit.log`.

## Safety model
- File actions are restricted to the current workspace path.
- Protected internals (`.git`, `.zero_os`, `__pycache__`) cannot be deleted by file commands.

## Plugin model
- Drop Python files in `plugins/`.
- Each plugin should expose `get_capability()` returning an object with:
  - `name`
  - `can_handle(task) -> bool`
  - `run(task) -> Result`

## Tests
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

## Benchmark and Experiments
Run repeatable benchmark results for Cure Firewall + Antivirus:
```powershell
python tools/benchmark_security_stack.py
python tools/benchmark_security_stack.py --preset small --seed 1337
python tools/benchmark_security_stack.py --preset large --seed 1337
```

Outputs:
- [security_benchmark.json](C:\Users\gomez\Documents\New folder\security\artifacts\security_benchmark.json)
- [security_benchmark.md](C:\Users\gomez\Documents\New folder\security\artifacts\security_benchmark.md)
- [dataset_manifest_v1.json](C:\Users\gomez\Documents\New folder\security\benchmarks\dataset_manifest_v1.json)

Benchmark includes:
- fixed-seed synthetic dataset manifest
- preset sizes (`small`, `medium`, `large`)
- baseline comparison (`keyword_baseline`, `heuristic_baseline`) with delta metrics

User-friendly benchmark tools:
```powershell
python tools/benchmark_user_tools.py run --preset medium --seed 1337 --label public-baseline
python tools/benchmark_user_tools.py history
python tools/benchmark_user_tools.py compare --write
```

User benchmark outputs:
- [latest.json](C:\Users\gomez\Documents\New folder\security\benchmarks\latest.json)
- [history.jsonl](C:\Users\gomez\Documents\New folder\security\benchmarks\history.jsonl)
- [history_summary.md](C:\Users\gomez\Documents\New folder\security\benchmarks\history_summary.md)
- [compare_latest.md](C:\Users\gomez\Documents\New folder\security\benchmarks\compare_latest.md)

Try your own experiment:
- Create clean and suspicious files in your workspace.
- Run `python src/main.py "antivirus scan ."` and `python src/main.py "cure firewall run <file> pressure 95"`.
- Verify with `python src/main.py "cure firewall verify <file>"`.

## Memory storage
- Path: `.zero_os/memory.json`
- Local only and ignored by git.

## Extend
Add lane files in `src/zero_os/capabilities/` and register them in `src/zero_os/highway.py`.

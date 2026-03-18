# Zero-OS

Zero-OS is an experimental open-source platform that combines a local OS-style control surface, a built-in assistant called Zero AI, security tooling, packaging flows, and a Windows-native shell.

[![UI Cross-Platform Smoke](https://github.com/Viomnz/Zero-OS/actions/workflows/ui-cross-platform-smoke.yml/badge.svg)](https://github.com/Viomnz/Zero-OS/actions/workflows/ui-cross-platform-smoke.yml)
[GitHub Releases](https://github.com/Viomnz/Zero-OS/releases)

## At A Glance
- What it is: a local-first Zero OS platform with a web shell, a Windows native shell, Zero AI, security tools, GitHub intake flows, bundle/export tools, and experimental native boot work.
- What works now: the web shell, the Windows native shell, repo quickstart launchers, Zero AI runtime commands, security tooling, bundle/share packaging, CI checks, and GitHub issue/PR intake flows.
- What is experimental: the standalone native OS/kernel path, some self-management and continuity systems, large-scale indexing features, the native app store production scaffolds, and production-grade installer/signing delivery.
- How to run it: on Windows, download the native app from Releases or run the repo quickstart `.cmd`. On any platform with Python, run `python zero_os_quickstart.py`.
- Supported platforms: Windows is the main supported path. macOS and Linux have a smoke-tested launcher and web-shell path, but broader validation is still planned.
- How mature it is: substantial and usable for local workflows, demos, and development, but still pre-1.0 and not a finished consumer OS or a fully productized standalone kernel.

## Quick Start
GitHub users should not need to learn Zero OS commands first.

[Download Native App](https://github.com/Viomnz/Zero-OS/releases)

Fastest ways to start:
1. Windows easiest path: download the native app or portable package from Releases
2. Windows from the repo: double-click `Zero OS QuickStart.cmd`
3. Any OS with Python: run `python zero_os_quickstart.py`
4. macOS or Linux shell: run `./zero_os_quickstart.sh`
5. macOS Finder: double-click `Zero OS QuickStart.command`

What QuickStart does:
1. runs first-run setup
2. opens the best available UI
3. lets you use built-in buttons instead of memorizing commands

Important:
- the git repo includes the `.cmd`, `.command`, `.py`, and `.sh` launchers
- prebuilt Windows `.exe` binaries come from GitHub Releases, not from a fresh clone

Manual setup if you want the explicit steps:
1. Clone or download Zero OS
2. Run `.\zero_os_launcher.ps1 first-run`
3. Open the UI with `python zero_os_ui.py` or `Start-Process ".\zero_os_shell.html"`
4. Use the built-in buttons like `Know Everything` and `Know Everything + Complete All`

```powershell
git clone https://github.com/Viomnz/Zero-OS.git
cd Zero-OS
.\zero_os_launcher.ps1 first-run
python zero_os_ui.py
```

Cross-platform QuickStart commands:

```powershell
python zero_os_quickstart.py
```

```sh
./zero_os_quickstart.sh
```

```sh
make quickstart
```

Cross-platform UI launch if setup is already done:

```powershell
python zero_os_ui.py
```

Or with `make`:

```sh
make ui
```

On macOS or Linux:

```sh
chmod +x ./zero_os_ui.sh
./zero_os_ui.sh
```

UI behavior by platform:
- Windows: launches the Zero OS native desktop UI
- macOS/Linux: launches the Zero OS web shell with the local shell bridge
- Web fallback: opens the guided Start Here flow first

GitHub Actions also smoke-tests this universal UI path on Windows, macOS, and Linux.

## Prerequisites
- End users from source: Python 3.11+ on x64
- End users from Releases: no source build required for the Windows native app path
- Optional convenience tooling: `make` for shortcut commands on systems that have it
- Native shell contributors on Windows: .NET SDK 8+ compatible with `net8.0-windows`
- Native packaging contributors on Windows: Windows SDK `makeappx`, WiX tooling, and a signing certificate for signed MSIX output

## Validation Scope
- Cross-platform UI smoke is automated on Windows, macOS, and Linux in [ui-cross-platform-smoke.yml](C:\Users\gomez\Documents\New folder\.github\workflows\ui-cross-platform-smoke.yml)
- Core CI gates currently run on Windows in [ci.yml](C:\Users\gomez\Documents\New folder\.github\workflows\ci.yml)
- Windows native shell build, publish, portable packaging, and MSIX packaging run in [native-shell-windows.yml](C:\Users\gomez\Documents\New folder\.github\workflows\native-shell-windows.yml)
- Native store Windows packaging smoke also runs in [ci.yml](C:\Users\gomez\Documents\New folder\.github\workflows\ci.yml)
- macOS and Linux launcher/web-shell paths are smoke-tested, but not yet validated to Windows-level depth

## Major Subsystems
- Web shell: [zero_os_shell.html](C:\Users\gomez\Documents\New folder\zero_os_shell.html)
- Windows native shell: [native_ui/ZeroOS.NativeShell](C:\Users\gomez\Documents\New folder\native_ui\ZeroOS.NativeShell)
- Zero AI runtime and continuity systems: [src/zero_os](C:\Users\gomez\Documents\New folder\src\zero_os)
- Security stack, including Cure Firewall and Antivirus: [SECURITY.md](C:\Users\gomez\Documents\New folder\SECURITY.md)
- Native boot and kernel R&D: [docs/kernel/README.md](C:\Users\gomez\Documents\New folder\docs\kernel\README.md)
- Native app store and multi-OS packaging scaffolds: [docs/NATIVE_APP_STORE.md](C:\Users\gomez\Documents\New folder\docs\NATIVE_APP_STORE.md)
- AI-from-scratch baseline stack: [ai_from_scratch/README.md](C:\Users\gomez\Documents\New folder\ai_from_scratch\README.md)

## Read Next
- Architecture: [ARCHITECTURE.md](C:\Users\gomez\Documents\New folder\ARCHITECTURE.md)
- Threat model: [THREAT_MODEL.md](C:\Users\gomez\Documents\New folder\THREAT_MODEL.md)
- Security policy: [SECURITY.md](C:\Users\gomez\Documents\New folder\SECURITY.md)
- Compatibility matrix: [docs/COMPATIBILITY_MATRIX.md](C:\Users\gomez\Documents\New folder\docs\COMPATIBILITY_MATRIX.md)
- Kernel R&D overview: [docs/kernel/README.md](C:\Users\gomez\Documents\New folder\docs\kernel\README.md)
- Physics derivation note: [docs/physics/born_rule_from_filtration.md](C:\Users\gomez\Documents\New folder\docs\physics\born_rule_from_filtration.md)
- Relativistic extension note: [docs/physics/spacetime_from_classical_layer_geometry.md](C:\Users\gomez\Documents\New folder\docs\physics\spacetime_from_classical_layer_geometry.md)
- Native app store subsystem: [docs/NATIVE_APP_STORE.md](C:\Users\gomez\Documents\New folder\docs\NATIVE_APP_STORE.md)
- Roadmap: [ROADMAP.md](C:\Users\gomez\Documents\New folder\ROADMAP.md)
- Contributing: [CONTRIBUTING.md](C:\Users\gomez\Documents\New folder\CONTRIBUTING.md)

If you want the local dashboard server too:

```powershell
.\zero_os_launcher.ps1 open-dashboard
.\zero_os_launcher.ps1 start-shell-bridge
```

Fast checks:

```powershell
python src/main.py "core status"
python src/main.py "security overview"
python src/main.py "github status"
```

Cross-platform shortcuts with `make`:

```sh
make core
make security
make github
make bundle
make share
make release
```

## What Works Today
- Windows native shell with quickstart, file browsing, search, editing, packaging controls, and Zero AI runtime actions
- Cross-platform web shell with guided start pages, GitHub helpers, output viewer, saved files, and in-shell file viewing
- Zero AI continuity, inspection, repair, governor, and simulation flows
- Security tooling including Cure Firewall and Antivirus inside this codebase scope
- Bundle/export/share flows for Zero OS and Zero AI
- GitHub issue and pull request intake, planning, and draft-reply flows
- Cross-platform launcher and quickstart paths
- Native app store scaffolds, backend scaffolds, and packaging metadata for multiple operating systems

## What Is Still Experimental
- Standalone native boot and kernel work
- Some large-scale indexing and watcher workflows
- Installer signing and full production release delivery
- Several advanced Zero AI autonomy and continuity systems
- Native app store production deployment and vendor integration
- Overall product polish beyond the current developer/power-user stage

## Platforms
- Windows: best-supported experience, including the native shell and beginner launchers
- macOS: smoke-tested launcher and web-shell path, broader validation still planned
- Linux: smoke-tested launcher and web-shell path, broader validation still planned
- Standalone native image: available for R&D and testing, not the main supported user path yet

## Maturity
- UI layer: usable now
- Developer workflow layer: usable now
- Zero AI local tooling layer: substantial but still evolving
- Security/tooling layer: strong in repo scope
- Native app store layer: scaffolded and progressing, not production-ready
- Native standalone OS layer: experimental
- Overall project state: ambitious, working, and real, but not finished

## Get Zero OS
Best ways for GitHub users to copy Zero OS:
- `git clone https://github.com/Viomnz/Zero-OS.git`
- download the repo zip from GitHub Releases or the repository page
- download the ready-made native app or release bundle from GitHub Releases
- run `.\zero_os_launcher.ps1 first-run`
- open the UI and use the built-in buttons

If you want to create a clean shareable local copy from this repo, use:

```powershell
python src/main.py "zero os export bundle"
python src/main.py "zero os share package"
```

Those commands generate a sanitized export under `dist/` without local runtime secrets.

## Release For GitHub Users
To publish an easy download for GitHub users:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

For Windows users who do not want to build anything locally, the native release flow now produces:
- a published native shell build
- a portable installer zip with launchers and onboarding docs
- an MSIX package for Windows-native installation

You can also build that package locally:

```powershell
powershell -ExecutionPolicy Bypass -File .\native_ui\ZeroOS.NativeShell\publish.ps1
powershell -ExecutionPolicy Bypass -File .\native_ui\ZeroOS.NativeShell\package_msix.ps1
powershell -ExecutionPolicy Bypass -File .\native_ui\ZeroOS.NativeShell\package_portable.ps1
```

That triggers the release workflow in [release-share-bundle.yml](C:\Users\gomez\Documents\New folder\.github\workflows\release-share-bundle.yml), which:
- builds `zero os share package`
- creates a `zero_os_bundle_*.zip`
- uploads it to the GitHub Release page

So users can either:
- clone the repo
- download the repository zip
- or download the ready-made release bundle zip

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
- RSI is a **second-layer eye** for Zero-AI: it observes opportunities for refinement and capability growth, while Zero-AI remains the governing intelligence responsible for stability, coherence, and survival.
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
- or run `.\zero_os_launcher.ps1 open-dashboard` for the optional local dashboard server

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
- Optional dashboard server command:
```powershell
.\zero_os_launcher.ps1 open-dashboard
```
- Dashboard server URL: `http://127.0.0.1:8765/zero_os_dashboard.html`
- Windows-like shell UI: [zero_os_shell.html](C:\Users\gomez\Documents\New folder\zero_os_shell.html)
- The shell UI is the main guided interface in this repo. The dashboard server is an additional local surface.

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

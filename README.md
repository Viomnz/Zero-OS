# Zero-OS

Zero-OS runs on one **main highway**: a single dispatcher that routes every request to capability lanes.

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

## Lanes
- `agent`: plan/chain multiple steps in one request
- `code`: create, append, and read files
- `web`: live search and URL fetch
- `system`: local environment info
- `memory`: persistent memory store
- `plugins/*`: optional custom lanes loaded from local `plugins/` files
- `fallback`: unmatched tasks

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

## Memory storage
- Path: `.zero_os/memory.json`
- Local only and ignored by git.

## Extend
Add lane files in `src/zero_os/capabilities/` and register them in `src/zero_os/highway.py`.

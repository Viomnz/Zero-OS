# Zero-OS

Zero-OS uses a **main highway** architecture: one entry point routes every request to the right capability lane.

## Current highway lanes
- `code`: coding and file actions
- `web`: internet/search/browser tasks (stub lane)
- `system`: local environment info
- `memory`: memory-intent lane (stub lane)
- `fallback`: unmatched tasks

## Run
```powershell
python src/main.py "create file notes/plan.txt with main highway online"
python src/main.py "append to notes/plan.txt: next add agents"
python src/main.py "read file notes/plan.txt"
python src/main.py "list files"
python src/main.py "whoami"
```

## What is real now
- `code` can create, append, and read files.
- `system` can list files, show current directory, show user, and show date/time.

## Extend
Add a new file under `src/zero_os/capabilities/` with:
1. `can_handle(task)` keyword or rule matching
2. `run(task)` returning a unified `Result`

Then register it in `src/zero_os/highway.py`.

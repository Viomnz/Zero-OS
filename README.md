# Zero-OS

Zero-OS now includes a **main highway** architecture: one entry point routes every request to the right capability lane.

## Current highway lanes
- `code`: coding, build, debug, refactor tasks
- `web`: internet/search/browser tasks
- `system`: OS/file/run tasks
- `memory`: remember/store/recall tasks
- `fallback`: unmatched tasks

## Run
```powershell
python src/main.py "build a code scaffold"
python src/main.py "search latest AI news"
python src/main.py "remember this note"
```

## Extend
Add a new file under `src/zero_os/capabilities/` with:
1. `can_handle(task)` keyword or rule matching
2. `run(task)` returning a unified `Result`

Then register it in `src/zero_os/highway.py`.

## Vision mapping
Your goal "can do anything in one main highway" is implemented as:
- one input API (`dispatch`)
- one routing layer (`Highway`)
- unlimited pluggable lanes (capabilities)
- one output contract (`Result`)

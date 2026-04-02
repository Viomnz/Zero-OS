# Logic Engine v3

A modular contradiction-testing engine with three interfaces:

1. CLI
2. JSON API
3. Web UI

## Core flow

Input -> Rules -> Reality + Adapters -> Contradiction -> Multi-layer Recursion -> Truth Score -> Compression -> Memory

## Features

- absolute claim detection
- self-validation detection
- rule violations
- reality mismatch detection
- adapter findings
- weighted truth scoring
- contradiction compression
- memory lineage

## Run the CLI

```bash
python main.py --content "This system is always correct" --reality-file examples/reality_state.json --pretty
```

## Run the API

```bash
uvicorn api:app --reload
```

Open:
- `GET /health`
- `POST /evaluate`

## Run the Web UI

```bash
uvicorn web_ui:app --reload
```

Open:
- `http://127.0.0.1:8000/`

## Files

- `logic_engine/` core engine modules
- `main.py` CLI
- `api.py` JSON API
- `web_ui.py` browser UI
- `examples/` sample request and reality state
- `tests/` unit tests

## Install

```bash
pip install -r requirements.txt
```

## Test

```bash
python -m unittest tests/test_engine.py -v
```

## Notes

This package is intentionally self-contained so it can be moved into larger systems later without requiring immediate integration changes.

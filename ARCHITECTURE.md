# Zero OS Architecture

## Goal
Zero OS uses one main highway dispatcher with layered controls around execution.
The system is open source, local first, and designed for both casual and heavy users.

## Runtime Flow
Core rules apply before lane dispatch.

Current runtime sequence in daemon and reasoning path:
1. Security and integrity check
2. Calibration layer
3. Degradation detection layer
4. Communication and interface layer
5. Goal alignment check
6. Internal reasoning with three signals
7. Consensus and fallback control
8. Controlled execution output

## Highway Lanes
- `agent` for codex-style planning and multi-step execution
- `system` for operations and control commands
- `code` for file actions inside workspace
- `web` for internet tasks
- `api` and `browser` utility lanes
- `memory` for persistent memory store
- `plugins/*` for extensions

## Key Defensive Layers
- `security_integrity_layer.py` blocks malicious input and unauthorized command patterns
- `calibration_layer.py` updates reliability toward stable targets
- `degradation_detection.py` detects long-term decline and triggers recovery actions
- `internal_zero_reasoner.py` enforces logic, environment, and survival consensus
- `agent_guard.py` integrity checks and trusted-file restore behavior

## Ops Automation
- Auto optimize engine
- Auto merge similar queue tasks
- AI files smart maintenance

These run from daemon monitor cycle and write runtime evidence in `.zero_os/runtime`.

## Unified Executor
Terminal and PowerShell are merged to one execution path:
- `shell run <command>`
- `terminal run <command>`
- `powershell run <command>`

Dashboard and launcher route into this same path.

## Core Data Paths
- Source: `src/`, `ai_from_scratch/`
- Runtime: `.zero_os/runtime/`
- Production state: `.zero_os/production/`
- Trust keys: `.zero_os/keys/`
- Backups and quarantine: `.zero_os/backup/`, `.zero_os/quarantine/`

## Design Principles
1. One highway routing
2. Immutable core policy
3. No auth requirement by project policy
4. Defense before execution
5. Measurable behavior through logs and tests
6. Open source and local-first operation


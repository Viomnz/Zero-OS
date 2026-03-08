# Scheduler

## Objective
Guarantee forward progress and bounded scheduling latency.

## Requirements
- round-robin baseline
- per-task timeslice
- no starvation in baseline mode

## Prototype Mapping
- code: `src/zero_os/kernel_rnd/scheduler.py`
- class: `RoundRobinScheduler`

## Next
- priority-aware scheduler
- realtime class
- CPU affinity model

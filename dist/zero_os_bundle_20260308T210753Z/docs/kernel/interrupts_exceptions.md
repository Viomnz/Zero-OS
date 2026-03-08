# Interrupts and Exceptions

## Objective
Handle async events and faults with deterministic dispatch.

## Requirements
- IRQ handler registration
- dispatch table lookup
- fault reporting path

## Prototype Mapping
- code: `src/zero_os/kernel_rnd/interrupt_core.py`
- class: `InterruptController`

## Next
- timer IRQ source
- nested interrupt policy
- panic escalation on unrecoverable faults

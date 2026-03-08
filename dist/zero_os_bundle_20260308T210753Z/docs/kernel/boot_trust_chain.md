# Boot and Trust Chain

## Objective
Start every boot from a verifiable image and deterministic fallback.

## Requirements
- kernel image hash verification before handoff
- trusted key material separated from runtime state
- safe-mode entry on verification failure

## Prototype Mapping
- code: `src/zero_os/kernel_rnd/boot_trust.py`
- function: `verify_boot_image(path, expected_sha256)`

## Next
- signed manifest (not hash-only)
- measured boot log format

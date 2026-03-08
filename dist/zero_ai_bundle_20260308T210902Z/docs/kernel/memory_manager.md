# Memory Manager

## Objective
Provide predictable page allocation and isolation boundaries.

## Requirements
- fixed-size page allocator for first stage
- owner tracking for each allocated page
- deterministic free and stats reporting

## Prototype Mapping
- code: `src/zero_os/kernel_rnd/memory_manager.py`
- class: `PageAllocator`

## Next
- virtual address map
- page table abstraction
- per-process address spaces

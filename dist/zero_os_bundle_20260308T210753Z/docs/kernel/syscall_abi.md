# Syscall ABI

## Objective
Define a stable contract between user space and kernel services.

## Baseline Syscalls
1. process spawn
2. process exit
3. file open/read/write
4. page alloc/free
5. IPC send/receive

## Prototype Mapping
- code: `src/zero_os/kernel_rnd/syscall_abi.py`
- function: `resolve_syscall(number)`

## Rules
- syscall numbers are stable once released
- any change requires ABI version bump

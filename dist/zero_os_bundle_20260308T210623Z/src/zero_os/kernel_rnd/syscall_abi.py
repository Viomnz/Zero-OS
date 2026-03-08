from __future__ import annotations


SYSCALL_TABLE = {
    1: "proc_spawn",
    2: "proc_exit",
    3: "file_open",
    4: "file_read",
    5: "file_write",
    6: "mem_alloc_page",
    7: "mem_free_page",
    8: "ipc_send",
    9: "ipc_recv",
}


def resolve_syscall(number: int) -> dict:
    name = SYSCALL_TABLE.get(int(number))
    return {"ok": name is not None, "number": int(number), "name": name}

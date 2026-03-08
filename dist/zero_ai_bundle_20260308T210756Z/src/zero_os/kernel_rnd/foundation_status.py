from __future__ import annotations

from pathlib import Path


def kernel_foundation_status(cwd: str) -> dict:
    root = Path(cwd).resolve()
    docs = root / "docs" / "kernel"
    required_docs = [
        "README.md",
        "boot_trust_chain.md",
        "memory_manager.md",
        "scheduler.md",
        "syscall_abi.md",
        "interrupts_exceptions.md",
        "process_thread_model.md",
        "driver_framework.md",
    ]
    checks = {name: (docs / name).exists() for name in required_docs}
    passed = sum(1 for ok in checks.values() if ok)
    return {
        "kernel_rnd_foundation_score": round((passed / len(required_docs)) * 100, 2),
        "passed": passed,
        "total": len(required_docs),
        "checks": checks,
        "next_priority": [
            "timer core prototype",
            "vfs abstraction",
            "security capability model",
            "panic dump format",
        ],
    }

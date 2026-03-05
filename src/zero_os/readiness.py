"""OS readiness and gap-fix scaffolding."""

from __future__ import annotations

import json
from pathlib import Path


def os_readiness(cwd: str) -> dict:
    base = Path(cwd).resolve()
    checks = {
        "drivers_manifest": (base / "drivers" / "manifest.json").exists(),
        "apps_registry": (base / "apps" / "registry.json").exists(),
        "services_manifest": (base / "services" / "manifest.json").exists(),
        "security_policy": (base / "security" / "policy.json").exists(),
        "system_profile": (base / "zero_os_config" / "system_profile.json").exists(),
        "ci_pipeline": (base / ".github" / "workflows" / "ci.yml").exists(),
    }
    score = int(sum(1 for v in checks.values() if v) * 100 / len(checks))
    missing = [k for k, v in checks.items() if not v]
    return {"score": score, "checks": checks, "missing": missing}


def apply_missing_fix(cwd: str) -> dict:
    base = Path(cwd).resolve()
    created = []

    targets = {
        base / "drivers" / "manifest.json": {
            "version": 1,
            "drivers": [
                {"name": "generic-fs", "status": "active"},
                {"name": "generic-net", "status": "active"},
                {"name": "generic-display", "status": "planned"},
            ],
        },
        base / "apps" / "registry.json": {
            "version": 1,
            "apps": [],
        },
        base / "services" / "manifest.json": {
            "version": 1,
            "services": [
                {"name": "zero-ai-daemon", "autostart": True},
                {"name": "cure-firewall", "autostart": True},
            ],
        },
        base / "security" / "policy.json": {
            "version": 1,
            "policies": {
                "mark_strict_default": True,
                "net_strict_default": True,
                "signed_beacons_required": True,
            },
        },
        base / "zero_os_config" / "system_profile.json": {
            "name": "zero-os",
            "mode": "specialized",
            "goal": "secure recursive intelligence runtime",
        },
    }

    for path, payload in targets.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            created.append(str(path))

    return {"created": created, "created_count": len(created)}


def beginner_os_coverage(cwd: str) -> dict:
    base = Path(cwd).resolve()
    checks = {
        "boot_kernel_base": (base / "kernel" / "config.json").exists(),
        "process_scheduler": (base / "kernel" / "scheduler.json").exists(),
        "memory_management": (base / "kernel" / "memory.json").exists(),
        "filesystem_core": (base / "kernel" / "filesystem.json").exists(),
        "device_drivers": (base / "drivers" / "manifest.json").exists(),
        "cli_shell": (base / "shell" / "commands.json").exists(),
        "security_permissions": (base / "security" / "policy.json").exists(),
        "syscall_api": (base / "kernel" / "syscalls.json").exists(),
        "app_loader": (base / "apps" / "loader.json").exists(),
        "update_rollback": (base / "zero_os_config" / "update_channels.json").exists(),
        "logging_errors": (base / "security" / "error_playbooks.json").exists(),
        "test_recovery": (base / "tests" / "conftest.py").exists(),
    }
    total = len(checks)
    passed = sum(1 for v in checks.values() if v)
    score = int(passed * 100 / total)
    missing = [k for k, v in checks.items() if not v]
    return {"score": score, "checks": checks, "missing": missing, "passed": passed, "total": total}


def apply_beginner_os_fix(cwd: str) -> dict:
    base = Path(cwd).resolve()
    created = []
    targets = {
        base / "kernel" / "config.json": {
            "name": "zero-kernel",
            "boot_mode": "single-user",
            "version": 1,
        },
        base / "kernel" / "scheduler.json": {
            "algorithm": "round_robin",
            "timeslice_ms": 25,
        },
        base / "kernel" / "memory.json": {
            "allocator": "paged",
            "page_size": 4096,
            "protection": True,
        },
        base / "kernel" / "filesystem.json": {
            "type": "zero-fs",
            "journaling": True,
        },
        base / "kernel" / "syscalls.json": {
            "syscalls": [
                "process.spawn",
                "process.kill",
                "fs.read",
                "fs.write",
                "mem.alloc",
                "mem.free",
                "net.send",
                "net.recv",
            ]
        },
        base / "shell" / "commands.json": {
            "commands": [
                "help",
                "ls",
                "pwd",
                "cat",
                "run",
                "ps",
                "kill",
            ]
        },
        base / "apps" / "loader.json": {
            "format": "manifest-first",
            "verify_signatures": True,
        },
        base / "zero_os_config" / "update_channels.json": {
            "channel": "stable",
            "rollback_points": 5,
        },
    }
    for path, payload in targets.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            created.append(str(path))
    return {"created": created, "created_count": len(created)}

from __future__ import annotations

from pathlib import Path


def _check_any(root: Path, candidates: list[str]) -> bool:
    for rel in candidates:
        if (root / rel).exists():
            return True
    return False


def real_os_status(cwd: str) -> dict:
    root = Path(cwd).resolve()
    checks = {
        "bootloader_artifact": _check_any(
            root,
            [
                "boot/zero_boot.efi",
                "boot/zero_bootloader.efi",
                "build/boot/zero_boot.efi",
            ],
        ),
        "kernel_binary": _check_any(
            root,
            [
                "kernel/zero_kernel.bin",
                "kernel/zero_kernel.elf",
                "build/kernel/zero_kernel.bin",
                "build/kernel/zero_kernel.elf",
            ],
        ),
        "initramfs_image": _check_any(
            root,
            [
                "boot/initramfs.img",
                "build/boot/initramfs.img",
            ],
        ),
        "hardware_driver_bundle": _check_any(
            root,
            [
                "drivers/manifest.json",
                "drivers/signed/manifest.json",
            ],
        ),
        "bootable_media_recipe": _check_any(
            root,
            [
                "scripts/build_boot_media.ps1",
                "scripts/build_boot_media.sh",
                "docs/kernel/boot_media.md",
            ],
        ),
    }
    passed = sum(1 for ok in checks.values() if ok)
    total = len(checks)
    score = round((passed / total) * 100, 2)
    mode = "prototype-native" if passed == total else "hosted-overlay"
    return {
        "ok": True,
        "classification": mode,
        "real_os_readiness_score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "summary": (
            "Standalone boot path detected."
            if mode == "prototype-native"
            else "Runs as a hosted OS layer on top of an existing operating system."
        ),
        "next_priority": [
            "produce bootloader artifact",
            "build kernel binary artifact",
            "generate initramfs image",
            "package signed minimal driver bundle",
        ],
    }

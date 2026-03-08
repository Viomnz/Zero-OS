from __future__ import annotations

from pathlib import Path


def _check_any(root: Path, candidates: list[str]) -> bool:
    for rel in candidates:
        if (root / rel).exists():
            return True
    return False


def _check_any_glob(root: Path, patterns: list[str]) -> bool:
    for pattern in patterns:
        if any(root.glob(pattern)):
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
                "build/native_os/boot.bin",
                "build/native_os/stage2.bin",
            ],
        ) or _check_any_glob(
            root,
            [
                "boot/*boot*.efi",
                "build/boot/*boot*.efi",
                "build/native_os/*boot*.bin",
                "build/native_os/*stage*.bin",
                "build/native_os/*.efi",
            ],
        ),
        "kernel_binary": _check_any(
            root,
            [
                "kernel/zero_kernel.bin",
                "kernel/zero_kernel.elf",
                "build/kernel/zero_kernel.bin",
                "build/kernel/zero_kernel.elf",
                "build/native_os/kernel.bin",
                "build/native_os/zero_os_native.img",
            ],
        ) or _check_any_glob(
            root,
            [
                "kernel/*kernel*.bin",
                "kernel/*kernel*.elf",
                "build/kernel/*kernel*.bin",
                "build/kernel/*kernel*.elf",
                "build/native_os/*kernel*.bin",
                "build/native_os/*.img",
            ],
        ),
        "initramfs_image": _check_any(
            root,
            [
                "boot/initramfs.img",
                "build/boot/initramfs.img",
                "build/native_os/userland/init.bin",
            ],
        ) or _check_any_glob(
            root,
            [
                "boot/*initramfs*.img",
                "build/boot/*initramfs*.img",
                "build/native_os/userland/init*.bin",
                "build/native_os/init*.img",
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
    priorities = []
    if not checks["bootloader_artifact"]:
        priorities.append("produce bootloader artifact")
    if not checks["kernel_binary"]:
        priorities.append("build kernel binary artifact")
    if not checks["initramfs_image"]:
        priorities.append("generate initramfs image")
    if not checks["hardware_driver_bundle"]:
        priorities.append("package signed minimal driver bundle")
    if not checks["bootable_media_recipe"]:
        priorities.append("document bootable media build recipe")
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
        "next_priority": priorities,
    }

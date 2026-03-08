from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if p.returncode != 0:
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        raise RuntimeError(out.strip() or f"command failed: {' '.join(cmd)}")


def build_image(root: Path, image_name: str = "zero_os_native.img", size_kb: int = 1440) -> Path:
    nasm = shutil.which("nasm")
    if not nasm:
        candidates = [
            r"C:\Users\gomez\tools\nasm\nasm-3.01\nasm.exe",
            r"C:\Program Files\NASM\nasm.exe",
            r"C:\Program Files (x86)\NASM\nasm.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                nasm = c
                break
    if not nasm:
        raise RuntimeError("nasm not found. Install NASM, then rerun.")

    boot_src = root / "native_os" / "boot" / "boot.asm"
    stage2_src = root / "native_os" / "boot" / "stage2.asm"
    kernel_src = root / "native_os" / "kernel" / "kernel_entry.asm"
    if not boot_src.exists():
        raise RuntimeError(f"missing boot source: {boot_src}")
    if not stage2_src.exists():
        raise RuntimeError(f"missing stage2 source: {stage2_src}")
    if not kernel_src.exists():
        raise RuntimeError(f"missing kernel source: {kernel_src}")

    out_dir = root / "build" / "native_os"
    out_dir.mkdir(parents=True, exist_ok=True)
    boot_bin = out_dir / "boot.bin"
    stage2_bin = out_dir / "stage2.bin"
    kernel_bin = out_dir / "kernel.bin"
    image = out_dir / image_name

    run([nasm, "-f", "bin", str(boot_src), "-o", str(boot_bin)], root)
    run([nasm, "-f", "bin", str(stage2_src), "-o", str(stage2_bin)], root)
    run([nasm, "-f", "bin", str(kernel_src), "-o", str(kernel_bin)], root)

    total = max(512, int(size_kb) * 1024)
    image.write_bytes(b"\x00" * total)

    data = boot_bin.read_bytes()
    if len(data) != 512:
        raise RuntimeError(f"boot sector must be exactly 512 bytes, got {len(data)}")
    stage2 = stage2_bin.read_bytes()
    stage2_sectors = 4
    stage2_max = stage2_sectors * 512
    if len(stage2) == 0:
        raise RuntimeError("stage2 payload is empty")
    if len(stage2) > stage2_max:
        raise RuntimeError(f"stage2 too large: {len(stage2)} > {stage2_max} bytes")
    kernel = kernel_bin.read_bytes()
    kernel_sectors = 64
    kernel_max = kernel_sectors * 512
    if len(kernel) == 0:
        raise RuntimeError("kernel payload is empty")
    if len(kernel) > kernel_max:
        raise RuntimeError(f"kernel too large: {len(kernel)} > {kernel_max} bytes")
    with image.open("r+b") as f:
        f.seek(0)
        f.write(data)
        f.seek(512)
        f.write(stage2)
        f.seek(512 * 5)  # sector 6 start (1-based)
        f.write(kernel)

    return image


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Zero OS native bootable image")
    ap.add_argument("--image-name", default="zero_os_native.img")
    ap.add_argument("--size-kb", type=int, default=1440)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    img = build_image(root, args.image_name, args.size_kb)
    print(str(img))
    print("Build OK: bootable BIOS image created.")
    print("Run with: qemu-system-i386 -drive format=raw,file=" + str(img))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

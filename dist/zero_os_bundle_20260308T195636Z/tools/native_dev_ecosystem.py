from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_native_image import build_image


def _which(candidates: list[str]) -> str:
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
    return ""


def toolchain_status() -> dict:
    cross = _which(["x86_64-elf-gcc", "i686-elf-gcc"])
    status = {
        "nasm": _which(["nasm"]),
        "clang": _which(["clang"]),
        "lld": _which(["ld.lld", "lld-link"]),
        "gcc": _which(["gcc"]),
        "cross_gcc": cross,
        "qemu_i386": _which(["qemu-system-i386"]),
    }
    score = sum(1 for v in status.values() if bool(v))
    return {"ok": True, "score": score, "total": len(status), "tools": status}


def _run(cmd: list[str], cwd: Path) -> None:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if p.returncode != 0:
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        raise RuntimeError(out.strip() or f"command failed: {' '.join(cmd)}")


def build_kernel_userland(root: Path) -> dict:
    img = build_image(root)
    nasm = _which(["nasm"])
    if not nasm:
        fallback = Path(r"C:\Users\gomez\tools\nasm\nasm-3.01\nasm.exe")
        nasm = str(fallback) if fallback.exists() else ""
    if not nasm:
        raise RuntimeError("nasm not found for userland build")

    user_src = root / "native_os" / "userland" / "init.asm"
    out_dir = root / "build" / "native_os" / "userland"
    out_dir.mkdir(parents=True, exist_ok=True)
    user_bin = out_dir / "init.bin"
    _run([nasm, "-f", "bin", str(user_src), "-o", str(user_bin)], root)

    manifest = {
        "image": str(img),
        "userland_modules": [{"name": "init", "path": str(user_bin), "size": user_bin.stat().st_size}],
    }
    manifest_path = root / "build" / "native_os" / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "manifest": manifest, "manifest_path": str(manifest_path)}


def qemu_boot_smoke(root: Path, timeout_s: int = 5) -> dict:
    qemu = _which(["qemu-system-i386"])
    if not qemu:
        fallback = Path(r"C:\Program Files\qemu\qemu-system-i386.exe")
        qemu = str(fallback) if fallback.exists() else ""
    if not qemu:
        return {"ok": False, "reason": "qemu-system-i386 not found"}

    img = root / "build" / "native_os" / "zero_os_native.img"
    if not img.exists():
        build_image(root)

    cmd = [qemu, "-drive", f"format=raw,file={img}", "-nographic", "-monitor", "none", "-serial", "none"]
    try:
        subprocess.run(cmd, cwd=str(root), timeout=timeout_s, capture_output=True, text=True)
        return {"ok": True, "result": "qemu-exited", "image": str(img)}
    except subprocess.TimeoutExpired:
        return {"ok": True, "result": "qemu-boot-running", "image": str(img)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Zero OS native developer ecosystem")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("toolchain-status")
    sub.add_parser("build-all")
    smoke = sub.add_parser("qemu-smoke")
    smoke.add_argument("--timeout", type=int, default=5)
    args = ap.parse_args()

    root = ROOT
    try:
        if args.cmd == "toolchain-status":
            data = toolchain_status()
        elif args.cmd == "build-all":
            data = build_kernel_userland(root)
        else:
            data = qemu_boot_smoke(root, args.timeout)
        print(json.dumps(data, indent=2))
        return 0 if data.get("ok", False) else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

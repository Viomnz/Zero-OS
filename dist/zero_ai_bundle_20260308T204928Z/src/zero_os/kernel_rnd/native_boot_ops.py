from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.kernel_rnd.boot_trust import image_sha256, verify_boot_image


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "native_boot_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "uefi": {"enabled": False, "bootx64_path": "", "last_scaffold_utc": ""},
        "loaders": {"elf": [], "modules": []},
        "panic": {"last_panic_utc": "", "last_reason": "", "recovered": True, "last_dump_path": ""},
        "secure_boot": {"enabled": False, "pk_hash": "", "last_verify": {}},
        "measured_boot": {"entries": []},
        "updated_utc": _utc_now(),
    }


def _load(cwd: str) -> dict:
    p = _state_path(cwd)
    if not p.exists():
        d = _default_state()
        _save(cwd, d)
        return d
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        d = _default_state()
        _save(cwd, d)
        return d


def _save(cwd: str, state: dict) -> None:
    state["updated_utc"] = _utc_now()
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def uefi_status(cwd: str) -> dict:
    s = _load(cwd)
    root = Path(cwd).resolve()
    p = root / "native_os" / "uefi" / "EFI" / "BOOT" / "BOOTX64.EFI"
    u = s["uefi"]
    u["bootx64_path"] = str(p)
    u["enabled"] = p.exists()
    _save(cwd, s)
    return {"ok": True, "uefi": u}


def uefi_scaffold(cwd: str) -> dict:
    root = Path(cwd).resolve()
    boot_dir = root / "native_os" / "uefi" / "EFI" / "BOOT"
    boot_dir.mkdir(parents=True, exist_ok=True)
    efi = boot_dir / "BOOTX64.EFI"
    if not efi.exists():
        efi.write_bytes(b"ZERO-OS-UEFI-STUB\n")
    nsh = root / "native_os" / "uefi" / "startup.nsh"
    nsh.write_text("fs0:\\EFI\\BOOT\\BOOTX64.EFI\n", encoding="utf-8")
    s = _load(cwd)
    s["uefi"]["enabled"] = True
    s["uefi"]["bootx64_path"] = str(efi)
    s["uefi"]["last_scaffold_utc"] = _utc_now()
    _save(cwd, s)
    return {"ok": True, "uefi": s["uefi"], "startup_nsh": str(nsh)}


def _is_elf(path: Path) -> bool:
    try:
        h = path.read_bytes()[:4]
    except Exception:
        return False
    return h == b"\x7fELF"


def elf_load(cwd: str, rel_path: str) -> dict:
    p = (Path(cwd).resolve() / rel_path).resolve()
    if not p.exists():
        return {"ok": False, "reason": "file missing", "path": str(p)}
    if not _is_elf(p):
        return {"ok": False, "reason": "not_elf_magic", "path": str(p)}
    s = _load(cwd)
    rec = {"path": str(p), "sha256": image_sha256(str(p)), "loaded_utc": _utc_now()}
    s["loaders"]["elf"].append(rec)
    _save(cwd, s)
    return {"ok": True, "elf": rec}


def module_load(cwd: str, rel_path: str) -> dict:
    p = (Path(cwd).resolve() / rel_path).resolve()
    if not p.exists():
        return {"ok": False, "reason": "file missing", "path": str(p)}
    s = _load(cwd)
    rec = {"path": str(p), "sha256": image_sha256(str(p)), "loaded_utc": _utc_now()}
    s["loaders"]["modules"].append(rec)
    _save(cwd, s)
    return {"ok": True, "module": rec}


def loader_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "loaders": s["loaders"]}


def panic_trigger(cwd: str, reason: str) -> dict:
    root = Path(cwd).resolve()
    crash_dir = root / ".zero_os" / "crash"
    crash_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dump = crash_dir / f"panic_{ts}.json"
    payload = {"time_utc": _utc_now(), "reason": reason.strip(), "hint": "run kernel panic recover"}
    dump.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    s = _load(cwd)
    s["panic"] = {
        "last_panic_utc": payload["time_utc"],
        "last_reason": payload["reason"],
        "recovered": False,
        "last_dump_path": str(dump),
    }
    _save(cwd, s)
    return {"ok": True, "panic": s["panic"]}


def panic_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "panic": s["panic"]}


def panic_recover(cwd: str) -> dict:
    s = _load(cwd)
    s["panic"]["recovered"] = True
    _save(cwd, s)
    return {"ok": True, "panic": s["panic"]}


def secure_boot_set(cwd: str, enabled: bool, pk_hash: str = "") -> dict:
    s = _load(cwd)
    s["secure_boot"]["enabled"] = bool(enabled)
    if pk_hash:
        s["secure_boot"]["pk_hash"] = pk_hash.strip()
    _save(cwd, s)
    return {"ok": True, "secure_boot": s["secure_boot"]}


def measured_boot_record(cwd: str, component: str, rel_path: str) -> dict:
    p = (Path(cwd).resolve() / rel_path).resolve()
    digest = image_sha256(str(p)) if p.exists() else ""
    rec = {"time_utc": _utc_now(), "component": component.strip(), "path": str(p), "sha256": digest, "exists": p.exists()}
    s = _load(cwd)
    s["measured_boot"]["entries"].append(rec)
    _save(cwd, s)
    return {"ok": True, "entry": rec}


def measured_boot_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "measured_boot": s["measured_boot"]}


def boot_verify(cwd: str, rel_path: str, expected_sha256: str) -> dict:
    p = (Path(cwd).resolve() / rel_path).resolve()
    res = verify_boot_image(str(p), expected_sha256.strip())
    s = _load(cwd)
    s["secure_boot"]["last_verify"] = res
    _save(cwd, s)
    return res

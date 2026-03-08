from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "kernel_stack_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "scheduler": {"queue": [], "last_tid": 0, "tick_count": 0, "current": None},
        "memory": {"total_pages": 4096, "allocations": {}},
        "drivers": {"loaded": {}},
        "filesystem": {"mounts": {}},
        "network": {"interfaces": {}, "routes": []},
        "storage": {"block_drivers": {}, "devices": {}},
        "fs_journal": {"enabled": False, "entries": [], "last_recovery_utc": ""},
        "net_stack": {
            "arp": False,
            "ip": False,
            "tcp": False,
            "udp": False,
            "dhcp": False,
            "dns": False,
            "nics": {},
        },
        "input_display": {
            "keyboard": {"driver": "", "enabled": False},
            "mouse": {"driver": "", "enabled": False},
            "display": {"driver": "", "mode": "vga-text"},
        },
        "platform": {
            "acpi_enabled": False,
            "apic_enabled": False,
            "smp_enabled": False,
            "cpu_count": 1,
        },
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


def kernel_stack_status(cwd: str) -> dict:
    s = _load(cwd)
    for k, v in _default_state().items():
        s.setdefault(k, v)
    used = sum(int(v) for v in s["memory"]["allocations"].values())
    total = int(s["memory"]["total_pages"])
    return {
        "ok": True,
        "scheduler": {
            "queued": len(s["scheduler"]["queue"]),
            "tick_count": int(s["scheduler"]["tick_count"]),
            "current": s["scheduler"]["current"],
        },
        "memory": {
            "total_pages": total,
            "used_pages": used,
            "free_pages": max(0, total - used),
            "allocations": s["memory"]["allocations"],
        },
        "drivers": {"loaded_count": len(s["drivers"]["loaded"]), "loaded": s["drivers"]["loaded"]},
        "filesystem": {"mount_count": len(s["filesystem"]["mounts"]), "mounts": s["filesystem"]["mounts"]},
        "network": {
            "interface_count": len(s["network"]["interfaces"]),
            "route_count": len(s["network"]["routes"]),
            "interfaces": s["network"]["interfaces"],
            "routes": s["network"]["routes"],
        },
        "storage": s["storage"],
        "fs_journal": s["fs_journal"],
        "net_stack": s["net_stack"],
        "input_display": s["input_display"],
        "platform": s["platform"],
        "updated_utc": s.get("updated_utc", ""),
    }


def scheduler_enqueue(cwd: str, name: str, priority: int = 0, timeslice_ms: int = 10) -> dict:
    s = _load(cwd)
    tid = int(s["scheduler"]["last_tid"]) + 1
    s["scheduler"]["last_tid"] = tid
    s["scheduler"]["queue"].append(
        {"tid": tid, "name": name.strip(), "priority": int(priority), "timeslice_ms": int(timeslice_ms)}
    )
    _save(cwd, s)
    return {"ok": True, "enqueued": s["scheduler"]["queue"][-1], "queue_depth": len(s["scheduler"]["queue"])}


def scheduler_tick(cwd: str) -> dict:
    s = _load(cwd)
    q = s["scheduler"]["queue"]
    if not q:
        return {"ok": False, "reason": "queue empty"}
    current = q.pop(0)
    q.append(current)
    s["scheduler"]["tick_count"] = int(s["scheduler"]["tick_count"]) + 1
    s["scheduler"]["current"] = current
    _save(cwd, s)
    return {"ok": True, "current": current, "tick_count": s["scheduler"]["tick_count"]}


def memory_alloc(cwd: str, owner: str, pages: int = 1) -> dict:
    s = _load(cwd)
    p = max(1, int(pages))
    allocs = s["memory"]["allocations"]
    used = sum(int(v) for v in allocs.values())
    total = int(s["memory"]["total_pages"])
    if used + p > total:
        return {"ok": False, "reason": "out of pages", "requested_pages": p, "free_pages": max(0, total - used)}
    allocs[owner.strip()] = int(allocs.get(owner.strip(), 0)) + p
    _save(cwd, s)
    return {"ok": True, "owner": owner.strip(), "pages": allocs[owner.strip()]}


def memory_free(cwd: str, owner: str) -> dict:
    s = _load(cwd)
    allocs = s["memory"]["allocations"]
    if owner.strip() not in allocs:
        return {"ok": False, "reason": "owner not found"}
    released = int(allocs.pop(owner.strip()))
    _save(cwd, s)
    return {"ok": True, "owner": owner.strip(), "released_pages": released}


def driver_load(cwd: str, name: str, version: str = "dev") -> dict:
    s = _load(cwd)
    s["drivers"]["loaded"][name.strip()] = {"version": version.strip(), "loaded_utc": _utc_now()}
    _save(cwd, s)
    return {"ok": True, "driver": name.strip(), "version": version.strip()}


def driver_unload(cwd: str, name: str) -> dict:
    s = _load(cwd)
    cur = s["drivers"]["loaded"]
    if name.strip() not in cur:
        return {"ok": False, "reason": "driver not loaded"}
    cur.pop(name.strip())
    _save(cwd, s)
    return {"ok": True, "driver": name.strip()}


def fs_mount(cwd: str, name: str, path: str, fs_type: str = "vfs") -> dict:
    s = _load(cwd)
    s["filesystem"]["mounts"][name.strip()] = {"path": path.strip(), "fs_type": fs_type.strip(), "mounted_utc": _utc_now()}
    _save(cwd, s)
    return {"ok": True, "mount": name.strip(), "path": path.strip(), "fs_type": fs_type.strip()}


def net_iface_add(cwd: str, name: str, cidr: str) -> dict:
    s = _load(cwd)
    s["network"]["interfaces"][name.strip()] = {"cidr": cidr.strip(), "state": "up"}
    _save(cwd, s)
    return {"ok": True, "interface": name.strip(), "cidr": cidr.strip()}


def net_route_add(cwd: str, destination: str, via: str) -> dict:
    s = _load(cwd)
    r = {"destination": destination.strip(), "via": via.strip()}
    s["network"]["routes"].append(r)
    _save(cwd, s)
    return {"ok": True, "route": r}


def block_driver_set(cwd: str, kind: str, enabled: bool, version: str = "dev") -> dict:
    s = _load(cwd)
    n = kind.strip().lower()
    if n not in {"ahci", "nvme", "virtio-blk"}:
        return {"ok": False, "reason": "driver must be ahci|nvme|virtio-blk"}
    s["storage"]["block_drivers"][n] = {"enabled": bool(enabled), "version": version.strip()}
    _save(cwd, s)
    return {"ok": True, "driver": n, "config": s["storage"]["block_drivers"][n]}


def fs_write(cwd: str, mount: str, path: str, data: str) -> dict:
    s = _load(cwd)
    m = mount.strip()
    if m not in s["filesystem"]["mounts"]:
        return {"ok": False, "reason": "mount not found"}
    dev = s["storage"]["devices"].setdefault(m, {})
    dev[path.strip()] = data
    if s["fs_journal"]["enabled"]:
        s["fs_journal"]["entries"].append({"op": "write", "mount": m, "path": path.strip(), "len": len(data)})
    _save(cwd, s)
    return {"ok": True, "mount": m, "path": path.strip(), "bytes": len(data)}


def fs_read(cwd: str, mount: str, path: str) -> dict:
    s = _load(cwd)
    m = mount.strip()
    data = s["storage"]["devices"].get(m, {}).get(path.strip())
    if data is None:
        return {"ok": False, "reason": "file not found"}
    return {"ok": True, "mount": m, "path": path.strip(), "data": data}


def fs_journal_set(cwd: str, enabled: bool) -> dict:
    s = _load(cwd)
    s["fs_journal"]["enabled"] = bool(enabled)
    _save(cwd, s)
    return {"ok": True, "enabled": s["fs_journal"]["enabled"]}


def fs_recovery_run(cwd: str) -> dict:
    s = _load(cwd)
    count = len(s["fs_journal"]["entries"])
    s["fs_journal"]["last_recovery_utc"] = _utc_now()
    _save(cwd, s)
    return {"ok": True, "replayed_entries": count, "last_recovery_utc": s["fs_journal"]["last_recovery_utc"]}


def net_protocol_set(cwd: str, protocol: str, enabled: bool) -> dict:
    s = _load(cwd)
    p = protocol.strip().lower()
    if p not in {"arp", "ip", "tcp", "udp", "dhcp", "dns"}:
        return {"ok": False, "reason": "protocol must be arp|ip|tcp|udp|dhcp|dns"}
    s["net_stack"][p] = bool(enabled)
    _save(cwd, s)
    return {"ok": True, "protocol": p, "enabled": s["net_stack"][p]}


def nic_driver_set(cwd: str, name: str, driver: str, enabled: bool = True) -> dict:
    s = _load(cwd)
    s["net_stack"]["nics"][name.strip()] = {"driver": driver.strip(), "enabled": bool(enabled)}
    _save(cwd, s)
    return {"ok": True, "nic": name.strip(), "config": s["net_stack"]["nics"][name.strip()]}


def input_driver_set(cwd: str, device: str, driver: str, enabled: bool) -> dict:
    s = _load(cwd)
    d = device.strip().lower()
    if d not in {"keyboard", "mouse"}:
        return {"ok": False, "reason": "device must be keyboard|mouse"}
    s["input_display"][d] = {"driver": driver.strip(), "enabled": bool(enabled)}
    _save(cwd, s)
    return {"ok": True, "device": d, "config": s["input_display"][d]}


def display_driver_set(cwd: str, driver: str, mode: str) -> dict:
    s = _load(cwd)
    s["input_display"]["display"] = {"driver": driver.strip(), "mode": mode.strip()}
    _save(cwd, s)
    return {"ok": True, "display": s["input_display"]["display"]}


def platform_topology_set(cwd: str, acpi: bool | None = None, apic: bool | None = None, smp: bool | None = None, cpu_count: int | None = None) -> dict:
    s = _load(cwd)
    p = s["platform"]
    if acpi is not None:
        p["acpi_enabled"] = bool(acpi)
    if apic is not None:
        p["apic_enabled"] = bool(apic)
    if smp is not None:
        p["smp_enabled"] = bool(smp)
    if cpu_count is not None:
        p["cpu_count"] = max(1, int(cpu_count))
    _save(cwd, s)
    return {"ok": True, "platform": p}

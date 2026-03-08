from __future__ import annotations

import platform

from zero_os.hyperlayer.adapters.base import BaseAdapter
from zero_os.hyperlayer.adapters.linux import LinuxAdapter
from zero_os.hyperlayer.adapters.macos import MacOSAdapter
from zero_os.hyperlayer.adapters.windows import WindowsAdapter
from zero_os.hyperlayer.contracts import ZeroApi


def get_adapter() -> ZeroApi:
    name = platform.system().lower()
    if name.startswith("win"):
        return WindowsAdapter()
    if name.startswith("linux"):
        return LinuxAdapter()
    if name.startswith("darwin"):
        return MacOSAdapter()
    return BaseAdapter()


def hyperlayer_status() -> dict:
    adapter = get_adapter()
    info = adapter.get_system_info()
    list_files_ok = adapter.list_files(path=".", limit=5).ok
    net_probe_ok = adapter.network_probe("example.com", 443, 2).ok
    pkg_ok = adapter.package_runtime_status().ok
    sec_ok = adapter.security_policy_backend().ok
    return {
        "zero_hyperlayer": True,
        "active_backend": adapter.backend_name(),
        "system_info": info.detail,
        "unified_api": {
            "get_system_info": True,
            "list_processes": True,
            "run_shell": True,
            "list_files": list_files_ok,
            "network_probe": net_probe_ok,
            "package_runtime_status": pkg_ok,
            "security_policy_backend": sec_ok,
        },
        "planned_next": [],
    }

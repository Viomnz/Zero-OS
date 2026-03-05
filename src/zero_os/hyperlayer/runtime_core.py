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
    return {
        "zero_hyperlayer": True,
        "active_backend": adapter.backend_name(),
        "system_info": info.detail,
        "unified_api": {
            "get_system_info": True,
            "list_processes": True,
            "run_shell": True,
        },
        "planned_next": [
            "unified filesystem API",
            "unified network sockets API",
            "unified package runtime",
            "cross-platform security policy backend",
        ],
    }

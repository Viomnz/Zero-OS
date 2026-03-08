from __future__ import annotations

from zero_os.hyperlayer.adapters.base import BaseAdapter


class WindowsAdapter(BaseAdapter):
    def backend_name(self) -> str:
        return "windows"

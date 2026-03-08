from __future__ import annotations

from zero_os.net_client import request_text
from zero_os.native_app_store import install as native_store_install, status as native_store_status
from zero_os.recovery import zero_ai_recover
from zero_os.self_repair import self_repair_run


def web_fetch(url: str) -> dict:
    return request_text(url, timeout=8, retries=1)


def store_status(cwd: str) -> dict:
    return native_store_status(cwd)


def store_install(cwd: str, app_name: str, os_name: str = "") -> dict:
    return native_store_install(cwd, app_name, os_name)


def run_recovery(cwd: str) -> dict:
    return zero_ai_recover(cwd)


def run_self_repair(cwd: str) -> dict:
    return self_repair_run(cwd)

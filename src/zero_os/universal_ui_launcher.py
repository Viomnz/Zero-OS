from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def _base(cwd: str) -> Path:
    return Path(cwd).resolve()


def _shell_url(cwd: str) -> str:
    return (_base(cwd) / "zero_os_shell.html").resolve().as_uri()


def _welcome_url(cwd: str) -> str:
    return (_base(cwd) / "index.html").resolve().as_uri()


def _bridge_running(host: str = "127.0.0.1", port: int = 8766) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.4):
            return True
    except OSError:
        return False


def _spawn_shell_bridge(cwd: str) -> dict:
    base = _base(cwd)
    from zero_os.native_shell_bridge import init_shell_bridge_auth

    auth = init_shell_bridge_auth(str(base))
    command = [
        sys.executable,
        "-c",
        (
            "from zero_os.native_shell_bridge import run_shell_bridge; "
            f"run_shell_bridge(r'{str(base)}')"
        ),
    ]
    kwargs: dict = {
        "cwd": str(base),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True

    subprocess.Popen(command, **kwargs)
    for _ in range(20):
        if _bridge_running():
            return {"ok": True, "bridge_started": True, "config_js": auth["config_js"], "port": 8766}
        time.sleep(0.2)
    return {"ok": False, "bridge_started": False, "config_js": auth["config_js"], "port": 8766}


def launch(cwd: str) -> dict:
    base = _base(cwd)
    platform_name = sys.platform
    smoke_mode = os.getenv("ZERO_OS_UI_SMOKE", "").strip().lower() in {"1", "true", "yes", "on"}

    if smoke_mode:
        return {
            "ok": True,
            "launched": False,
            "ui": "zero-os-ui-smoke",
            "platform_mode": "windows-native" if platform_name.startswith("win") else "cross-platform-web-shell",
            "welcome_url": _welcome_url(str(base)),
            "shell_url": _shell_url(str(base)),
            "smoke": True,
        }

    if platform_name.startswith("win"):
        try:
            from zero_os.native_zero_ui import launch as native_zero_ui_launch

            payload = native_zero_ui_launch(str(base))
            if isinstance(payload, dict):
                payload.setdefault("platform_mode", "windows-native")
                payload.setdefault("recommended_fallback", _shell_url(str(base)))
                return payload
        except Exception as exc:
            fallback = launch_web_shell(str(base))
            fallback["native_error"] = str(exc)
            fallback["platform_mode"] = "windows-web-fallback"
            return fallback

    payload = launch_web_shell(str(base))
    payload["platform_mode"] = "cross-platform-web-shell"
    return payload


def launch_web_shell(cwd: str) -> dict:
    base = _base(cwd)
    bridge = {"ok": True, "bridge_started": False, "port": 8766}
    if not _bridge_running():
        bridge = _spawn_shell_bridge(str(base))

    welcome_url = _welcome_url(str(base))
    shell_url = _shell_url(str(base))
    webbrowser.open(welcome_url)
    return {
        "ok": True,
        "launched": True,
        "ui": "zero-os-welcome",
        "welcome_url": welcome_url,
        "shell_url": shell_url,
        "bridge": bridge,
        "commands": {
            "python": f'{sys.executable} "{base / "zero_os_ui.py"}"',
            "zero_os": 'python src/main.py "zero os native ui launch"',
        },
    }


def cli() -> int:
    cwd = str(Path.cwd())
    result = launch(cwd)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(cli())

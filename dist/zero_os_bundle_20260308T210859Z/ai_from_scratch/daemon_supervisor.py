from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            return bool(out) and "No tasks are running" not in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _startup_healthy(runtime: Path) -> bool:
    hb = runtime / "zero_ai_heartbeat.json"
    if not hb.exists():
        return False
    payload = _read_json(hb)
    return payload.get("status") == "running" and bool(payload.get("boot_ok", False))


def _spawn_kwargs() -> dict:
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        # Keep daemon alive if the supervisor/session exits and avoid flashing console windows.
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    return kwargs


def _background_python() -> str:
    if os.name != "nt":
        return sys.executable
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    return str(pyw if pyw.exists() else py)


def run_supervisor(base: Path) -> None:
    rt = _runtime(base)
    lock = rt / "zero_supervisor.lock"
    pidfile = rt / "zero_supervisor.pid"
    daemon_pidfile = rt / "zero_ai.pid"
    stopfile = rt / "zero_supervisor.stop"
    heartbeat = rt / "zero_supervisor_heartbeat.json"

    if lock.exists():
        old = _read_pid(lock)
        if old and _pid_alive(old):
            return
        lock.unlink(missing_ok=True)
    lock.write_text(str(os.getpid()), encoding="utf-8")
    pidfile.write_text(str(os.getpid()), encoding="utf-8")
    stopfile.unlink(missing_ok=True)

    restart_times: list[float] = []
    last_restart = 0.0
    max_restarts_window = 5
    restart_window_seconds = 120.0
    startup_timeout_seconds = 25.0
    min_restart_interval = 5.0

    try:
        while True:
            if stopfile.exists():
                stopfile.unlink(missing_ok=True)
                break
            daemon_pid = _read_pid(daemon_pidfile)
            alive = bool(daemon_pid and _pid_alive(daemon_pid))
            restarted = False
            throttled = False
            startup_ok = None
            if not alive:
                now = time.time()
                restart_times = [t for t in restart_times if now - t <= restart_window_seconds]
                if len(restart_times) >= max_restarts_window:
                    throttled = True
                elif now - last_restart < min_restart_interval:
                    throttled = True
                if throttled:
                    _write(
                        heartbeat,
                        {
                            "time_utc": _utc_now(),
                            "status": "throttled",
                            "reason": "restart backoff active",
                            "supervisor_pid": os.getpid(),
                            "daemon_pid": daemon_pid,
                            "daemon_alive": alive,
                            "restart_window_seconds": restart_window_seconds,
                            "max_restarts_window": max_restarts_window,
                            "restart_attempts_window": len(restart_times),
                        },
                    )
                    time.sleep(3)
                    continue

                subprocess.Popen(
                    [_background_python(), str(base / "ai_from_scratch" / "daemon.py")],
                    cwd=str(base),
                    **_spawn_kwargs(),
                )
                restarted = True
                last_restart = now
                restart_times.append(now)
                started_at = time.time()
                while time.time() - started_at < startup_timeout_seconds:
                    daemon_pid = _read_pid(daemon_pidfile)
                    if daemon_pid and _pid_alive(daemon_pid) and _startup_healthy(rt):
                        startup_ok = True
                        break
                    time.sleep(1)
                if startup_ok is None:
                    startup_ok = False
                    daemon_pid = _read_pid(daemon_pidfile)
                    if daemon_pid and _pid_alive(daemon_pid):
                        try:
                            os.kill(daemon_pid, signal.SIGTERM)
                        except Exception:
                            pass
            _write(
                heartbeat,
                {
                    "time_utc": _utc_now(),
                    "status": "running",
                    "supervisor_pid": os.getpid(),
                    "daemon_pid": _read_pid(daemon_pidfile),
                    "daemon_alive": bool(daemon_pid and _pid_alive(daemon_pid)),
                    "restarted": restarted,
                    "startup_ok": startup_ok,
                    "restart_attempts_window": len(restart_times),
                },
            )
            time.sleep(3)
    finally:
        pidfile.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
        _write(heartbeat, {"time_utc": _utc_now(), "status": "stopped"})


if __name__ == "__main__":
    run_supervisor(Path.cwd())

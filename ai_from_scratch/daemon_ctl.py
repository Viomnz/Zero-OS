from __future__ import annotations

import argparse
import os
import signal
import subprocess
from pathlib import Path


def runtime(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def start(base: Path) -> None:
    rt = runtime(base)
    pidfile = rt / "zero_ai.pid"
    stopfile = rt / "zero_ai.stop"
    stopfile.unlink(missing_ok=True)
    if pidfile.exists():
        print("already running or stale pidfile")
        return
    cmd = [
        "python",
        str(base / "ai_from_scratch" / "daemon.py"),
    ]
    subprocess.Popen(cmd, cwd=str(base), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("started")


def stop(base: Path) -> None:
    rt = runtime(base)
    pidfile = rt / "zero_ai.pid"
    stopfile = rt / "zero_ai.stop"
    stopfile.write_text("stop", encoding="utf-8")
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text(encoding="utf-8").strip())
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        pidfile.unlink(missing_ok=True)
    print("stop signal sent")


def status(base: Path) -> None:
    rt = runtime(base)
    hb = rt / "zero_ai_heartbeat.json"
    if not hb.exists():
        print("not running")
        return
    print(hb.read_text(encoding="utf-8", errors="replace"))


def task(base: Path, prompt: str) -> None:
    rt = runtime(base)
    inbox = rt / "zero_ai_tasks.txt"
    with inbox.open("a", encoding="utf-8") as handle:
        handle.write(prompt + "\n")
    print("task queued")


def main() -> None:
    p = argparse.ArgumentParser(description="Zero-AI daemon control")
    p.add_argument("cmd", choices=["start", "stop", "status", "task"])
    p.add_argument("--prompt", default="")
    args = p.parse_args()

    base = Path.cwd()
    if args.cmd == "start":
        start(base)
    elif args.cmd == "stop":
        stop(base)
    elif args.cmd == "status":
        status(base)
    elif args.cmd == "task":
        task(base, args.prompt)


if __name__ == "__main__":
    main()

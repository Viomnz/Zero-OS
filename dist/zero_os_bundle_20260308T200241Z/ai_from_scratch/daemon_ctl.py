from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from agent_guard import build_baseline, check_health
from english_dictionary import add_definition, dictionary_status, lookup_definition
from internal_zero_reasoner import get_reasoner_profile, set_reasoner_mode, set_reasoner_profile
from open_system_logic import run_sandbox_experiment
from security_core import assess_security, load_policy, save_policy, scan_reputation, trust_file
from smart_flow import run_smart_flow
from agents_monitor import run_agents_monitor
from agents_remediation import run_agents_remediation
from chat_api_server import run_chat_api


def runtime(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


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


def _mode_file(base: Path) -> Path:
    return runtime(base) / "daemon_mode.json"


def _read_mode(base: Path) -> str:
    p = _mode_file(base)
    if not p.exists():
        return "dev"
    try:
        payload = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        mode = str(payload.get("mode", "dev")).strip().lower()
        return mode if mode in {"dev", "protected"} else "dev"
    except Exception:
        return "dev"


def _write_mode(base: Path, mode: str) -> dict:
    selected = mode.strip().lower()
    if selected not in {"dev", "protected"}:
        raise ValueError("mode must be one of: dev, protected")
    payload = {"mode": selected}
    _mode_file(base).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _checkpoint_health(base: Path) -> dict:
    ckpt = base / "ai_from_scratch" / "checkpoint.json"
    backup = runtime(base) / "checkpoint.backup.json"
    if not ckpt.exists() and backup.exists():
        ckpt.write_text(backup.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    if ckpt.exists():
        try:
            payload = _read_json(ckpt)
            if isinstance(payload, dict) and "vocab" in payload and "logits" in payload:
                backup.write_text(ckpt.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                return {"ok": True, "source": "checkpoint"}
        except Exception:
            pass
    if backup.exists():
        try:
            payload = _read_json(backup)
            if isinstance(payload, dict) and "vocab" in payload and "logits" in payload:
                ckpt.write_text(backup.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                return {"ok": True, "source": "backup_restore"}
        except Exception:
            pass
    return {"ok": False, "source": "missing_or_invalid"}


def _spawn_kwargs() -> dict:
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        # Keep daemon alive if the launcher exits and avoid flashing console windows.
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


def start(base: Path, *, quiet: bool = False) -> bool:
    rt = runtime(base)
    pidfile = rt / "zero_supervisor.pid"
    daemon_pidfile = rt / "zero_ai.pid"
    stopfile = rt / "zero_ai.stop"
    supervisor_stop = rt / "zero_supervisor.stop"
    try:
        stopfile.unlink(missing_ok=True)
    except PermissionError:
        pass
    try:
        supervisor_stop.unlink(missing_ok=True)
    except PermissionError:
        pass
    if pidfile.exists():
        try:
            spid = int(pidfile.read_text(encoding="utf-8").strip())
            if _pid_alive(spid):
                if not quiet:
                    print("already running")
                return False
        except Exception:
            pass
        pidfile.unlink(missing_ok=True)
    if daemon_pidfile.exists():
        try:
            dpid = int(daemon_pidfile.read_text(encoding="utf-8").strip())
            if not _pid_alive(dpid):
                daemon_pidfile.unlink(missing_ok=True)
        except Exception:
            daemon_pidfile.unlink(missing_ok=True)
    cmd = [_background_python(), str(base / "ai_from_scratch" / "daemon_supervisor.py")]
    subprocess.Popen(cmd, cwd=str(base), **_spawn_kwargs())
    if not quiet:
        print("started")
    return True


def stop(base: Path) -> None:
    rt = runtime(base)
    pidfile = rt / "zero_ai.pid"
    supervisor_pid = rt / "zero_supervisor.pid"
    stopfile = rt / "zero_ai.stop"
    supervisor_stop = rt / "zero_supervisor.stop"
    stopfile.write_text("stop", encoding="utf-8")
    supervisor_stop.write_text("stop", encoding="utf-8")
    if pidfile.exists():
        forced = False
        try:
            pid = int(pidfile.read_text(encoding="utf-8").strip())
            for _ in range(100):
                if not pidfile.exists():
                    break
                time.sleep(0.1)
            if pidfile.exists():
                os.kill(pid, signal.SIGTERM)
                forced = True
        except Exception:
            pass
        if forced:
            pidfile.unlink(missing_ok=True)
    if supervisor_pid.exists():
        forced = False
        try:
            pid = int(supervisor_pid.read_text(encoding="utf-8").strip())
            for _ in range(100):
                if not supervisor_pid.exists():
                    break
                time.sleep(0.1)
            if supervisor_pid.exists():
                os.kill(pid, signal.SIGTERM)
                forced = True
        except Exception:
            pass
        if forced:
            supervisor_pid.unlink(missing_ok=True)
    print("stop signal sent")


def status(base: Path) -> None:
    rt = runtime(base)
    hb = rt / "zero_ai_heartbeat.json"
    shb = rt / "zero_supervisor_heartbeat.json"
    pidfile = rt / "zero_ai.pid"
    if not hb.exists():
        print("not running")
    else:
        payload = json.loads(hb.read_text(encoding="utf-8", errors="replace"))
        live = False
        if pidfile.exists():
            try:
                live = _pid_alive(int(pidfile.read_text(encoding="utf-8").strip()))
            except Exception:
                live = False
        payload["pid_alive"] = live
        if not live and payload.get("status") == "running":
            payload["status"] = "stale"
            payload["reason"] = "heartbeat stale: pid not running"
        print(json.dumps(payload, indent=2))
    if shb.exists():
        print(shb.read_text(encoding="utf-8", errors="replace"))
    print(json.dumps({"mode": _read_mode(base)}, indent=2))


def task(base: Path, prompt: str) -> None:
    rt = runtime(base)
    inbox = rt / "zero_ai_tasks.txt"
    with inbox.open("a", encoding="utf-8") as handle:
        handle.write(prompt + "\n")
    print("task queued")


def health(base: Path) -> None:
    check_health(base)
    print(Path(runtime(base) / "agent_health.json").read_text(encoding="utf-8", errors="replace"))


def baseline(base: Path) -> None:
    build_baseline(base)
    print((runtime(base) / "agent_integrity_baseline.json").read_text(encoding="utf-8", errors="replace"))


def security(base: Path) -> None:
    assess_security(base, 0)
    print(Path(runtime(base) / "security_report.json").read_text(encoding="utf-8", errors="replace"))


def security_policy(base: Path, kv: str) -> None:
    current = load_policy(base)
    if not kv:
        print(json.dumps(current, indent=2))
        return
    updates = {}
    for part in kv.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        key = k.strip()
        val = v.strip()
        if key not in current:
            continue
        if key == "blocked_process_names":
            updates[key] = [x.strip().lower() for x in val.split("|") if x.strip()]
        else:
            updates[key] = int(val)
    out = save_policy(base, updates)
    print(json.dumps(out, indent=2))


def reputation_scan(base: Path) -> None:
    report = scan_reputation(base)
    print(json.dumps(report, indent=2))


def trust(base: Path, file_rel: str, score: int, level: str, note: str) -> None:
    if not file_rel:
        raise ValueError("--file is required")
    entry = trust_file(base, file_rel, score=score, level=level, note=note)
    print(json.dumps(entry, indent=2))


def dictionary(base: Path, word: str, add_word: str, definition: str) -> None:
    if add_word:
        print(json.dumps(add_definition(str(base), add_word, definition), indent=2))
        return
    if word:
        print(json.dumps(lookup_definition(str(base), word), indent=2))
        return
    print(json.dumps(dictionary_status(str(base)), indent=2))


def sandbox_experiment(base: Path) -> None:
    print(json.dumps(run_sandbox_experiment(str(base)), indent=2))


def reasoner_profile(base: Path, profile: str) -> None:
    if profile:
        print(json.dumps(set_reasoner_profile(str(base), profile), indent=2))
        return
    print(json.dumps(get_reasoner_profile(str(base)), indent=2))


def reasoner_mode(base: Path, mode: str) -> None:
    if mode:
        print(json.dumps(set_reasoner_mode(str(base), mode), indent=2))
        return
    print(json.dumps({"mode": get_reasoner_profile(str(base)).get("mode", "stability")}, indent=2))


def daemon_mode(base: Path, mode: str) -> None:
    if mode:
        print(json.dumps(_write_mode(base, mode), indent=2))
        return
    print(json.dumps({"mode": _read_mode(base)}, indent=2))


def smart_flow(base: Path, workspace: str) -> None:
    print(json.dumps(run_smart_flow(str(base), workspace), indent=2))


def refresh_monitor(base: Path) -> None:
    monitor = run_agents_monitor(str(base))
    remediation = run_agents_remediation(str(base), monitor)
    print(json.dumps({"monitor": monitor, "remediation": remediation}, indent=2))


def stabilize(base: Path) -> None:
    stop(base)
    time.sleep(1)
    ckpt = _checkpoint_health(base)
    build_baseline(base)
    started = start(base, quiet=True)
    if not started:
        print(json.dumps({"stabilized": False, "reason": "already_running", "checkpoint": ckpt}, indent=2))
        return

    rt = runtime(base)
    hb = rt / "zero_ai_heartbeat.json"
    ready = False
    status_payload = {}
    for _ in range(20):
        if hb.exists():
            status_payload = _read_json(hb)
            if status_payload.get("status") == "running" and bool(status_payload.get("boot_ok", False)):
                ready = True
                break
            if status_payload.get("status") in {"contained", "eliminated", "compromised"}:
                break
        time.sleep(1)
    monitor = run_agents_monitor(str(base))
    if not ready:
        stop(base)
    print(
        json.dumps(
            {
                "stabilized": ready,
                "checkpoint": ckpt,
                "startup": status_payload,
                "monitor": monitor,
            },
            indent=2,
        )
    )


def serve_chat(base: Path, host: str, port: int) -> None:
    run_chat_api(base, host=host, port=port)


def main() -> None:
    p = argparse.ArgumentParser(description="Zero-AI daemon control")
    p.add_argument(
        "cmd",
        choices=[
            "start",
            "stop",
            "status",
            "task",
            "health",
            "baseline",
            "security",
            "security-policy",
            "reputation-scan",
            "trust-file",
            "dictionary",
            "sandbox-experiment",
            "reasoner-profile",
            "reasoner-mode",
            "mode",
            "smart-flow",
            "refresh-monitor",
            "stabilize",
            "serve-chat",
        ],
    )
    p.add_argument("--prompt", default="")
    p.add_argument("--kv", default="")
    p.add_argument("--file", default="")
    p.add_argument("--score", type=int, default=80)
    p.add_argument("--level", default="trusted")
    p.add_argument("--note", default="")
    p.add_argument("--word", default="")
    p.add_argument("--add-word", default="")
    p.add_argument("--definition", default="")
    p.add_argument("--profile", default="")
    p.add_argument("--mode", default="")
    p.add_argument("--workspace", default="")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
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
    elif args.cmd == "health":
        health(base)
    elif args.cmd == "baseline":
        baseline(base)
    elif args.cmd == "security":
        security(base)
    elif args.cmd == "security-policy":
        security_policy(base, args.kv)
    elif args.cmd == "reputation-scan":
        reputation_scan(base)
    elif args.cmd == "trust-file":
        trust(base, args.file, args.score, args.level, args.note)
    elif args.cmd == "dictionary":
        dictionary(base, args.word, args.add_word, args.definition)
    elif args.cmd == "sandbox-experiment":
        sandbox_experiment(base)
    elif args.cmd == "reasoner-profile":
        reasoner_profile(base, args.profile)
    elif args.cmd == "reasoner-mode":
        reasoner_mode(base, args.mode)
    elif args.cmd == "mode":
        daemon_mode(base, args.mode)
    elif args.cmd == "smart-flow":
        smart_flow(base, args.workspace)
    elif args.cmd == "refresh-monitor":
        refresh_monitor(base)
    elif args.cmd == "stabilize":
        stabilize(base)
    elif args.cmd == "serve-chat":
        serve_chat(base, args.host, args.port)


if __name__ == "__main__":
    main()

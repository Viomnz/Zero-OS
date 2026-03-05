from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from agent_guard import build_baseline, check_health
from english_dictionary import add_definition, dictionary_status, lookup_definition
from internal_zero_reasoner import get_reasoner_profile, set_reasoner_mode, set_reasoner_profile
from open_system_logic import run_sandbox_experiment
from security_core import assess_security, load_policy, save_policy, scan_reputation, trust_file

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


def health(base: Path) -> None:
    report = check_health(base)
    print(Path(runtime(base) / "agent_health.json").read_text(encoding="utf-8", errors="replace"))


def baseline(base: Path) -> None:
    build_baseline(base)
    print((runtime(base) / "agent_integrity_baseline.json").read_text(encoding="utf-8", errors="replace"))


def security(base: Path) -> None:
    report = assess_security(base, 0)
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


def main() -> None:
    p = argparse.ArgumentParser(description="Zero-AI daemon control")
    p.add_argument("cmd", choices=["start", "stop", "status", "task", "health", "baseline", "security", "security-policy", "reputation-scan", "trust-file", "dictionary", "sandbox-experiment", "reasoner-profile", "reasoner-mode"])
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


if __name__ == "__main__":
    main()

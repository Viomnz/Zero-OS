from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from src/ for monitor integration.
BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model import TinyBigramModel
from zero_os.cure_firewall import audit_status
from scan import run_scan
from universe_laws_guard import check_universe_laws


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _monitor_and_backup(base: Path, runtime: Path) -> None:
    monitor_file = runtime / "zero_ai_monitor.json"
    backup_root = base / ".zero_os" / "backup" / "latest"
    backup_root.mkdir(parents=True, exist_ok=True)

    beacons_dir = base / ".zero_os" / "beacons"
    beacon_count = len(list(beacons_dir.glob("*.json"))) if beacons_dir.exists() else 0
    audit = audit_status(str(base))
    _write_json(
        monitor_file,
        {
            "time_utc": _utc_now(),
            "beacon_count": beacon_count,
            "audit_status": audit,
            "mode": "assistant+monitor+backup",
        },
    )

    targets = [
        runtime / "zero_ai_heartbeat.json",
        runtime / "zero_ai_output.txt",
        runtime / "zero_ai_tasks.txt",
        runtime / "zero_ai_scan_report.json",
        monitor_file,
        base / "laws" / "profile.json",
        base / "laws" / "recursion_law.txt",
    ]
    for src in targets:
        if src.exists() and src.is_file():
            shutil.copy2(src, backup_root / src.name)


def main() -> None:
    base = Path.cwd()
    runtime = _runtime_dir(base)
    heartbeat = runtime / "zero_ai_heartbeat.json"
    pidfile = runtime / "zero_ai.pid"
    inbox = runtime / "zero_ai_tasks.txt"
    outbox = runtime / "zero_ai_output.txt"
    stopfile = runtime / "zero_ai.stop"
    ckpt = base / "ai_from_scratch" / "checkpoint.json"

    pidfile.write_text(str(os.getpid()), encoding="utf-8")
    if not inbox.exists():
        inbox.write_text("", encoding="utf-8")

    model = TinyBigramModel.load(str(ckpt)) if ckpt.exists() else None
    processed_lines = len(inbox.read_text(encoding="utf-8", errors="replace").splitlines())
    next_monitor = 0.0

    while True:
        if stopfile.exists():
            stopfile.unlink(missing_ok=True)
            break

        if model is None and ckpt.exists():
            model = TinyBigramModel.load(str(ckpt))

        _write_json(
            heartbeat,
            {
                "status": "running",
                "pid": os.getpid(),
                "time_utc": _utc_now(),
                "checkpoint_loaded": model is not None,
                "inbox": str(inbox),
                "outbox": str(outbox),
                "monitor": str(runtime / "zero_ai_monitor.json"),
                "backup": str(base / ".zero_os" / "backup" / "latest"),
            },
        )

        now_ts = time.time()
        if now_ts >= next_monitor:
            _monitor_and_backup(base, runtime)
            next_monitor = now_ts + 10.0

        lines = inbox.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > processed_lines and model is not None:
            new_lines = lines[processed_lines:]
            for raw in new_lines:
                prompt = raw.strip()
                if not prompt:
                    continue
                with outbox.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc_now()}] prompt={prompt}\n")
                    if prompt.lower().startswith("scan"):
                        report = run_scan(base)
                        status = "[SCAN_PASS]" if report["syntax_error_count"] == 0 and report["tests_passed"] else "[SCAN_FAIL]"
                        handle.write(status + "\n")
                        handle.write(
                            f"syntax_error_count={report['syntax_error_count']}\n"
                            f"tests_passed={report['tests_passed']}\n"
                            "report=.zero_os/runtime/zero_ai_scan_report.json\n\n"
                        )
                    else:
                        accepted = False
                        result_text = ""
                        for i in range(20):
                            sample = model.sample(prompt, length=180, temperature=1.0, seed=100 + i)
                            chk = check_universe_laws(sample)
                            if chk.passed:
                                accepted = True
                                result_text = sample
                                break
                        handle.write(("[UNIVERSE_LAWS_PASS]\n" if accepted else "[UNIVERSE_LAWS_BLOCKED]\n"))
                        handle.write(result_text + "\n\n")
            processed_lines = len(lines)
        elif len(lines) < processed_lines:
            processed_lines = len(lines)

        time.sleep(2)

    _write_json(
        heartbeat,
        {
            "status": "stopped",
            "pid": os.getpid(),
            "time_utc": _utc_now(),
        },
    )
    pidfile.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

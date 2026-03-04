from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from model import TinyBigramModel
from universe_laws_guard import check_universe_laws


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    last_size = inbox.stat().st_size

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
            },
        )

        size = inbox.stat().st_size
        if size > last_size and model is not None:
            data = inbox.read_text(encoding="utf-8", errors="replace")
            task = data[last_size:].strip()
            if task:
                prompt = task.splitlines()[-1].strip()
                accepted = False
                result_text = ""
                for i in range(20):
                    sample = model.sample(prompt, length=180, temperature=1.0, seed=100 + i)
                    chk = check_universe_laws(sample)
                    if chk.passed:
                        accepted = True
                        result_text = sample
                        break
                with outbox.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc_now()}] prompt={prompt}\n")
                    handle.write(("[UNIVERSE_LAWS_PASS]\n" if accepted else "[UNIVERSE_LAWS_BLOCKED]\n"))
                    handle.write(result_text + "\n\n")
            last_size = size
        elif size < last_size:
            last_size = size

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

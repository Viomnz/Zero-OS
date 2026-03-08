from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from zero_os.kernel_rnd.runtime_stack import process_exit, process_spawn


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Zero Native Store Desktop</title>
  <style>
    :root { --bg: #08131d; --panel: #102536; --line: #284863; --text: #eef6ff; --accent: #ffb84d; }
    body { margin: 0; font-family: "Segoe UI", Tahoma, sans-serif; color: var(--text); background: linear-gradient(180deg, #12324d, var(--bg)); }
    .shell { max-width: 1120px; margin: 24px auto; padding: 24px; }
    .hero, .grid > section { background: rgba(16,37,54,.86); border: 1px solid var(--line); border-radius: 18px; padding: 18px; }
    .hero h1 { margin: 0 0 10px; font-size: 34px; }
    .hero p { margin: 0; color: #bcd2e8; }
    .grid { margin-top: 18px; display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 14px; }
    .cta { display: inline-block; margin-top: 14px; background: var(--accent); color: #221606; padding: 10px 14px; border-radius: 999px; font-weight: 700; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1>Zero Native Store</h1>
      <p>Desktop shell for native installs, signed updates, entitlements, and backend sync.</p>
      <span class="cta">Desktop-first client shell</span>
    </section>
    <div class="grid">
      <section><h2>Discover</h2><p>Search, trust score, onboarding, and install actions.</p></section>
      <section><h2>Library</h2><p>Installed apps, repair, uninstall, rollback, and channels.</p></section>
      <section><h2>Backend</h2><p>Identity, charges, event sync, and entitlement refresh.</p></section>
    </div>
  </main>
</body>
</html>
"""


def _state_root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "desktop"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path(cwd: str) -> Path:
    return _state_root(cwd) / "session.json"


def _default_state() -> dict:
    return {
        "session_manager": "zero-desktop-session",
        "window_manager": "stacked-shell",
        "compositor": {"enabled": True, "mode": "layer-compositor", "effects": ["snap", "stack", "blur"]},
        "start_menu": {"style": "layered", "search": True, "pins": ["Zero Files", "Zero Terminal", "Zero Store"]},
        "windows": [],
        "updated_utc": "",
    }


def _load_state(cwd: str) -> dict:
    p = _state_path(cwd)
    if not p.exists():
        data = _default_state()
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        data = _default_state()
    for k, v in _default_state().items():
        data.setdefault(k, v)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def _save_state(cwd: str, state: dict) -> None:
    state["updated_utc"] = datetime.now(timezone.utc).isoformat()
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def scaffold(cwd: str) -> dict:
    root = Path(cwd).resolve() / "build" / "native_store_prod" / "desktop_shell"
    root.mkdir(parents=True, exist_ok=True)
    state = _load_state(cwd)
    files = {
        root / "index.html": HTML,
        root / "app.json": json.dumps(
            {
                "window": {"width": 1280, "height": 820, "title": "Zero Native Store"},
                "integrations": {"protocol_handlers": ["zero-store://"], "notifications": True, "tray": True},
                "desktop": state,
            },
            indent=2,
        )
        + "\n",
    }
    created = []
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
        created.append(str(path))
    return {"ok": True, "root": str(root), "created": created}


def desktop_session_set(cwd: str, session_manager: str, window_manager: str, start_menu_style: str) -> dict:
    state = _load_state(cwd)
    state["session_manager"] = session_manager.strip()
    state["window_manager"] = window_manager.strip()
    state["start_menu"]["style"] = start_menu_style.strip()
    _save_state(cwd, state)
    return {"ok": True, "desktop": state}


def desktop_window_open(cwd: str, app: str, layer: str = "normal") -> dict:
    state = _load_state(cwd)
    proc = process_spawn(cwd, app.strip(), "user")
    rec = {
        "app": app.strip(),
        "layer": layer.strip(),
        "state": "open",
        "z": len(state["windows"]) + 1,
        "snapped": False,
        "pid": proc.get("process", {}).get("pid"),
    }
    state["windows"].append(rec)
    _save_state(cwd, state)
    return {"ok": True, "window": rec, "count": len(state["windows"]), "process": proc.get("process", {})}


def window_action(cwd: str, app: str, action: str) -> dict:
    state = _load_state(cwd)
    name = app.strip().lower()
    action_n = action.strip().lower()
    if action_n not in {"minimize", "maximize", "snap", "close"}:
        return {"ok": False, "reason": "action must be minimize|maximize|snap|close"}
    for rec in reversed(state["windows"]):
        if str(rec.get("app", "")).lower() == name:
            if action_n == "close":
                rec["state"] = "closed"
                if rec.get("pid") is not None:
                    process_exit(cwd, int(rec["pid"]))
            elif action_n == "minimize":
                rec["state"] = "minimized"
            elif action_n == "maximize":
                rec["state"] = "maximized"
                rec["layer"] = "foreground"
            elif action_n == "snap":
                rec["snapped"] = True
                rec["state"] = "open"
            rec["last_action"] = action_n
            rec["z"] = max([int(w.get("z", 0)) for w in state["windows"]] + [0]) + 1
            _save_state(cwd, state)
            return {"ok": True, "window": rec}
    return {"ok": False, "reason": "window not found"}


def compositor_set(cwd: str, mode: str, effects: list[str]) -> dict:
    state = _load_state(cwd)
    state["compositor"] = {
        "enabled": True,
        "mode": mode.strip(),
        "effects": [effect.strip() for effect in effects if effect.strip()],
    }
    _save_state(cwd, state)
    return {"ok": True, "desktop": state}


def window_layer_set(cwd: str, app: str, layer: str) -> dict:
    state = _load_state(cwd)
    name = app.strip().lower()
    for rec in reversed(state["windows"]):
        if str(rec.get("app", "")).lower() == name:
            rec["layer"] = layer.strip()
            rec["z"] = max([int(w.get("z", 0)) for w in state["windows"]] + [0]) + 1
            _save_state(cwd, state)
            return {"ok": True, "window": rec}
    return {"ok": False, "reason": "window not found"}


def desktop_status(cwd: str) -> dict:
    state = _load_state(cwd)
    return {"ok": True, "desktop": state, "window_count": len(state["windows"])}


def launch(cwd: str, backend_url: str = "http://127.0.0.1:8088/health") -> dict:
    root = Path(cwd).resolve() / "build" / "native_store_prod" / "desktop_shell"
    root.mkdir(parents=True, exist_ok=True)
    app = tk.Tk()
    app.title("Zero Native Store")
    app.geometry("980x640")
    app.configure(bg="#08131d")

    header = tk.Label(app, text="Zero Native Store", fg="#eef6ff", bg="#08131d", font=("Segoe UI", 24, "bold"))
    header.pack(pady=(18, 8))
    status_label = tk.Label(app, text="Backend: checking", fg="#bcd2e8", bg="#08131d", font=("Segoe UI", 11))
    status_label.pack()

    frame = ttk.Frame(app, padding=16)
    frame.pack(fill="both", expand=True, padx=16, pady=16)
    app_list = tk.Text(frame, height=16, width=100, bg="#102536", fg="#eef6ff", insertbackground="#eef6ff")
    app_list.pack(fill="both", expand=True)
    app_list.insert("1.0", "Discover\n- Native packages\n- Signed channels\n- Repair and rollback\n")

    def refresh_backend() -> None:
        try:
            with urllib.request.urlopen(backend_url, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            status_label.config(text="Backend: online")
            app_list.delete("1.0", "end")
            app_list.insert("1.0", json.dumps(data, indent=2))
        except Exception as exc:
            status_label.config(text=f"Backend: offline ({exc.__class__.__name__})")

    ttk.Button(app, text="Refresh Backend", command=refresh_backend).pack(pady=(0, 18))
    refresh_backend()
    app.mainloop()
    return {"ok": True, "launched": True}

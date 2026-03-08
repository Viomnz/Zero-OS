from __future__ import annotations

import json
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk


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


def scaffold(cwd: str) -> dict:
    root = Path(cwd).resolve() / "build" / "native_store_prod" / "desktop_shell"
    root.mkdir(parents=True, exist_ok=True)
    files = {
        root / "index.html": HTML,
        root / "app.json": json.dumps(
            {
                "window": {"width": 1280, "height": 820, "title": "Zero Native Store"},
                "integrations": {"protocol_handlers": ["zero-store://"], "notifications": True, "tray": True},
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

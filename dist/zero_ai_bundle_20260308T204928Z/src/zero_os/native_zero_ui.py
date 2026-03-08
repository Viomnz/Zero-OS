from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk


REPO_URL = "https://github.com/Viomnz/Zero-OS"
RELEASES_URL = "https://github.com/Viomnz/Zero-OS/releases"
CLONE_CMD = "git clone https://github.com/Viomnz/Zero-OS.git"
FIRST_RUN_CMD = r".\zero_os_launcher.ps1 first-run"
OPEN_SHELL_CMD = r'Start-Process ".\zero_os_shell.html"'
TAG_CMDS = "git tag v1.0.0\ngit push origin v1.0.0"


def _base(cwd: str) -> Path:
    return Path(cwd).resolve()


def _dist(cwd: str) -> Path:
    p = _base(cwd) / "dist"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _artifact_entries(cwd: str) -> list[Path]:
    return sorted(_dist(cwd).glob("zero_os_bundle_*"), key=lambda p: p.stat().st_mtime, reverse=True)


def _run_zero_os(cwd: str, command: str) -> dict:
    base = _base(cwd)
    proc = subprocess.run(
        [sys.executable, str(base / "src" / "main.py"), command],
        cwd=str(base),
        capture_output=True,
        text=True,
    )
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    payload = {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
    }
    if stdout:
        lines = stdout.splitlines()
        if lines and lines[0].startswith("lane="):
            candidate = "\n".join(lines[1:]).strip()
            if candidate:
                try:
                    payload["json"] = json.loads(candidate)
                except Exception:
                    payload["text"] = candidate
    return payload


def launch(cwd: str) -> dict:
    base = _base(cwd)
    dist = _dist(cwd)

    app = tk.Tk()
    app.title("Zero OS Native UI")
    app.geometry("1240x820")
    app.minsize(1080, 720)
    app.configure(bg="#0c1524")

    style = ttk.Style(app)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Card.TFrame", background="#152538")
    style.configure("Hero.TFrame", background="#173453")
    style.configure("Title.TLabel", background="#173453", foreground="#eef6ff", font=("Segoe UI", 22, "bold"))
    style.configure("Body.TLabel", background="#173453", foreground="#bdd0e6", font=("Segoe UI", 10))
    style.configure("CardTitle.TLabel", background="#152538", foreground="#eef6ff", font=("Segoe UI", 12, "bold"))
    style.configure("CardBody.TLabel", background="#152538", foreground="#bdd0e6", font=("Segoe UI", 10))

    clipboard_status = tk.StringVar(value="Ready")
    result_status = tk.StringVar(value="No action run yet")
    selected_artifact = tk.StringVar(value="")

    root_frame = ttk.Frame(app, padding=18)
    root_frame.pack(fill="both", expand=True)

    hero = ttk.Frame(root_frame, style="Hero.TFrame", padding=20)
    hero.pack(fill="x")
    ttk.Label(hero, text="Zero OS Native UI", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        hero,
        text="Native desktop control surface for copying, exporting, releasing, and sharing Zero OS.",
        style="Body.TLabel",
    ).pack(anchor="w", pady=(6, 0))

    notebook = ttk.Notebook(root_frame)
    notebook.pack(fill="both", expand=True, pady=(16, 0))

    share_tab = ttk.Frame(notebook, padding=16)
    artifacts_tab = ttk.Frame(notebook, padding=16)
    releases_tab = ttk.Frame(notebook, padding=16)
    github_tab = ttk.Frame(notebook, padding=16)
    runtime_tab = ttk.Frame(notebook, padding=16)
    about_tab = ttk.Frame(notebook, padding=16)
    notebook.add(share_tab, text="Share Zero OS")
    notebook.add(artifacts_tab, text="Artifacts")
    notebook.add(releases_tab, text="Release Manager")
    notebook.add(github_tab, text="GitHub")
    notebook.add(runtime_tab, text="Runtime")
    notebook.add(about_tab, text="About")

    def set_result(text: str) -> None:
        result_status.set(text)

    def copy_text(text: str, label: str) -> None:
        app.clipboard_clear()
        app.clipboard_append(text)
        clipboard_status.set(f"Copied: {label}")
        set_result(f"Copied {label} to clipboard")

    def open_url(url: str) -> None:
        webbrowser.open(url)
        set_result(f"Opened {url}")

    def open_dist() -> None:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Start-Process '{dist}'"], check=False)
        set_result("Opened dist folder")

    def open_path(path: Path | None) -> None:
        if not path:
            return
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Start-Process '{path}'"], check=False)
        set_result(f"Opened {path.name}")

    def reveal_path(path: Path | None) -> None:
        if not path:
            return
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Start-Process explorer.exe '/select,\"{path}\"'"], check=False)
        set_result(f"Revealed {path.name}")

    def render_output(payload: object) -> None:
        output_box.delete("1.0", "end")
        output_box.insert("1.0", json.dumps(payload, indent=2) if isinstance(payload, dict) else str(payload))

    def current_artifact() -> Path | None:
        name = selected_artifact.get().strip()
        if not name:
            return None
        p = dist / name
        return p if p.exists() else None

    def render_artifact_details() -> None:
        artifact_details.delete("1.0", "end")
        path = current_artifact()
        if not path:
            artifact_details.insert("1.0", "Select an artifact to inspect.")
            return
        stat = path.stat()
        lines = [
            f"Name: {path.name}",
            f"Path: {path}",
            f"Kind: {'ZIP archive' if path.suffix.lower() == '.zip' else 'Bundle directory'}",
            f"Modified: {stat.st_mtime}",
        ]
        if path.is_file():
            lines.append(f"Size: {stat.st_size} bytes")
        else:
            lines.append(f"Entries: {sum(1 for _ in path.rglob('*'))}")
            manifest = path / "zero_os_share_manifest.json"
            if manifest.exists():
                try:
                    lines.append("")
                    lines.append(json.dumps(json.loads(manifest.read_text(encoding='utf-8', errors='replace')), indent=2))
                except Exception:
                    pass
        artifact_details.insert("1.0", "\n".join(lines))

    def refresh_dist() -> None:
        items = _artifact_entries(str(base))
        dist_box.delete("1.0", "end")
        artifact_list.delete(0, "end")
        if not items:
            dist_box.insert("1.0", "No exported bundles yet.")
            selected_artifact.set("")
            render_artifact_details()
            return
        for item in items:
            kind = "ZIP" if item.suffix.lower() == ".zip" else "DIR"
            dist_box.insert("end", f"[{kind}] {item.name}\n")
            artifact_list.insert("end", item.name)
        if not selected_artifact.get() or not (dist / selected_artifact.get()).exists():
            selected_artifact.set(items[0].name)
            artifact_list.selection_set(0)
        render_artifact_details()

    def run_and_render(command: str, success_label: str) -> None:
        set_result(f"Running: {command}")
        result = _run_zero_os(str(base), command)
        if result.get("ok"):
            payload = result.get("json") or result.get("text") or result.get("stdout") or success_label
            render_output(payload)
            set_result(success_label)
            refresh_dist()
        else:
            render_output(result.get("stderr") or result.get("stdout") or "Action failed")
            set_result("Action failed")

    top_actions = ttk.Frame(share_tab)
    top_actions.pack(fill="x")

    left = ttk.Frame(top_actions)
    left.pack(side="left", fill="both", expand=True)
    right = ttk.Frame(top_actions)
    right.pack(side="left", fill="both", expand=True, padx=(12, 0))

    clone_card = ttk.Frame(left, style="Card.TFrame", padding=16)
    clone_card.pack(fill="x", pady=(0, 12))
    ttk.Label(clone_card, text="Copy From GitHub", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(clone_card, text="Give GitHub users one-click copy actions.", style="CardBody.TLabel").pack(anchor="w", pady=(4, 10))
    ttk.Button(clone_card, text="Copy Clone Command", command=lambda: copy_text(CLONE_CMD, "clone command")).pack(side="left")
    ttk.Button(clone_card, text="Open Repo", command=lambda: open_url(REPO_URL)).pack(side="left", padx=(8, 0))
    ttk.Button(clone_card, text="Open Releases", command=lambda: open_url(RELEASES_URL)).pack(side="left", padx=(8, 0))

    setup_card = ttk.Frame(left, style="Card.TFrame", padding=16)
    setup_card.pack(fill="x")
    ttk.Label(setup_card, text="Quick Start", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(setup_card, text="Copy the setup steps new users need after cloning.", style="CardBody.TLabel").pack(anchor="w", pady=(4, 10))
    ttk.Button(setup_card, text="Copy First-Run", command=lambda: copy_text(FIRST_RUN_CMD, "first-run command")).pack(side="left")
    ttk.Button(setup_card, text="Copy Open Shell", command=lambda: copy_text(OPEN_SHELL_CMD, "open shell command")).pack(side="left", padx=(8, 0))

    export_card = ttk.Frame(right, style="Card.TFrame", padding=16)
    export_card.pack(fill="x", pady=(0, 12))
    ttk.Label(export_card, text="Local Share Build", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(export_card, text="Create a clean folder bundle or zip from the native UI.", style="CardBody.TLabel").pack(anchor="w", pady=(4, 10))
    ttk.Button(export_card, text="Export Bundle", command=lambda: run_and_render("zero os export bundle", "Export bundle complete")).pack(side="left")
    ttk.Button(export_card, text="Create Share Zip", command=lambda: run_and_render("zero os share package", "Share zip complete")).pack(side="left", padx=(8, 0))
    ttk.Button(export_card, text="Open Dist Folder", command=open_dist).pack(side="left", padx=(8, 0))

    status_card = ttk.Frame(right, style="Card.TFrame", padding=16)
    status_card.pack(fill="both", expand=True)
    ttk.Label(status_card, text="Native UI Status", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(status_card, textvariable=clipboard_status, style="CardBody.TLabel").pack(anchor="w", pady=(4, 6))
    ttk.Label(status_card, textvariable=result_status, style="CardBody.TLabel").pack(anchor="w")

    lower = ttk.Frame(share_tab)
    lower.pack(fill="both", expand=True, pady=(14, 0))
    lower.columnconfigure(0, weight=1)
    lower.columnconfigure(1, weight=1)

    out_frame = ttk.Frame(lower, style="Card.TFrame", padding=16)
    out_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    ttk.Label(out_frame, text="Command Output", style="CardTitle.TLabel").pack(anchor="w")
    output_box = tk.Text(out_frame, height=18, bg="#0d1826", fg="#eef6ff", insertbackground="#eef6ff", relief="flat", wrap="word")
    output_box.pack(fill="both", expand=True, pady=(8, 0))
    output_box.insert("1.0", "Run Export Bundle or Create Share Zip to see output here.")

    dist_frame = ttk.Frame(lower, style="Card.TFrame", padding=16)
    dist_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    ttk.Label(dist_frame, text="Share Artifacts", style="CardTitle.TLabel").pack(anchor="w")
    dist_box = tk.Text(dist_frame, height=18, bg="#0d1826", fg="#eef6ff", insertbackground="#eef6ff", relief="flat", wrap="word")
    dist_box.pack(fill="both", expand=True, pady=(8, 0))

    artifacts_tab.columnconfigure(0, weight=1)
    artifacts_tab.columnconfigure(1, weight=2)
    artifacts_tab.rowconfigure(0, weight=1)

    artifacts_list_frame = ttk.Frame(artifacts_tab, style="Card.TFrame", padding=16)
    artifacts_list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    ttk.Label(artifacts_list_frame, text="Exported Bundles", style="CardTitle.TLabel").pack(anchor="w")
    artifact_list = tk.Listbox(artifacts_list_frame, bg="#0d1826", fg="#eef6ff", selectbackground="#28507b", relief="flat")
    artifact_list.pack(fill="both", expand=True, pady=(8, 10))
    art_actions = ttk.Frame(artifacts_list_frame)
    art_actions.pack(anchor="w")
    ttk.Button(art_actions, text="Refresh", command=refresh_dist).pack(side="left")
    ttk.Button(art_actions, text="Open", command=lambda: open_path(current_artifact())).pack(side="left", padx=(8, 0))
    ttk.Button(art_actions, text="Reveal", command=lambda: reveal_path(current_artifact())).pack(side="left", padx=(8, 0))
    ttk.Button(art_actions, text="Copy Path", command=lambda: copy_text(str(current_artifact()), "artifact path") if current_artifact() else None).pack(side="left", padx=(8, 0))

    artifacts_detail_frame = ttk.Frame(artifacts_tab, style="Card.TFrame", padding=16)
    artifacts_detail_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    ttk.Label(artifacts_detail_frame, text="Artifact Details", style="CardTitle.TLabel").pack(anchor="w")
    artifact_details = tk.Text(artifacts_detail_frame, bg="#0d1826", fg="#eef6ff", insertbackground="#eef6ff", relief="flat", wrap="word")
    artifact_details.pack(fill="both", expand=True, pady=(8, 0))

    def on_artifact_select(_event: object = None) -> None:
        sel = artifact_list.curselection()
        if not sel:
            return
        selected_artifact.set(artifact_list.get(sel[0]))
        render_artifact_details()

    artifact_list.bind("<<ListboxSelect>>", on_artifact_select)

    release_card = ttk.Frame(releases_tab, style="Card.TFrame", padding=16)
    release_card.pack(fill="both", expand=True)
    ttk.Label(release_card, text="Release Manager", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(release_card, text="Prepare what GitHub users need: release links, bundle zips, and tag workflow.", style="CardBody.TLabel").pack(anchor="w", pady=(4, 10))
    rel_actions = ttk.Frame(release_card)
    rel_actions.pack(anchor="w")
    ttk.Button(rel_actions, text="Open Releases", command=lambda: open_url(RELEASES_URL)).pack(side="left")
    ttk.Button(rel_actions, text="Copy Releases Link", command=lambda: copy_text(RELEASES_URL, "releases link")).pack(side="left", padx=(8, 0))
    ttk.Button(rel_actions, text="Copy Tag Commands", command=lambda: copy_text(TAG_CMDS, "tag commands")).pack(side="left", padx=(8, 0))
    ttk.Button(rel_actions, text="Create Share Zip", command=lambda: run_and_render("zero os share package", "Share zip complete")).pack(side="left", padx=(8, 0))
    release_text = tk.Text(release_card, height=22, bg="#0d1826", fg="#eef6ff", insertbackground="#eef6ff", relief="flat", wrap="word")
    release_text.pack(fill="both", expand=True, pady=(10, 0))
    release_text.insert(
        "1.0",
        "Recommended release flow:\n\n"
        "1. Build the share zip.\n"
        "2. Push a version tag like v1.0.0.\n"
        "3. Let GitHub Actions attach the bundle zip to the release.\n"
        "4. Point users to the Releases page.\n\n"
        f"Repository: {REPO_URL}\n"
        f"Releases: {RELEASES_URL}\n"
        f"Tag commands:\n{TAG_CMDS}\n",
    )

    github_card = ttk.Frame(github_tab, style="Card.TFrame", padding=16)
    github_card.pack(fill="both", expand=True)
    ttk.Label(github_card, text="GitHub Share Page", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(github_card, text="Simple share controls for GitHub users and maintainers.", style="CardBody.TLabel").pack(anchor="w", pady=(4, 10))
    gh_actions = ttk.Frame(github_card)
    gh_actions.pack(anchor="w")
    ttk.Button(gh_actions, text="Copy Clone Command", command=lambda: copy_text(CLONE_CMD, "clone command")).pack(side="left")
    ttk.Button(gh_actions, text="Copy Repo Link", command=lambda: copy_text(REPO_URL, "repo link")).pack(side="left", padx=(8, 0))
    ttk.Button(gh_actions, text="Copy Releases Link", command=lambda: copy_text(RELEASES_URL, "releases link")).pack(side="left", padx=(8, 0))
    ttk.Button(gh_actions, text="Open GitHub", command=lambda: open_url(REPO_URL)).pack(side="left", padx=(8, 0))
    gh_text = tk.Text(github_card, height=22, bg="#0d1826", fg="#eef6ff", insertbackground="#eef6ff", relief="flat", wrap="word")
    gh_text.pack(fill="both", expand=True, pady=(10, 0))
    gh_text.insert(
        "1.0",
        "Give GitHub users these simplest options:\n\n"
        f"- Clone command: {CLONE_CMD}\n"
        f"- Repo URL: {REPO_URL}\n"
        f"- Releases URL: {RELEASES_URL}\n"
        f"- First run: {FIRST_RUN_CMD}\n"
        f"- Open shell: {OPEN_SHELL_CMD}\n",
    )

    runtime_card = ttk.Frame(runtime_tab, style="Card.TFrame", padding=16)
    runtime_card.pack(fill="both", expand=True)
    ttk.Label(runtime_card, text="Runtime Shortcuts", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(runtime_card, text="Fast native buttons for common local actions.", style="CardBody.TLabel").pack(anchor="w", pady=(4, 10))
    runtime_buttons = ttk.Frame(runtime_card)
    runtime_buttons.pack(anchor="w")
    ttk.Button(runtime_buttons, text="Core Status", command=lambda: run_and_render("core status", "Core status loaded")).pack(side="left")
    ttk.Button(runtime_buttons, text="Security Overview", command=lambda: run_and_render("security overview", "Security overview loaded")).pack(side="left", padx=(8, 0))
    ttk.Button(runtime_buttons, text="GitHub Status", command=lambda: run_and_render("github status", "GitHub status loaded")).pack(side="left", padx=(8, 0))

    about_card = ttk.Frame(about_tab, style="Card.TFrame", padding=16)
    about_card.pack(fill="both", expand=True)
    ttk.Label(about_card, text="About This Native UI", style="CardTitle.TLabel").pack(anchor="w")
    about_text = tk.Text(about_card, height=18, bg="#0d1826", fg="#eef6ff", insertbackground="#eef6ff", relief="flat", wrap="word")
    about_text.pack(fill="both", expand=True, pady=(8, 0))
    about_text.insert(
        "1.0",
        "This is a native desktop surface for Zero OS sharing tasks.\n\n"
        "Use it to:\n"
        "- copy clone and setup commands\n"
        "- open the GitHub repo and Releases page\n"
        "- build local share bundles and zip packages\n"
        "- inspect exported artifacts and manifests\n"
        "- prepare release links and tag commands\n"
        "- open the dist folder\n"
        "- run common runtime checks\n",
    )

    refresh_dist()
    app.mainloop()
    return {"ok": True, "launched": True, "ui": "native-zero-ui"}

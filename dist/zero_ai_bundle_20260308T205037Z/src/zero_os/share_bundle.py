from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


EXCLUDE_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
}

EXCLUDE_ROOTS = {
    ".zero_os",
    "dist",
}

EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
}

ZERO_AI_INCLUDE_ROOTS = (
    "src/zero_os",
    "tests",
    "docs",
)

ZERO_AI_INCLUDE_FILES = (
    "README.md",
    "ROADMAP.md",
    "zero_os_shell.html",
    "index.html",
    "zero_os_ui.py",
    "zero_os_ui.sh",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _should_skip(path: Path, base: Path) -> bool:
    rel = path.relative_to(base)
    parts = set(rel.parts)
    if parts.intersection(EXCLUDE_PARTS):
        return True
    if rel.parts and rel.parts[0] in EXCLUDE_ROOTS:
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    return False


def _copy_tree(src: Path, dest: Path) -> dict:
    copied_files = 0
    copied_dirs = 0
    skipped_locked = []
    for path in src.rglob("*"):
        if _should_skip(path, src):
            continue
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            copied_dirs += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, target)
            copied_files += 1
        except PermissionError:
            skipped_locked.append(str(rel).replace("\\", "/"))
    return {"copied_files": copied_files, "copied_dirs": copied_dirs, "skipped_locked": skipped_locked}


def _copy_selected(base: Path, dest: Path, roots: tuple[str, ...], files: tuple[str, ...]) -> dict:
    copied_files = 0
    copied_dirs = 0
    skipped_missing = []
    skipped_locked = []

    for rel_file in files:
        src = base / rel_file
        if not src.exists():
            skipped_missing.append(rel_file.replace("\\", "/"))
            continue
        target = dest / rel_file
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, target)
            copied_files += 1
        except PermissionError:
            skipped_locked.append(rel_file.replace("\\", "/"))

    for rel_root in roots:
        src_root = base / rel_root
        if not src_root.exists():
            skipped_missing.append(rel_root.replace("\\", "/"))
            continue
        for path in src_root.rglob("*"):
            if _should_skip(path, base):
                continue
            rel = path.relative_to(base)
            target = dest / rel
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                copied_dirs += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(path, target)
                copied_files += 1
            except PermissionError:
                skipped_locked.append(str(rel).replace("\\", "/"))

    return {
        "copied_files": copied_files,
        "copied_dirs": copied_dirs,
        "skipped_missing": skipped_missing,
        "skipped_locked": skipped_locked,
    }


def _strictify_manifest(manifest: dict) -> dict:
    blocked = bool(manifest.get("skipped_missing") or manifest.get("skipped_locked"))
    if blocked:
        manifest["ok"] = False
        manifest["strict"] = True
        manifest["reason"] = "strict_export_blocked"
    else:
        manifest["strict"] = True
    return manifest


def export_bundle(cwd: str) -> dict:
    base = Path(cwd).resolve()
    dist = base / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    bundle_dir = dist / f"zero_os_bundle_{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    stats = _copy_tree(base, bundle_dir)
    manifest = {
        "ok": True,
        "generated_utc": stamp,
        "source": str(base),
        "bundle_dir": str(bundle_dir),
        "excluded_roots": sorted(EXCLUDE_ROOTS),
        "excluded_parts": sorted(EXCLUDE_PARTS),
        **stats,
    }
    (bundle_dir / "zero_os_share_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def share_package(cwd: str) -> dict:
    exported = export_bundle(cwd)
    if not exported.get("ok", False):
        return exported
    bundle_dir = Path(str(exported["bundle_dir"]))
    zip_base = bundle_dir.parent / bundle_dir.name
    archive_path = shutil.make_archive(str(zip_base), "zip", root_dir=bundle_dir.parent, base_dir=bundle_dir.name)
    return {
        "ok": True,
        "bundle_dir": str(bundle_dir),
        "archive_path": archive_path,
        "generated_utc": exported["generated_utc"],
        "copied_files": exported["copied_files"],
        "copied_dirs": exported["copied_dirs"],
    }


def export_zero_ai_bundle(cwd: str) -> dict:
    base = Path(cwd).resolve()
    dist = base / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    bundle_dir = dist / f"zero_ai_bundle_{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    stats = _copy_selected(base, bundle_dir, ZERO_AI_INCLUDE_ROOTS, ZERO_AI_INCLUDE_FILES)
    manifest = {
        "ok": True,
        "generated_utc": stamp,
        "source": str(base),
        "bundle_dir": str(bundle_dir),
        "bundle_kind": "zero_ai",
        "included_roots": list(ZERO_AI_INCLUDE_ROOTS),
        "included_files": list(ZERO_AI_INCLUDE_FILES),
        **stats,
    }
    (bundle_dir / "zero_ai_share_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def export_zero_ai_bundle_strict(cwd: str) -> dict:
    return _strictify_manifest(export_zero_ai_bundle(cwd))


def share_zero_ai_package(cwd: str) -> dict:
    exported = export_zero_ai_bundle(cwd)
    if not exported.get("ok", False):
        return exported
    bundle_dir = Path(str(exported["bundle_dir"]))
    zip_base = bundle_dir.parent / bundle_dir.name
    archive_path = shutil.make_archive(str(zip_base), "zip", root_dir=bundle_dir.parent, base_dir=bundle_dir.name)
    return {
        "ok": True,
        "bundle_dir": str(bundle_dir),
        "archive_path": archive_path,
        "generated_utc": exported["generated_utc"],
        "bundle_kind": "zero_ai",
        "copied_files": exported["copied_files"],
        "copied_dirs": exported["copied_dirs"],
    }


def share_zero_ai_package_strict(cwd: str) -> dict:
    exported = export_zero_ai_bundle_strict(cwd)
    if not exported.get("ok", False):
        return exported
    bundle_dir = Path(str(exported["bundle_dir"]))
    zip_base = bundle_dir.parent / bundle_dir.name
    archive_path = shutil.make_archive(str(zip_base), "zip", root_dir=bundle_dir.parent, base_dir=bundle_dir.name)
    return {
        "ok": True,
        "bundle_dir": str(bundle_dir),
        "archive_path": archive_path,
        "generated_utc": exported["generated_utc"],
        "bundle_kind": "zero_ai",
        "strict": True,
        "copied_files": exported["copied_files"],
        "copied_dirs": exported["copied_dirs"],
    }

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path


def _root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "store"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _registry_path(cwd: str) -> Path:
    return _root(cwd) / "registry.json"


def _load_registry(cwd: str) -> dict:
    p = _registry_path(cwd)
    if not p.exists():
        data = {"apps": []}
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"apps": []}


def _save_registry(cwd: str, data: dict) -> None:
    _registry_path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_platform(target_override: str = "") -> str:
    if target_override.strip():
        return target_override.strip().lower()
    s = platform.system().lower()
    if "windows" in s:
        return "windows"
    if "darwin" in s:
        return "macos"
    if "linux" in s:
        return "linux"
    return "unknown"


def detect_device() -> dict:
    arch = platform.machine().lower()
    cpu = "x86_64" if any(k in arch for k in ("x86_64", "amd64")) else arch
    return {
        "os": detect_platform(),
        "cpu": cpu or "unknown",
        "architecture": cpu or "unknown",
        "permissions": "standard",
        "security": "baseline",
    }


def _read_manifest(pdir: Path) -> tuple[dict | None, str]:
    manifest_path = pdir / "manifest.json"
    if not manifest_path.exists():
        return None, f"manifest missing: {manifest_path}"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8", errors="replace")), ""
    except Exception:
        return None, "invalid manifest json"


def _normalize_targets(manifest: dict) -> dict:
    # v1 compatibility: manifest.targets map
    if isinstance(manifest.get("targets"), dict):
        return {str(k).lower(): str(v) for k, v in manifest["targets"].items()}
    # UAP layout default map
    return {
        "windows": "builds/windows_x64.exe",
        "linux": "builds/linux_x64.bin",
        "macos": "builds/macos_arm.app",
        "android": "builds/android.apk",
        "ios": "builds/ios.ipa",
        "web": "builds/web.wasm",
    }


def validate_package(cwd: str, package_dir: str) -> dict:
    root = Path(cwd).resolve()
    pdir = (root / package_dir).resolve()
    manifest, err = _read_manifest(pdir)
    if manifest is None:
        return {"ok": False, "reason": err}

    name = str(manifest.get("name", "")).strip()
    version = str(manifest.get("version", "")).strip()
    if not name or not version:
        return {"ok": False, "reason": "manifest requires name and version"}

    targets = _normalize_targets(manifest)
    files: dict[str, dict] = {}
    missing: list[str] = []
    for os_key, rel in targets.items():
        fp = (pdir / rel).resolve()
        if not fp.exists():
            continue
        files[os_key] = {"path": str(fp), "sha256": _sha256(fp), "size": fp.stat().st_size}
    if not files:
        missing = list(targets.keys())

    metadata_dir = pdir / "metadata"
    signature_path = pdir / "signature" / "developer.sig"
    permissions_path = metadata_dir / "permissions.json"
    permissions = {}
    if permissions_path.exists():
        try:
            permissions = json.loads(permissions_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            permissions = {}

    sec = {
        "signature_present": signature_path.exists(),
        "permissions_present": permissions_path.exists(),
        "malware_scan": "not_run",
    }
    ok = bool(files) and sec["signature_present"]
    return {
        "ok": ok,
        "name": name,
        "version": version,
        "files": files,
        "missing": missing,
        "metadata": {
            "icon": str((metadata_dir / "icon.png").resolve()),
            "description": str((metadata_dir / "description.md").resolve()),
            "permissions": permissions,
        },
        "security": sec,
        "layers": {
            "identity": "developer.sig",
            "package": "UAP",
            "compatibility": "target-matching",
            "runtime": "native|compatibility|wasm",
            "distribution": "registry+storage",
        },
    }


def publish_package(cwd: str, package_dir: str) -> dict:
    v = validate_package(cwd, package_dir)
    if not v.get("ok", False):
        return {"ok": False, "reason": "validation failed", "validation": v}
    reg = _load_registry(cwd)
    apps = [a for a in reg.get("apps", []) if not (a.get("name") == v["name"] and a.get("version") == v["version"])]
    apps.append(
        {
            "name": v["name"],
            "version": v["version"],
            "package_dir": str((Path(cwd).resolve() / package_dir).resolve()),
            "targets": v["files"],
            "metadata": v["metadata"],
            "security": v["security"],
        }
    )
    reg["apps"] = apps
    _save_registry(cwd, reg)
    return {"ok": True, "published": {"name": v["name"], "version": v["version"]}, "registry_total": len(apps)}


def list_packages(cwd: str) -> dict:
    reg = _load_registry(cwd)
    return {"ok": True, "total": len(reg.get("apps", [])), "apps": reg.get("apps", [])}


def _fallback_for(os_name: str) -> dict:
    # Priority: compatibility layer, container, wasm, virtualization
    if os_name == "linux":
        return {"method": "compatibility", "engine": "wine-proton"}
    if os_name in {"windows", "macos"}:
        return {"method": "container", "engine": "oci-sandbox"}
    if os_name in {"android", "ios"}:
        return {"method": "runtime", "engine": "wasm"}
    return {"method": "virtualization", "engine": "vm"}


def resolve_package(cwd: str, name: str, target_os: str = "", cpu: str = "", architecture: str = "", security: str = "") -> dict:
    reg = _load_registry(cwd)
    device = detect_device()
    os_name = detect_platform(target_os) if target_os else device["os"]
    if cpu:
        device["cpu"] = cpu
    if architecture:
        device["architecture"] = architecture
    if security:
        device["security"] = security

    candidates = [a for a in reg.get("apps", []) if str(a.get("name", "")).lower() == name.strip().lower()]
    if not candidates:
        return {"ok": False, "reason": "app not found", "name": name}
    app = sorted(candidates, key=lambda x: str(x.get("version", "")))[-1]
    target = app.get("targets", {}).get(os_name)
    if target:
        return {
            "ok": True,
            "name": app["name"],
            "version": app["version"],
            "device": device,
            "os": os_name,
            "delivery": "native",
            "target": target,
        }
    fb = _fallback_for(os_name)
    web = app.get("targets", {}).get("web")
    if web:
        return {
            "ok": True,
            "name": app["name"],
            "version": app["version"],
            "device": device,
            "os": os_name,
            "delivery": "fallback-web",
            "target": web,
            "fallback": {"method": "runtime", "engine": "wasm"},
        }
    return {
        "ok": False,
        "reason": "target not available",
        "name": name,
        "os": os_name,
        "fallback": fb,
    }


def security_scan(cwd: str, name: str) -> dict:
    reg = _load_registry(cwd)
    candidates = [a for a in reg.get("apps", []) if str(a.get("name", "")).lower() == name.strip().lower()]
    if not candidates:
        return {"ok": False, "reason": "app not found", "name": name}
    app = sorted(candidates, key=lambda x: str(x.get("version", "")))[-1]
    sec = app.get("security", {})
    risky = not bool(sec.get("signature_present", False))
    return {
        "ok": not risky,
        "name": app["name"],
        "version": app["version"],
        "checks": {
            "developer_signing": bool(sec.get("signature_present", False)),
            "permission_system": bool(sec.get("permissions_present", False)),
            "malware_scan": "placeholder-pass",
            "runtime_monitoring": "placeholder-on",
            "sandboxing": "client-enforced",
        },
    }

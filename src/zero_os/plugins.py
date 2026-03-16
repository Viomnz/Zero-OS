"""Native plugin capability loader and registry."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import re
import secrets
import shutil
import sys
from typing import Any

from zero_os.types import Capability

MANIFEST_FILENAME = "plugin.json"
DEFAULT_ENTRY = "plugin.py"
DEFAULT_FACTORY = "get_capability"
SUPPORTED_SCHEMA_VERSION = 1
PLUGIN_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
FACTORY_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class PluginSpec:
    name: str
    kind: str
    root_path: Path
    entry_path: Path
    manifest_path: Path | None
    version: str
    description: str
    factory: str
    managed: bool
    distribution: str = "private-local"
    local_only: bool = True
    mutable: bool = True
    issues: tuple[str, ...] = ()


@dataclass
class PluginInspection:
    spec: PluginSpec
    enabled: bool
    structural_valid: bool
    runtime_valid: bool
    signature_valid: bool | None
    trust: str
    load_allowed: bool
    issues: list[str]
    capability_name: str | None = None
    capability: Capability | None = None
    registry_entry: dict[str, Any] | None = None


def load_plugins(cwd: str) -> tuple[Capability, ...]:
    loaded: list[Capability] = []
    for inspection in _collect_plugin_inspections(cwd, runtime_probe=True):
        if inspection.load_allowed and inspection.capability is not None:
            loaded.append(inspection.capability)
    return tuple(loaded)


def plugin_status(cwd: str, name: str | None = None) -> dict:
    inspections = _filter_inspections(_collect_plugin_inspections(cwd, runtime_probe=True), name)
    if name and not inspections:
        return {"ok": False, "reason": "plugin missing", "plugin": name}
    payload = _status_payload(inspections)
    payload["ok"] = True
    return payload


def plugin_validate(cwd: str, name: str | None = None) -> dict:
    inspections = _filter_inspections(_collect_plugin_inspections(cwd, runtime_probe=True), name)
    if name and not inspections:
        return {"ok": False, "reason": "plugin missing", "plugin": name}
    blocking = [
        item
        for item in inspections
        if item.enabled and (not item.structural_valid or not item.runtime_valid or item.signature_valid is False)
    ]
    payload = _status_payload(inspections)
    payload["ok"] = not blocking
    payload["validated_count"] = len(inspections)
    return payload


def plugin_scaffold(cwd: str, name: str) -> dict:
    normalized = name.strip()
    if not _is_valid_plugin_name(normalized):
        return {"ok": False, "reason": "plugin name must match [A-Za-z0-9._-]+"}
    root = _plugins_root(cwd, create=True)
    target_dir = root / normalized
    legacy_path = root / f"{normalized}.py"
    if target_dir.exists() or legacy_path.exists():
        return {"ok": False, "reason": "plugin already exists", "plugin": normalized}

    target_dir.mkdir(parents=True, exist_ok=False)
    manifest = _default_manifest(normalized)
    _save_json(target_dir / MANIFEST_FILENAME, manifest)
    _write_plugin_template(target_dir / DEFAULT_ENTRY, normalized)
    _update_registry(
        cwd,
        normalized,
        {
            "enabled": True,
            "managed": True,
            "installed_utc": _utc_now(),
            "install_source": "scaffold",
            "updated_utc": _utc_now(),
        },
    )
    signature = plugin_sign(cwd, normalized)
    return {
        "ok": True,
        "plugin": normalized,
        "path": str(target_dir),
        "manifest_path": str(target_dir / MANIFEST_FILENAME),
        "entry_path": str(target_dir / DEFAULT_ENTRY),
        "signature": signature,
    }


def plugin_install_local(cwd: str, source_path: str) -> dict:
    source = _resolve_external_path(cwd, source_path)
    if not source.exists():
        return {"ok": False, "reason": "source path missing", "source": str(source)}

    root = _plugins_root(cwd, create=True)
    if source.is_dir():
        manifest_path = source / MANIFEST_FILENAME
        if manifest_path.exists():
            manifest = _load_json(manifest_path, {})
            issues, manifest_name, entry_name, factory_name, version, description, distribution, local_only, mutable = _manifest_details(source, manifest)
            if issues:
                return {"ok": False, "reason": "invalid plugin manifest", "issues": issues, "source": str(source)}
            target_dir = root / manifest_name
            legacy_path = root / f"{manifest_name}.py"
            if target_dir.exists() or legacy_path.exists():
                return {"ok": False, "reason": "plugin already exists", "plugin": manifest_name}
            shutil.copytree(source, target_dir)
            installed_name = manifest_name
            entry_path = target_dir / entry_name
            if not entry_path.exists():
                return {"ok": False, "reason": "installed entry missing", "plugin": installed_name}
        else:
            detected_entry, detect_issue = _detect_local_directory_entry(source)
            if detect_issue:
                return {"ok": False, "reason": detect_issue, "source": str(source)}
            installed_name = _normalize_install_name(source.name)
            if not installed_name:
                return {"ok": False, "reason": "local directory name cannot be normalized into a plugin id", "source": str(source)}
            target_dir = root / installed_name
            legacy_path = root / f"{installed_name}.py"
            if target_dir.exists() or legacy_path.exists():
                return {"ok": False, "reason": "plugin already exists", "plugin": installed_name}
            shutil.copytree(source, target_dir)
            _save_json(
                target_dir / MANIFEST_FILENAME,
                _default_manifest(
                    installed_name,
                    description=f"Imported from local directory {source.name}",
                    entry=detected_entry,
                ),
            )
    else:
        if source.suffix.lower() != ".py":
            return {"ok": False, "reason": "local install expects a .py file or plugin directory", "source": str(source)}
        installed_name = _normalize_install_name(source.stem)
        if not installed_name:
            return {"ok": False, "reason": "plugin file stem cannot be normalized into a plugin id", "plugin": source.stem}
        target_dir = root / installed_name
        legacy_path = root / f"{installed_name}.py"
        if target_dir.exists() or legacy_path.exists():
            return {"ok": False, "reason": "plugin already exists", "plugin": installed_name}
        target_dir.mkdir(parents=True, exist_ok=False)
        shutil.copy2(source, target_dir / DEFAULT_ENTRY)
        _save_json(target_dir / MANIFEST_FILENAME, _default_manifest(installed_name, description=f"Imported from {source.name}"))

    _update_registry(
        cwd,
        installed_name,
        {
            "enabled": True,
            "managed": True,
            "installed_utc": _utc_now(),
            "install_source": str(source),
            "updated_utc": _utc_now(),
        },
    )
    signature = plugin_sign(cwd, installed_name)
    return {
        "ok": True,
        "plugin": installed_name,
        "path": str(target_dir),
        "signature": signature,
    }


def plugin_enable(cwd: str, name: str) -> dict:
    return _set_enabled(cwd, name, True)


def plugin_disable(cwd: str, name: str) -> dict:
    return _set_enabled(cwd, name, False)


def plugin_sign(cwd: str, name: str) -> dict:
    spec = _find_plugin_spec(cwd, name)
    if spec is None:
        return {"ok": False, "reason": "plugin missing", "plugin": name}
    digest, file_count = _hash_plugin_source(spec)
    signature = hmac.new(_key(cwd, "plugin_sign"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    record = {
        "plugin": spec.name,
        "kind": spec.kind,
        "path": str(spec.root_path if spec.kind == "native" else spec.entry_path),
        "sha256": digest,
        "signature": signature,
        "file_count": file_count,
        "signed_utc": _utc_now(),
    }
    signatures = _load_json(_signatures_path(cwd), {"plugins": {}})
    signatures.setdefault("plugins", {})
    signatures["plugins"][spec.name] = record
    _save_json(_signatures_path(cwd), signatures)
    return {"ok": True, **record}


def plugin_verify(cwd: str, name: str) -> dict:
    spec = _find_plugin_spec(cwd, name)
    if spec is None:
        return {"ok": False, "reason": "plugin missing", "plugin": name}
    signatures = _load_json(_signatures_path(cwd), {"plugins": {}})
    record = signatures.get("plugins", {}).get(spec.name)
    if not record:
        return {"ok": False, "reason": "no signature", "plugin": spec.name}
    digest, file_count = _hash_plugin_source(spec)
    signature = hmac.new(_key(cwd, "plugin_sign"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    valid = hmac.compare_digest(signature, record.get("signature", ""))
    return {
        "ok": valid,
        "plugin": spec.name,
        "kind": spec.kind,
        "sha256": digest,
        "file_count": file_count,
        "reason": "signature valid" if valid else "signature mismatch",
    }


def _set_enabled(cwd: str, name: str, enabled: bool) -> dict:
    spec = _find_plugin_spec(cwd, name)
    if spec is None:
        return {"ok": False, "reason": "plugin missing", "plugin": name}
    _update_registry(
        cwd,
        spec.name,
        {
            "enabled": enabled,
            "updated_utc": _utc_now(),
        },
    )
    return {
        "ok": True,
        "plugin": spec.name,
        "enabled": enabled,
        "status": plugin_status(cwd, spec.name),
    }


def _collect_plugin_inspections(cwd: str, runtime_probe: bool) -> list[PluginInspection]:
    registry = _load_json(_registry_path(cwd), {"plugins": {}})
    signatures = _load_json(_signatures_path(cwd), {"plugins": {}})
    inspections: list[PluginInspection] = []
    for spec in _discover_plugins(cwd):
        entry = registry.get("plugins", {}).get(spec.name, {})
        enabled = bool(entry.get("enabled", True))
        issues = list(spec.issues)
        structural_valid = not issues
        capability = None
        capability_name = None
        runtime_valid = False
        if structural_valid and runtime_probe:
            capability, runtime_issue = _instantiate_capability(spec)
            if runtime_issue:
                issues.append(runtime_issue)
            else:
                runtime_valid = True
                capability_name = getattr(capability, "name", spec.name)
        elif structural_valid:
            runtime_valid = True

        signature_record = signatures.get("plugins", {}).get(spec.name)
        signature_valid = _signature_state(signature_record, spec, cwd)
        trust = "signed" if signature_valid is True else "tampered" if signature_valid is False else "unsigned"
        load_allowed = enabled and structural_valid and runtime_valid and signature_valid is not False
        inspections.append(
            PluginInspection(
                spec=spec,
                enabled=enabled,
                structural_valid=structural_valid,
                runtime_valid=runtime_valid,
                signature_valid=signature_valid,
                trust=trust,
                load_allowed=load_allowed,
                issues=issues,
                capability_name=capability_name,
                capability=capability,
                registry_entry=entry,
            )
        )
    return inspections


def _inspection_payload(item: PluginInspection) -> dict:
    payload = {
        "name": item.spec.name,
        "kind": item.spec.kind,
        "path": str(item.spec.root_path if item.spec.kind == "native" else item.spec.entry_path),
        "entry_path": str(item.spec.entry_path),
        "managed": item.spec.managed,
        "version": item.spec.version,
        "description": item.spec.description,
        "distribution": item.spec.distribution,
        "local_only": item.spec.local_only,
        "mutable": item.spec.mutable,
        "enabled": item.enabled,
        "structural_valid": item.structural_valid,
        "runtime_valid": item.runtime_valid,
        "signature_valid": item.signature_valid,
        "trust": item.trust,
        "load_allowed": item.load_allowed,
        "issues": item.issues,
        "capability_name": item.capability_name,
    }
    if item.registry_entry:
        payload["registry"] = item.registry_entry
    return payload


def _status_payload(inspections: list[PluginInspection]) -> dict:
    plugins = [_inspection_payload(item) for item in inspections]
    invalid_count = sum(1 for item in inspections if not item.structural_valid or not item.runtime_valid or item.signature_valid is False)
    return {
        "plugin_count": len(plugins),
        "loadable_count": sum(1 for item in inspections if item.load_allowed),
        "invalid_count": invalid_count,
        "signed_count": sum(1 for item in inspections if item.signature_valid is True),
        "plugins": plugins,
    }


def _discover_plugins(cwd: str) -> list[PluginSpec]:
    root = _plugins_root(cwd)
    if not root.exists() or not root.is_dir():
        return []

    specs: list[PluginSpec] = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            specs.append(_native_spec_from_directory(child))
    for file_path in sorted(root.glob("*.py")):
        specs.append(
            PluginSpec(
                name=file_path.stem,
                kind="legacy",
                root_path=file_path.parent,
                entry_path=file_path,
                manifest_path=None,
                version="legacy",
                description="Legacy unmanaged plugin",
                factory=DEFAULT_FACTORY,
                managed=False,
                distribution="private-local",
                local_only=True,
                mutable=True,
            )
        )

    collisions: dict[str, int] = {}
    for spec in specs:
        collisions[spec.name.lower()] = collisions.get(spec.name.lower(), 0) + 1

    updated: list[PluginSpec] = []
    for spec in specs:
        issues = list(spec.issues)
        if collisions.get(spec.name.lower(), 0) > 1:
            issues.append("plugin name collision")
        updated.append(replace(spec, issues=tuple(dict.fromkeys(issues))))
    return updated


def _native_spec_from_directory(plugin_dir: Path) -> PluginSpec:
    manifest_path = plugin_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        entry_path = plugin_dir / DEFAULT_ENTRY
        issues = [f"missing {MANIFEST_FILENAME}"]
        if not entry_path.exists():
            issues.append(f"missing entry: {DEFAULT_ENTRY}")
        return PluginSpec(
            name=plugin_dir.name,
            kind="native",
            root_path=plugin_dir,
            entry_path=entry_path,
            manifest_path=None,
            version="0.0.0",
            description="",
            factory=DEFAULT_FACTORY,
            managed=True,
            distribution="private-local",
            local_only=True,
            mutable=True,
            issues=tuple(issues),
        )

    manifest = _load_json(manifest_path, {})
    issues, manifest_name, entry_name, factory_name, version, description, distribution, local_only, mutable = _manifest_details(plugin_dir, manifest)
    name = manifest_name if manifest_name and manifest_name == plugin_dir.name else plugin_dir.name
    return PluginSpec(
        name=name,
        kind="native",
        root_path=plugin_dir,
        entry_path=plugin_dir / entry_name,
        manifest_path=manifest_path,
        version=version,
        description=description,
        factory=factory_name,
        managed=True,
        distribution=distribution,
        local_only=local_only,
        mutable=mutable,
        issues=tuple(issues),
    )


def _manifest_details(
    plugin_dir: Path,
    manifest: dict[str, Any],
) -> tuple[list[str], str, str, str, str, str, str, bool, bool]:
    issues: list[str] = []
    if not isinstance(manifest, dict):
        return (["invalid plugin manifest"], plugin_dir.name, DEFAULT_ENTRY, DEFAULT_FACTORY, "0.0.0", "", "private-local", True, True)

    schema_version = manifest.get("schema_version", SUPPORTED_SCHEMA_VERSION)
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        issues.append(f"unsupported schema_version: {schema_version}")

    manifest_name = manifest.get("name", plugin_dir.name)
    if not isinstance(manifest_name, str) or not _is_valid_plugin_name(manifest_name):
        issues.append("manifest name must match [A-Za-z0-9._-]+")
        manifest_name = plugin_dir.name
    elif manifest_name != plugin_dir.name:
        issues.append("manifest name must match plugin directory")

    entry_name = manifest.get("entry", DEFAULT_ENTRY)
    if not isinstance(entry_name, str) or not _is_safe_relative_path(entry_name):
        issues.append("manifest entry must be a safe relative path")
        entry_name = DEFAULT_ENTRY
    entry_path = plugin_dir / entry_name
    if not entry_path.exists():
        issues.append(f"missing entry: {entry_name}")

    factory_name = manifest.get("factory", DEFAULT_FACTORY)
    if not isinstance(factory_name, str) or not FACTORY_NAME_RE.fullmatch(factory_name):
        issues.append("manifest factory must be a valid identifier")
        factory_name = DEFAULT_FACTORY

    version = manifest.get("version", "0.1.0")
    if not isinstance(version, str) or not version.strip():
        issues.append("manifest version must be a non-empty string")
        version = "0.1.0"

    description = manifest.get("description", "")
    if not isinstance(description, str):
        issues.append("manifest description must be a string")
        description = ""

    distribution = manifest.get("distribution", "private-local")
    if not isinstance(distribution, str) or not distribution.strip():
        issues.append("manifest distribution must be a non-empty string")
        distribution = "private-local"

    local_only = manifest.get("local_only", True)
    if not isinstance(local_only, bool):
        issues.append("manifest local_only must be true or false")
        local_only = True

    mutable = manifest.get("mutable", True)
    if not isinstance(mutable, bool):
        issues.append("manifest mutable must be true or false")
        mutable = True

    return issues, manifest_name, entry_name, factory_name, version, description, distribution, local_only, mutable


def _instantiate_capability(spec: PluginSpec) -> tuple[Capability | None, str | None]:
    module, load_issue = _load_module(spec)
    if load_issue:
        return (None, load_issue)
    factory = getattr(module, spec.factory, None)
    if not callable(factory):
        return (None, f"missing callable factory: {spec.factory}")
    try:
        capability = factory()
    except Exception as exc:
        return (None, f"factory failed: {exc.__class__.__name__}")
    if not hasattr(capability, "can_handle") or not hasattr(capability, "run"):
        return (None, "factory returned invalid capability")
    return (capability, None)


def _load_module(spec: PluginSpec) -> tuple[Any | None, str | None]:
    module_name = _module_name_for(spec)
    _clear_module_family(module_name)
    if spec.kind == "native":
        import_spec = importlib.util.spec_from_file_location(
            module_name,
            spec.entry_path,
            submodule_search_locations=[str(spec.root_path)],
        )
    else:
        import_spec = importlib.util.spec_from_file_location(module_name, spec.entry_path)
    if import_spec is None or import_spec.loader is None:
        return (None, "failed to build module spec")
    module = importlib.util.module_from_spec(import_spec)
    sys.modules[module_name] = module
    try:
        import_spec.loader.exec_module(module)
    except Exception as exc:
        _clear_module_family(module_name)
        return (None, f"entry import failed: {exc.__class__.__name__}")
    return (module, None)


def _module_name_for(spec: PluginSpec) -> str:
    digest = hashlib.sha256(str(spec.entry_path).encode("utf-8")).hexdigest()[:12]
    prefix = "native" if spec.kind == "native" else "legacy"
    return f"zero_os_{prefix}_plugin_{digest}"


def _clear_module_family(prefix: str) -> None:
    for name in [item for item in sys.modules if item == prefix or item.startswith(f"{prefix}.")]:
        sys.modules.pop(name, None)


def _signature_state(record: dict[str, Any] | None, spec: PluginSpec, cwd: str) -> bool | None:
    if not record:
        return None
    digest, _ = _hash_plugin_source(spec)
    signature = hmac.new(_key(cwd, "plugin_sign"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, record.get("signature", ""))


def _hash_plugin_source(spec: PluginSpec) -> tuple[str, int]:
    if spec.kind == "legacy":
        data = spec.entry_path.read_bytes()
        return (hashlib.sha256(data).hexdigest(), 1)

    hasher = hashlib.sha256()
    file_count = 0
    for file_path in sorted(spec.root_path.rglob("*")):
        if not file_path.is_file():
            continue
        if "__pycache__" in file_path.parts or file_path.suffix == ".pyc":
            continue
        relative = file_path.relative_to(spec.root_path).as_posix()
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(file_path.read_bytes())
        hasher.update(b"\0")
        file_count += 1
    return (hasher.hexdigest(), file_count)


def _find_plugin_spec(cwd: str, name: str) -> PluginSpec | None:
    wanted = name.strip().lower()
    for spec in _discover_plugins(cwd):
        if spec.name.lower() == wanted:
            return spec
    return None


def _filter_inspections(inspections: list[PluginInspection], name: str | None) -> list[PluginInspection]:
    if not name:
        return inspections
    wanted = name.strip().lower()
    return [item for item in inspections if item.spec.name.lower() == wanted]


def _resolve_external_path(cwd: str, raw_path: str) -> Path:
    candidate = Path(raw_path.strip().strip("\"'")).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path(cwd).resolve() / candidate).resolve()


def _plugins_root(cwd: str, create: bool = False) -> Path:
    path = Path(cwd).resolve() / "plugins"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _registry_root(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "production"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _registry_path(cwd: str) -> Path:
    return _registry_root(cwd) / "plugin_registry.json"


def _signatures_path(cwd: str) -> Path:
    return _registry_root(cwd) / "plugin_signatures.json"


def _update_registry(cwd: str, name: str, updates: dict[str, Any]) -> None:
    registry = _load_json(_registry_path(cwd), {"plugins": {}})
    registry.setdefault("plugins", {})
    record = dict(registry["plugins"].get(name, {}))
    record.update(updates)
    registry["plugins"][name] = record
    _save_json(_registry_path(cwd), registry)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _key(cwd: str, name: str) -> bytes:
    path = Path(cwd).resolve() / ".zero_os" / "keys" / f"{name}.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_valid_plugin_name(name: str) -> bool:
    return bool(PLUGIN_NAME_RE.fullmatch(name))


def _is_safe_relative_path(raw_path: str) -> bool:
    candidate = Path(raw_path)
    return bool(raw_path) and not candidate.is_absolute() and ".." not in candidate.parts


def _default_manifest(name: str, description: str | None = None, entry: str = DEFAULT_ENTRY) -> dict:
    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "name": name,
        "version": "0.1.0",
        "entry": entry,
        "factory": DEFAULT_FACTORY,
        "description": description or "Native Zero OS capability plugin.",
        "distribution": "private-local",
        "local_only": True,
        "mutable": True,
    }


def _write_plugin_template(path: Path, plugin_name: str) -> None:
    class_name = plugin_name.title().replace("_", "").replace("-", "").replace(".", "")
    template = (
        "from zero_os.types import Result\n\n"
        f"class {class_name}Capability:\n"
        f"    name = \"{plugin_name}\"\n\n"
        "    def can_handle(self, task):\n"
        f"        return task.text.lower().startswith(\"{plugin_name} \")\n\n"
        "    def run(self, task):\n"
        f"        return Result(self.name, \"{plugin_name} plugin executed\")\n\n"
        "def get_capability():\n"
        f"    return {class_name}Capability()\n"
    )
    path.write_text(template, encoding="utf-8")


def _detect_local_directory_entry(source: Path) -> tuple[str | None, str | None]:
    preferred = source / DEFAULT_ENTRY
    if preferred.exists():
        return (DEFAULT_ENTRY, None)
    top_level_py = sorted(
        item.name
        for item in source.iterdir()
        if item.is_file() and item.suffix.lower() == ".py"
    )
    if len(top_level_py) == 1:
        return (top_level_py[0], None)
    return (None, f"local directory install needs {MANIFEST_FILENAME}, {DEFAULT_ENTRY}, or exactly one top-level .py entry file")


def _normalize_install_name(raw_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name.strip())
    normalized = normalized.strip("._-")
    return normalized

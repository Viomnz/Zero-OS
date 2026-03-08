"""Plugin capability loader."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from zero_os.types import Capability


def load_plugins(cwd: str) -> tuple[Capability, ...]:
    plugin_dir = Path(cwd).resolve() / "plugins"
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        return ()

    loaded: list[Capability] = []
    for file in sorted(plugin_dir.glob("*.py")):
        module = _load_module(file)
        if module is None:
            continue
        factory = getattr(module, "get_capability", None)
        if callable(factory):
            try:
                capability = factory()
                if hasattr(capability, "can_handle") and hasattr(capability, "run"):
                    loaded.append(capability)
            except Exception:
                continue
    return tuple(loaded)


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"zero_os_plugin_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


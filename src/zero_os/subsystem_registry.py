from __future__ import annotations

from typing import Any, Callable

_REGISTRIES: dict[str, dict[str, Any]] = {}


def _plane_key(plane: str) -> str:
    key = str(plane or "").strip()
    if not key:
        raise ValueError("subsystem plane is required")
    return key


def _adapter_name(adapter: Any) -> str:
    name = str(getattr(adapter, "name", "") or "").strip()
    if not name:
        raise ValueError("subsystem adapter name is required")
    return name


def register_subsystem_adapter(plane: str, adapter: Any, *, replace: bool = False) -> Any:
    plane_key = _plane_key(plane)
    registry = _REGISTRIES.setdefault(plane_key, {})
    name = _adapter_name(adapter)
    if name in registry and not replace:
        raise ValueError(f"{plane_key} subsystem adapter already registered: {name}")
    registry[name] = adapter
    return adapter


def unregister_subsystem_adapter(plane: str, name: str) -> Any | None:
    registry = _REGISTRIES.get(_plane_key(plane), {})
    return registry.pop(str(name or "").strip(), None)


def subsystem_adapter_map(plane: str) -> dict[str, Any]:
    return dict(_REGISTRIES.get(_plane_key(plane), {}))


def subsystem_adapters(plane: str, *, key: Callable[[Any], Any] | None = None) -> tuple[Any, ...]:
    adapters = list(subsystem_adapter_map(plane).values())
    if key is None:
        adapters.sort(key=lambda adapter: _adapter_name(adapter))
    else:
        adapters.sort(key=key)
    return tuple(adapters)


def subsystem_registry_status() -> dict[str, Any]:
    planes: dict[str, Any] = {}
    for plane, registry in sorted(_REGISTRIES.items()):
        names = sorted(str(name) for name in registry)
        planes[plane] = {
            "count": len(names),
            "names": names,
        }
    return {
        "ok": True,
        "plane_count": len(planes),
        "planes": planes,
    }

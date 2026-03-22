from __future__ import annotations

import json
import re

from zero_os.internet_capability import internet_capability_refresh, internet_capability_status
from zero_os.maintenance_orchestrator import maintenance_refresh, maintenance_run, maintenance_status
from zero_os.plugins import (
    plugin_disable,
    plugin_enable,
    plugin_install_local,
    plugin_scaffold,
    plugin_sign,
    plugin_status,
    plugin_validate,
    plugin_verify,
)
from zero_os.release_readiness import release_readiness_refresh, release_readiness_status
from zero_os.types import Result, Task
from zero_os.world_class_readiness import world_class_readiness_refresh, world_class_readiness_status


def handle_extension_command(task: Task, raw: str, text: str) -> Result | None:
    return (
        _handle_readiness_and_internet(task, raw, text)
        or _handle_plugin_commands(task, raw, text)
    )


def _handle_readiness_and_internet(task: Task, raw: str, text: str) -> Result | None:
    normalized = text.strip()
    if normalized in {"zero ai maintenance", "zero ai maintenance status"}:
        return Result("system", json.dumps(maintenance_status(task.cwd), indent=2))
    if normalized == "zero ai maintenance refresh":
        return Result("system", json.dumps(maintenance_refresh(task.cwd), indent=2))
    if normalized in {"zero ai maintenance run", "zero ai maintenance fix"}:
        return Result("system", json.dumps(maintenance_run(task.cwd), indent=2))
    if normalized in {"zero ai internet", "zero ai internet status", "internet status"}:
        return Result("system", json.dumps(internet_capability_status(task.cwd), indent=2))
    if normalized in {"zero ai internet refresh", "internet refresh"}:
        return Result("system", json.dumps(internet_capability_refresh(task.cwd), indent=2))
    if normalized in {"world class readiness", "zero ai world class readiness", "zero ai world-class readiness"}:
        return Result("system", json.dumps(world_class_readiness_status(task.cwd), indent=2))
    if normalized in {"world class readiness refresh", "zero ai world class readiness refresh"}:
        return Result("system", json.dumps(world_class_readiness_refresh(task.cwd), indent=2))
    if normalized in {"zero ai release readiness", "zero ai release readiness status"}:
        return Result("system", json.dumps(release_readiness_status(task.cwd), indent=2))
    if normalized == "zero ai release readiness refresh":
        return Result("system", json.dumps(release_readiness_refresh(task.cwd), indent=2))
    return None


def _handle_plugin_commands(task: Task, raw: str, text: str) -> Result | None:
    stripped = raw.strip()
    plugin_status_m = re.match(r"^plugin status(?:\s+([A-Za-z0-9._-]+))?$", stripped, flags=re.IGNORECASE)
    if plugin_status_m:
        return Result("system", json.dumps(plugin_status(task.cwd, plugin_status_m.group(1)), indent=2))
    plugin_validate_m = re.match(r"^plugin validate(?:\s+([A-Za-z0-9._-]+))?$", stripped, flags=re.IGNORECASE)
    if plugin_validate_m:
        return Result("system", json.dumps(plugin_validate(task.cwd, plugin_validate_m.group(1)), indent=2))
    plugin_install_local_m = re.match(r"^plugin install local\s+(.+)$", stripped, flags=re.IGNORECASE)
    if plugin_install_local_m:
        return Result("system", json.dumps(plugin_install_local(task.cwd, plugin_install_local_m.group(1)), indent=2))
    plugin_enable_m = re.match(r"^plugin enable\s+([A-Za-z0-9._-]+)$", stripped, flags=re.IGNORECASE)
    if plugin_enable_m:
        return Result("system", json.dumps(plugin_enable(task.cwd, plugin_enable_m.group(1)), indent=2))
    plugin_disable_m = re.match(r"^plugin disable\s+([A-Za-z0-9._-]+)$", stripped, flags=re.IGNORECASE)
    if plugin_disable_m:
        return Result("system", json.dumps(plugin_disable(task.cwd, plugin_disable_m.group(1)), indent=2))
    plugin_sign_m = re.match(r"^plugin sign\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
    if plugin_sign_m:
        return Result("system", json.dumps(plugin_sign(task.cwd, plugin_sign_m.group(1)), indent=2))
    plugin_verify_m = re.match(r"^plugin verify\s+([A-Za-z0-9._-]+)$", text.strip(), flags=re.IGNORECASE)
    if plugin_verify_m:
        return Result("system", json.dumps(plugin_verify(task.cwd, plugin_verify_m.group(1)), indent=2))
    scaffold = re.match(r"^plugin scaffold\s+([A-Za-z0-9._-]+)$", text.strip())
    if scaffold:
        return Result("system", json.dumps(plugin_scaffold(task.cwd, scaffold.group(1)), indent=2))
    return None

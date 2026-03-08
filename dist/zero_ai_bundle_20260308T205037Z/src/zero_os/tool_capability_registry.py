from __future__ import annotations


def capability_registry() -> dict:
    return {
        "local_files": {
            "enabled": True,
            "risk": "medium",
            "actions": ["read", "write", "merge", "inspect"],
        },
        "web_lookup": {
            "enabled": True,
            "risk": "medium",
            "actions": ["search", "fetch", "validate"],
        },
        "shell": {
            "enabled": True,
            "risk": "high",
            "actions": ["run", "inspect"],
        },
        "system_runtime": {
            "enabled": True,
            "risk": "medium",
            "actions": ["status", "recover", "repair", "security", "platform"],
        },
        "native_store": {
            "enabled": True,
            "risk": "high",
            "actions": ["install", "upgrade", "rollback", "release"],
        },
        "backend_ops": {
            "enabled": True,
            "risk": "high",
            "actions": ["backup", "restore", "deploy", "status"],
        },
    }


def registry_status() -> dict:
    data = capability_registry()
    return {
        "ok": True,
        "tools": data,
        "enabled_count": sum(1 for item in data.values() if item.get("enabled")),
    }

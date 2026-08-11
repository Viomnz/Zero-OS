from __future__ import annotations

from pathlib import Path

from zero_os.whole_repo_capability_audit import audit_whole_repository


_PRIORITY = {
    "credential_read": 0,
    "network": 1,
    "process": 2,
    "filesystem_write": 3,
}


def build_remediation_queue(root: str | Path) -> dict:
    audit = audit_whole_repository(root)
    items = list(audit.get("unmediated", []))
    items.sort(
        key=lambda item: (
            _PRIORITY.get(str(item.get("sink_family", "")), 99),
            str(item.get("path", "")),
            int(item.get("line", 0)),
        )
    )
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(str(item.get("sink_family", "unknown")), []).append(item)

    return {
        "status": "CLEAR" if not items else "MIGRATION_REQUIRED",
        "remaining_bypasses": len(items),
        "priority_order": ["credential_read", "network", "process", "filesystem_write"],
        "grouped": grouped,
        "queue": items,
        "rule": "repair shared primitives and entrypoint families before per-file exceptions; no bypass may be averaged away",
    }

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Iterable

from zero_os.firmware_pure_logic import FirmwareMeasurement


def canonical_measurement_payload(measurement: FirmwareMeasurement) -> bytes:
    payload = asdict(measurement)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def measurement_leaf(measurement: FirmwareMeasurement) -> str:
    return hashlib.sha256(canonical_measurement_payload(measurement)).hexdigest()


def measured_boot_root(measurements: Iterable[FirmwareMeasurement]) -> dict:
    rows = sorted(tuple(measurements), key=lambda item: item.component_id)
    if not rows:
        return {"ok": False, "reason": "measurements_missing", "root": "", "leaves": []}
    leaves = [measurement_leaf(row) for row in rows]
    level = [bytes.fromhex(item) for item in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return {
        "ok": True,
        "root": level[0].hex(),
        "leaves": leaves,
        "component_ids": [row.component_id for row in rows],
        "measurement_count": len(rows),
        "authority_granted": False,
        "epistemic_role": "measured_boot_evidence_only",
    }

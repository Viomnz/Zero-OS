"""Lightweight, self-contained recursive logic filter."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CureResult:
    target: str
    activated: bool
    survived: bool
    pressure: int
    notes: str
    beacon_path: str | None = None


def run_cure_firewall(cwd: str, target_rel_path: str, pressure: int) -> CureResult:
    """Run the 3-part Cure Firewall pipeline on a local file target."""
    target = (Path(cwd).resolve() / target_rel_path).resolve()
    base = Path(cwd).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return CureResult(target=str(target), activated=False, survived=False, pressure=pressure, notes="blocked: path escapes workspace")

    if pressure < 50:
        return CureResult(target=str(target), activated=False, survived=False, pressure=pressure, notes="inactive: pressure below threshold")
    if not target.exists() or not target.is_file():
        return CureResult(target=str(target), activated=True, survived=False, pressure=pressure, notes="failed: target file missing")

    # Part 1: recursion engine (multi-pass self-hash reflection)
    data = target.read_bytes()
    digest_a = hashlib.sha256(data).hexdigest()
    digest_b = hashlib.sha256((digest_a + str(len(data))).encode("utf-8")).hexdigest()
    digest_c = hashlib.sha256((digest_b + digest_a).encode("utf-8")).hexdigest()

    # Part 2: logic checker (structural survivability checks)
    checks = {
        "size_ok": len(data) <= 1_000_000,
        "non_empty": len(data) > 0,
        "stable_chain": digest_c != digest_a,
        "text_or_binary_ok": True,
    }
    survived = all(checks.values())

    # Part 3: result handler (beacon mark on survival)
    beacon = None
    if survived:
        beacon_dir = base / ".zero_os" / "beacons"
        beacon_dir.mkdir(parents=True, exist_ok=True)
        beacon_file = beacon_dir / f"{target.stem}.beacon.json"
        payload = {
            "target": str(target),
            "pressure": pressure,
            "digest": digest_c,
            "checks": checks,
            "status": "recursion-pass",
        }
        beacon_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        beacon = str(beacon_file)

    note = "survived: recursion-pass beacon marked" if survived else "collapsed: survivability checks failed"
    return CureResult(
        target=str(target),
        activated=True,
        survived=survived,
        pressure=pressure,
        notes=note,
        beacon_path=beacon,
    )


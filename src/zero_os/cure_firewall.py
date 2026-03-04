"""Lightweight, self-contained recursive logic filter."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CureResult:
    target: str
    activated: bool
    survived: bool
    pressure: int
    notes: str
    score: int = 0
    beacon_path: str | None = None


def run_cure_firewall(cwd: str, target_rel_path: str, pressure: int) -> CureResult:
    """Run the 3-part Cure Firewall pipeline on a local file target."""
    target = (Path(cwd).resolve() / target_rel_path).resolve()
    base = Path(cwd).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return CureResult(target=str(target), activated=False, survived=False, pressure=pressure, notes="blocked: path escapes workspace", score=0)

    if pressure < 50:
        return CureResult(target=str(target), activated=False, survived=False, pressure=pressure, notes="inactive: pressure below threshold", score=0)
    if not target.exists() or not target.is_file():
        return CureResult(target=str(target), activated=True, survived=False, pressure=pressure, notes="failed: target file missing", score=0)

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
    score = _recursion_score(data, pressure, digest_a, digest_b, digest_c)
    survived = all(checks.values())

    # Part 3: result handler (beacon mark on survival)
    beacon = None
    if survived:
        beacon_dir = base / ".zero_os" / "beacons"
        beacon_dir.mkdir(parents=True, exist_ok=True)
        beacon_file = beacon_dir / f"{target.stem}.beacon.json"
        payload = {
            "schema": "zero-os-beacon-v2",
            "target": str(target),
            "pressure": pressure,
            "score": score,
            "digest": digest_c,
            "checks": checks,
            "status": "recursion-pass",
        }
        signature = _sign_payload(base, payload)
        payload["signature"] = signature
        beacon_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        beacon = str(beacon_file)

    note = "survived: recursion-pass beacon marked" if survived else "collapsed: survivability checks failed"
    return CureResult(
        target=str(target),
        activated=True,
        survived=survived,
        pressure=pressure,
        notes=note,
        score=score,
        beacon_path=beacon,
    )


def verify_beacon(cwd: str, target_rel_path: str) -> tuple[bool, str]:
    base = Path(cwd).resolve()
    target = (base / target_rel_path).resolve()
    beacon = base / ".zero_os" / "beacons" / f"{target.stem}.beacon.json"
    if not beacon.exists():
        return (False, f"missing beacon: {beacon}")
    try:
        payload = json.loads(beacon.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return (False, "invalid beacon json")
    signature = payload.get("signature", "")
    if not signature:
        return (False, "missing signature")
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    expected = _sign_payload(base, unsigned)
    if not hmac.compare_digest(signature, expected):
        return (False, "invalid signature")
    if unsigned.get("status") != "recursion-pass":
        return (False, "status is not recursion-pass")
    return (True, "signature valid")


def _recursion_score(data: bytes, pressure: int, a: str, b: str, c: str) -> int:
    """Custom recursion score: combines pressure, chain divergence, and payload complexity."""
    unique_bytes = len(set(data[:4096])) if data else 0
    entropy_factor = min(100, unique_bytes)
    chain_delta = sum(1 for i in range(len(a)) if a[i] != c[i])
    chain_factor = min(100, int(chain_delta * 100 / len(a)))
    size_factor = 100 if 0 < len(data) <= 1_000_000 else 0
    pressure_factor = max(0, min(100, pressure))
    score = int((pressure_factor * 0.35) + (chain_factor * 0.30) + (entropy_factor * 0.20) + (size_factor * 0.15))
    return max(0, min(100, score))


def _sign_payload(base: Path, payload: dict) -> str:
    key = _load_or_create_key(base)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def _load_or_create_key(base: Path) -> bytes:
    key_path = base / ".zero_os" / "keys" / "beacon.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        key_path.write_text(secrets.token_hex(32), encoding="utf-8")
    return key_path.read_text(encoding="utf-8").strip().encode("utf-8")

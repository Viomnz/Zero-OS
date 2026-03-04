"""Lightweight, self-contained recursive logic filter."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

BEACON_SCHEMA_FILE = "zero-os-beacon-v3"
BEACON_SCHEMA_NET = "zero-os-net-beacon-v3"
BEACON_POLICY_VERSION = 1
FILE_BEACON_TTL_DAYS = 30
NET_BEACON_TTL_DAYS = 7


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
        result = CureResult(target=str(target), activated=False, survived=False, pressure=pressure, notes="blocked: path escapes workspace", score=0)
        append_audit(base, "file_run", str(target), "blocked", result.notes)
        return result

    if pressure < 50:
        result = CureResult(target=str(target), activated=False, survived=False, pressure=pressure, notes="inactive: pressure below threshold", score=0)
        append_audit(base, "file_run", str(target), "inactive", result.notes)
        return result
    if not target.exists() or not target.is_file():
        result = CureResult(target=str(target), activated=True, survived=False, pressure=pressure, notes="failed: target file missing", score=0)
        append_audit(base, "file_run", str(target), "failed", result.notes)
        return result

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
        stat = target.stat()
        now = datetime.now(timezone.utc)
        payload = {
            "schema": BEACON_SCHEMA_FILE,
            "policy_version": BEACON_POLICY_VERSION,
            "target": str(target),
            "pressure": pressure,
            "score": score,
            "digest": digest_c,
            "checks": checks,
            "status": "recursion-pass",
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(days=FILE_BEACON_TTL_DAYS)).isoformat(),
            "binding": {
                "path": str(target),
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            },
        }
        signature = _sign_payload(base, payload)
        payload["signature"] = signature
        beacon_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        beacon = str(beacon_file)

    note = "survived: recursion-pass beacon marked" if survived else "collapsed: survivability checks failed"
    result = CureResult(
        target=str(target),
        activated=True,
        survived=survived,
        pressure=pressure,
        notes=note,
        score=score,
        beacon_path=beacon,
    )
    append_audit(base, "file_run", str(target), "pass" if survived else "collapse", f"score={score}; pressure={pressure}")
    return result


def verify_beacon(cwd: str, target_rel_path: str) -> tuple[bool, str]:
    base = Path(cwd).resolve()
    target = (base / target_rel_path).resolve()
    beacon = base / ".zero_os" / "beacons" / f"{target.stem}.beacon.json"
    if not beacon.exists():
        append_audit(base, "file_verify", str(target), "fail", "missing beacon")
        return (False, f"missing beacon: {beacon}")
    try:
        payload = json.loads(beacon.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        append_audit(base, "file_verify", str(target), "fail", "invalid beacon json")
        return (False, "invalid beacon json")
    if payload.get("schema") != BEACON_SCHEMA_FILE:
        append_audit(base, "file_verify", str(target), "fail", "schema mismatch")
        return (False, "schema mismatch")
    if int(payload.get("policy_version", -1)) != BEACON_POLICY_VERSION:
        append_audit(base, "file_verify", str(target), "fail", "policy version mismatch")
        return (False, "policy version mismatch")
    if _is_revoked(base, payload.get("digest", "")):
        append_audit(base, "file_verify", str(target), "fail", "digest revoked")
        return (False, "digest revoked")
    valid_time, reason = _check_time(payload)
    if not valid_time:
        append_audit(base, "file_verify", str(target), "fail", reason)
        return (False, reason)

    signature = payload.get("signature", "")
    if not signature:
        append_audit(base, "file_verify", str(target), "fail", "missing signature")
        return (False, "missing signature")
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    expected = _sign_payload(base, unsigned)
    if not hmac.compare_digest(signature, expected):
        append_audit(base, "file_verify", str(target), "fail", "invalid signature")
        return (False, "invalid signature")
    if unsigned.get("status") != "recursion-pass":
        append_audit(base, "file_verify", str(target), "fail", "status is not recursion-pass")
        return (False, "status is not recursion-pass")

    # Content drift binding check.
    if not target.exists() or not target.is_file():
        append_audit(base, "file_verify", str(target), "fail", "target missing")
        return (False, "target missing")
    binding = unsigned.get("binding", {})
    data = target.read_bytes()
    stat = target.stat()
    expected_hash = binding.get("sha256")
    expected_size = int(binding.get("size", -1))
    expected_mtime = int(binding.get("mtime_ns", -1))
    if expected_hash != hashlib.sha256(data).hexdigest() or expected_size != stat.st_size or expected_mtime != stat.st_mtime_ns:
        append_audit(base, "file_verify", str(target), "fail", "content drift detected")
        return (False, "content drift detected")

    append_audit(base, "file_verify", str(target), "pass", "signature valid")
    return (True, "signature valid")


def run_cure_firewall_net(cwd: str, url: str, pressure: int) -> CureResult:
    """Run Cure Firewall for internet targets (URL-level structural filter)."""
    base = Path(cwd).resolve()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        result = CureResult(target=url, activated=False, survived=False, pressure=pressure, notes="invalid url", score=0)
        append_audit(base, "net_run", url, "fail", result.notes)
        return result
    if not domain_allowed(base, parsed.netloc):
        result = CureResult(target=url, activated=False, survived=False, pressure=pressure, notes="blocked: domain denied by policy", score=0)
        append_audit(base, "net_run", url, "blocked", result.notes)
        return result
    if pressure < 50:
        result = CureResult(target=url, activated=False, survived=False, pressure=pressure, notes="inactive: pressure below threshold", score=0)
        append_audit(base, "net_run", url, "inactive", result.notes)
        return result

    data = url.encode("utf-8")
    digest_a = hashlib.sha256(data).hexdigest()
    digest_b = hashlib.sha256((digest_a + parsed.netloc).encode("utf-8")).hexdigest()
    digest_c = hashlib.sha256((digest_b + parsed.path).encode("utf-8")).hexdigest()

    checks = {
        "scheme_ok": parsed.scheme in {"http", "https"},
        "host_ok": bool(parsed.netloc),
        "path_ok": len(parsed.path) <= 2048,
        "stable_chain": digest_c != digest_a,
    }
    score = _recursion_score(data, pressure, digest_a, digest_b, digest_c)
    survived = all(checks.values())

    beacon = None
    if survived:
        beacon_dir = base / ".zero_os" / "beacons"
        beacon_dir.mkdir(parents=True, exist_ok=True)
        beacon_file = beacon_dir / f"net_{_url_id(url)}.beacon.json"
        now = datetime.now(timezone.utc)
        payload = {
            "schema": BEACON_SCHEMA_NET,
            "policy_version": BEACON_POLICY_VERSION,
            "target_url": url,
            "host": parsed.netloc,
            "pressure": pressure,
            "score": score,
            "digest": digest_c,
            "checks": checks,
            "status": "recursion-pass",
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(days=NET_BEACON_TTL_DAYS)).isoformat(),
        }
        signature = _sign_payload(base, payload)
        payload["signature"] = signature
        beacon_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        beacon = str(beacon_file)

    note = "survived: net recursion-pass beacon marked" if survived else "collapsed: survivability checks failed"
    result = CureResult(
        target=url,
        activated=True,
        survived=survived,
        pressure=pressure,
        notes=note,
        score=score,
        beacon_path=beacon,
    )
    append_audit(base, "net_run", url, "pass" if survived else "collapse", f"score={score}; pressure={pressure}")
    return result


def verify_beacon_net(cwd: str, url: str) -> tuple[bool, str]:
    base = Path(cwd).resolve()
    beacon = base / ".zero_os" / "beacons" / f"net_{_url_id(url)}.beacon.json"
    if not beacon.exists():
        append_audit(base, "net_verify", url, "fail", "missing net beacon")
        return (False, f"missing net beacon: {beacon}")
    try:
        payload = json.loads(beacon.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        append_audit(base, "net_verify", url, "fail", "invalid beacon json")
        return (False, "invalid beacon json")
    if payload.get("schema") != BEACON_SCHEMA_NET:
        append_audit(base, "net_verify", url, "fail", "schema mismatch")
        return (False, "schema mismatch")
    if int(payload.get("policy_version", -1)) != BEACON_POLICY_VERSION:
        append_audit(base, "net_verify", url, "fail", "policy version mismatch")
        return (False, "policy version mismatch")
    if _is_revoked(base, payload.get("digest", "")):
        append_audit(base, "net_verify", url, "fail", "digest revoked")
        return (False, "digest revoked")
    valid_time, reason = _check_time(payload)
    if not valid_time:
        append_audit(base, "net_verify", url, "fail", reason)
        return (False, reason)

    signature = payload.get("signature", "")
    if not signature:
        append_audit(base, "net_verify", url, "fail", "missing signature")
        return (False, "missing signature")
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    expected = _sign_payload(base, unsigned)
    if not hmac.compare_digest(signature, expected):
        append_audit(base, "net_verify", url, "fail", "invalid signature")
        return (False, "invalid signature")
    if unsigned.get("status") != "recursion-pass":
        append_audit(base, "net_verify", url, "fail", "status is not recursion-pass")
        return (False, "status is not recursion-pass")
    if unsigned.get("target_url") != url:
        append_audit(base, "net_verify", url, "fail", "target url mismatch")
        return (False, "target url mismatch")

    host = urlparse(url).netloc
    if not domain_allowed(base, host):
        append_audit(base, "net_verify", url, "fail", "domain denied by policy")
        return (False, "domain denied by policy")

    append_audit(base, "net_verify", url, "pass", "signature valid")
    return (True, "signature valid")


def domain_allowed(base: Path, host: str) -> bool:
    policy = load_net_policy(base)
    denied = set(policy.get("deny", []))
    allowed = set(policy.get("allow", []))
    h = host.lower().strip()
    if h in denied:
        return False
    if allowed and h not in allowed:
        return False
    return True


def load_net_policy(base: Path) -> dict[str, list[str]]:
    path = base / ".zero_os" / "net_policy.json"
    if not path.exists():
        return {"allow": [], "deny": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {"allow": [], "deny": []}
    allow = [str(x).lower().strip() for x in data.get("allow", []) if str(x).strip()]
    deny = [str(x).lower().strip() for x in data.get("deny", []) if str(x).strip()]
    return {"allow": sorted(set(allow)), "deny": sorted(set(deny))}


def set_net_policy(base: Path, host: str, mode: str) -> dict[str, list[str]]:
    policy = load_net_policy(base)
    host_norm = host.lower().strip()
    allow = set(policy.get("allow", []))
    deny = set(policy.get("deny", []))
    if mode == "allow":
        allow.add(host_norm)
        deny.discard(host_norm)
    elif mode == "deny":
        deny.add(host_norm)
        allow.discard(host_norm)
    elif mode == "remove":
        allow.discard(host_norm)
        deny.discard(host_norm)
    out = {"allow": sorted(allow), "deny": sorted(deny)}
    path = base / ".zero_os" / "net_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def audit_status(cwd: str) -> str:
    base = Path(cwd).resolve()
    path = base / ".zero_os" / "audit.log"
    if not path.exists():
        return f"audit log missing: {path}"
    lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if not lines:
        return f"audit entries: 0\npath: {path}"
    valid_chain = True
    prev_hash = ""
    for line in lines:
        record = json.loads(line)
        sig = record.get("signature", "")
        unsigned = dict(record)
        unsigned.pop("signature", None)
        expected = _sign_payload(base, unsigned)
        if not hmac.compare_digest(sig, expected):
            valid_chain = False
            break
        if unsigned.get("prev_hash", "") != prev_hash:
            valid_chain = False
            break
        prev_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
    return f"audit entries: {len(lines)}\nchain_valid: {valid_chain}\npath: {path}"


def append_audit(base: Path, event_type: str, target: str, outcome: str, details: str) -> None:
    path = base / ".zero_os" / "audit.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    prev_hash = ""
    if path.exists():
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        if lines:
            prev_hash = hashlib.sha256(lines[-1].encode("utf-8")).hexdigest()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "target": target,
        "outcome": outcome,
        "details": details,
        "prev_hash": prev_hash,
    }
    record["signature"] = _sign_payload(base, record)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _check_time(payload: dict) -> tuple[bool, str]:
    now = datetime.now(timezone.utc)
    issued_raw = str(payload.get("issued_at", ""))
    expires_raw = str(payload.get("expires_at", ""))
    try:
        issued = datetime.fromisoformat(issued_raw)
        expires = datetime.fromisoformat(expires_raw)
    except ValueError:
        return (False, "invalid timestamp fields")
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return (False, "beacon expired")
    if issued > now + timedelta(minutes=5):
        return (False, "issued_at is in the future")
    return (True, "time valid")


def _is_revoked(base: Path, digest: str) -> bool:
    path = base / ".zero_os" / "revocations.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return False
    revoked = {str(x).strip() for x in data.get("revoked_digests", [])}
    return digest in revoked


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


def _url_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]

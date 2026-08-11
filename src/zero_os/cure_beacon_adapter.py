from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from zero_os.cure_firewall import verify_beacon
from zero_os.immune_beacon import PressureEvidence


@dataclass(frozen=True)
class LegacyCureEvidence:
    accepted_as_pressure_evidence: bool
    status: str
    reasons: tuple[str, ...]
    subject_id: str
    artifact_hash: str
    pressure_evidence: tuple[PressureEvidence, ...]
    authority_granted: bool = False
    scope_certified: bool = False


def import_legacy_file_beacon(cwd: str, target_rel_path: str) -> LegacyCureEvidence:
    """Import an old Cure Firewall beacon as evidence, never as authority.

    Legacy Cure beacons are useful historical pressure records, but their signer
    lives in the same runtime trust domain and they do not independently certify
    scope. They therefore cannot mint a modern ImmuneBeacon by themselves.
    """
    ok, reason = verify_beacon(cwd, target_rel_path)
    base = Path(cwd).resolve()
    target = (base / target_rel_path).resolve()
    beacon_path = base / ".zero_os" / "beacons" / f"{target.stem}.beacon.json"
    reasons: list[str] = []
    if not ok:
        reasons.append(f"legacy_beacon_verification_failed:{reason}")
    if not beacon_path.exists():
        reasons.append("legacy_beacon_missing")
        payload = {}
    else:
        try:
            payload = json.loads(beacon_path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            payload = {}
            reasons.append("legacy_beacon_invalid_json")

    artifact_hash = ""
    if target.exists() and target.is_file():
        artifact_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    binding_hash = str(dict(payload.get("binding") or {}).get("sha256") or "")
    if artifact_hash and binding_hash and artifact_hash != binding_hash:
        reasons.append("legacy_beacon_binding_mismatch")

    pressure = int(payload.get("pressure", 0) or 0)
    status = str(payload.get("status") or "")
    checks = dict(payload.get("checks") or {})
    survived = bool(ok and status == "recursion-pass" and checks and all(bool(v) for v in checks.values()))
    evidence = ()
    if survived:
        evidence = (
            PressureEvidence(
                evidence_id=f"legacy-cure:{payload.get('digest', artifact_hash)}",
                pressure_family="legacy_cure_recursion",
                pressure_level=max(0, pressure),
                method_family="legacy_cure_firewall",
                lineage_id="legacy_cure_runtime_hmac",
                evaluator_id="legacy_cure_runtime",
                result="SURVIVED",
                provenance=(str(beacon_path),),
            ),
        )

    return LegacyCureEvidence(
        accepted_as_pressure_evidence=bool(survived and not reasons),
        status="LEGACY_CURE_PRESSURE_EVIDENCE_ONLY" if survived and not reasons else "LEGACY_CURE_EVIDENCE_REJECTED",
        reasons=tuple(reasons),
        subject_id=str(target),
        artifact_hash=artifact_hash,
        pressure_evidence=evidence,
        authority_granted=False,
        scope_certified=False,
    )

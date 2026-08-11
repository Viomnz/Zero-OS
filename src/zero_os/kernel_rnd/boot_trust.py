from __future__ import annotations

import hashlib
from pathlib import Path

from zero_os.firmware_measured_boot import measured_boot_root
from zero_os.firmware_pure_logic import (
    FirmwareMeasurement,
    FirmwarePolicy,
    HardwareTrustEvidence,
    decision_to_dict,
    evaluate_firmware_boot,
)


def image_sha256(path: str) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_boot_image(path: str, expected_sha256: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "reason": "image missing", "path": str(p)}
    got = image_sha256(str(p))
    ok = got.lower() == expected_sha256.lower()
    return {
        "ok": ok,
        "path": str(p),
        "expected": expected_sha256,
        "actual": got,
        "authority_granted": False,
        "epistemic_role": "measurement_only",
    }


def evaluate_measured_boot(
    *,
    policy: FirmwarePolicy,
    hardware: HardwareTrustEvidence,
    measurements: tuple[FirmwareMeasurement, ...],
    active_contradictions: tuple[str, ...] = (),
) -> dict:
    """Evaluate boot evidence without letting measurement become final authority."""
    root = measured_boot_root(measurements)
    decision = evaluate_firmware_boot(
        policy=policy,
        hardware=hardware,
        measurements=measurements,
        active_contradictions=active_contradictions,
    )
    return {
        "ok": bool(decision.allowed),
        "decision": decision_to_dict(decision),
        "measured_boot_root": root,
        "measurement_is_final_authority": False,
        "path_logic_is_final_authority": False,
        "requires_external_or_hardware_root_for_production": True,
    }

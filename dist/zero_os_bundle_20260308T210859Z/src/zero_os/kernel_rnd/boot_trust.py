from __future__ import annotations

import hashlib
from pathlib import Path


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
    return {"ok": ok, "path": str(p), "expected": expected_sha256, "actual": got}

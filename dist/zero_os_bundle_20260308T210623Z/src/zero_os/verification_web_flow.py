from __future__ import annotations

import re

from zero_os.net_client import request_text


def verify_web_lookup(url: str) -> dict:
    response = request_text(url, timeout=8, retries=1)
    if not response.get("ok", False):
        return {"ok": False, "url": url, "verified": False, "reason": response.get("error", "request_failed")}
    body = str(response.get("body", ""))
    signals = {
        "has_title": "<title" in body.lower(),
        "has_text": len(re.sub(r"\s+", " ", body).strip()) > 50,
        "http_ok": int(response.get("status", 0)) in {200, 201, 204},
    }
    score = sum(1 for v in signals.values() if v) / len(signals)
    return {
        "ok": True,
        "url": url,
        "verified": score >= 0.66,
        "verification_score": round(score, 4),
        "signals": signals,
        "status": response.get("status", 0),
    }

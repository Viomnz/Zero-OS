from __future__ import annotations

import json
import os

from english_understanding import human_response_from_understanding
from zero_os.net_client import request_text


def _remote_chat(prompt: str) -> str | None:
    url = os.getenv("ZERO_OS_CHAT_COMPLETIONS_URL", "").strip()
    if not url:
        return None
    model = os.getenv("ZERO_OS_CHAT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    timeout_s = float(os.getenv("ZERO_OS_CHAT_TIMEOUT_S", "30"))
    token = os.getenv("ZERO_OS_CHAT_API_KEY", "").strip()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    result = request_text(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        timeout=max(1, int(timeout_s)),
        retries=0,
    )
    if not result.get("ok", False):
        return None
    try:
        raw = json.loads(str(result.get("body", "")))
    except Exception:
        return None
    choices = raw.get("choices", []) if isinstance(raw, dict) else []
    if not choices:
        return None
    msg = choices[0].get("message", {})
    text = str(msg.get("content", "")).strip()
    return text or None


def generate_primary_response(prompt: str, understanding: dict) -> str:
    remote = _remote_chat(prompt)
    if remote:
        return remote
    return human_response_from_understanding(understanding, prompt)

from __future__ import annotations

import json
import os
import urllib.request

from english_understanding import human_response_from_understanding


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
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
        choices = raw.get("choices", [])
        if not choices:
            return None
        msg = choices[0].get("message", {})
        text = str(msg.get("content", "")).strip()
        return text or None
    except Exception:
        return None


def generate_primary_response(prompt: str, understanding: dict) -> str:
    remote = _remote_chat(prompt)
    if remote:
        return remote
    return human_response_from_understanding(understanding, prompt)

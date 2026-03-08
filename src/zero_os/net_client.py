from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_text(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
    retries: int = 2,
    backoff_seconds: float = 0.4,
) -> dict:
    hdrs = {"User-Agent": "Zero-OS/0.1"}
    if headers:
        hdrs.update(headers)

    last_error = ""
    attempts = max(1, int(retries) + 1)
    for i in range(attempts):
        try:
            req = Request(url, data=data, method=method.upper(), headers=hdrs)
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                status = int(getattr(resp, "status", 200))
                ctype = str(resp.headers.get("Content-Type", ""))
                return {
                    "ok": True,
                    "status": status,
                    "content_type": ctype,
                    "body": body,
                    "attempts": i + 1,
                }
        except HTTPError as exc:
            status = int(getattr(exc, "code", 0) or 0)
            payload = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            exc.close()
            # Retry on transient server/network class errors.
            if status >= 500 and i < attempts - 1:
                time.sleep(backoff_seconds * (2**i))
                continue
            return {
                "ok": False,
                "status": status,
                "content_type": "",
                "body": payload,
                "error": str(exc),
                "attempts": i + 1,
            }
        except URLError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        if i < attempts - 1:
            time.sleep(backoff_seconds * (2**i))

    return {
        "ok": False,
        "status": 0,
        "content_type": "",
        "body": "",
        "error": last_error or "request failed",
        "attempts": attempts,
    }


def parse_json_body(raw: str) -> tuple[bool, dict | list | str]:
    try:
        return (True, json.loads(raw))
    except Exception:
        return (False, raw)

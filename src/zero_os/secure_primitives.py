from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

from zero_os.capability_lease import require_scope
from zero_os.network_egress_policy import evaluate_egress


class CapabilityDenied(PermissionError):
    pass


def _require(scope: str) -> None:
    decision = require_scope(scope)
    if not decision.get("ok", False):
        raise CapabilityDenied(f"{decision.get('reason')}:{scope}")


def network_open(req: Request | str, *, timeout: int = 10, write: bool = False):
    url = req.full_url if isinstance(req, Request) else str(req)
    headers = dict(req.header_items()) if isinstance(req, Request) else {}
    decision = evaluate_egress(url, headers=headers, write=write)
    if not decision.allowed:
        raise CapabilityDenied(f"{decision.reason}:{decision.host or decision.scheme}")
    return urlopen(req, timeout=timeout)


def read_secret(path: str | Path, *, encoding: str = "utf-8") -> str:
    _require("credential:read")
    return Path(path).read_text(encoding=encoding)


def read_file(path: str | Path, *, encoding: str = "utf-8") -> str:
    _require("filesystem:read")
    return Path(path).read_text(encoding=encoding)


def write_file(path: str | Path, content: str, *, encoding: str = "utf-8") -> int:
    _require("filesystem:write")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target.write_text(content, encoding=encoding)


def remove_file(path: str | Path) -> None:
    _require("filesystem:write")
    Path(path).unlink()

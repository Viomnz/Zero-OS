from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

from zero_os.capability_lease import require_scope


class CapabilityDenied(PermissionError):
    pass


def _require(scope: str) -> None:
    decision = require_scope(scope)
    if not decision.get("ok", False):
        raise CapabilityDenied(f"{decision.get('reason')}:{scope}")


def network_open(req: Request | str, *, timeout: int = 10, write: bool = False):
    _require("network:write" if write else "network:fetch")
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

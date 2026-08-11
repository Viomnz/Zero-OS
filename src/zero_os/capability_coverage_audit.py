from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


GUARD_NAMES = {"authorize_capability", "authorize_runtime_mutation", "classify_action"}


@dataclass(frozen=True)
class CapabilitySink:
    path: str
    function: str
    line: int
    family: str
    mediated: bool


def _call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        parts: list[str] = []
        current = fn
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    return ""


def _family(name: str, node: ast.Call) -> str:
    low = name.lower()
    if any(x in low for x in ("write_text", "write_bytes", "unlink", "rename", "replace", "rmtree", "remove")):
        return "filesystem_mutation"
    if any(x in low for x in ("subprocess.run", "subprocess.popen", "os.system", "exec", "spawn")):
        return "process_execution"
    if any(x in low for x in ("urlopen", "requests.get", "httpx.get", "_api_get")):
        return "network_read"
    if any(x in low for x in ("requests.post", "httpx.post", "_api_post", "urlretrieve")):
        return "network_mutation"
    if any(x in low for x in ("getenv", "environ.get", "keyring", "secret", "credential", "token")):
        return "credential_access"
    if "tool" in low and any(x in low for x in ("invoke", "execute", "call", "run")):
        return "tool_invocation"
    if "tenant" in low and any(x in low for x in ("read", "fetch", "query", "get")):
        return "tenant_access"
    if any(x in low for x in ("deploy", "install", "self_repair", "upgrade_system")):
        return "privileged_mutation"
    return ""


def _function_has_guard(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child).split(".")[-1]
            if name in GUARD_NAMES:
                return True
    return False


def audit_capability_coverage(root: str | Path) -> dict:
    root = Path(root)
    src = root / "src" / "zero_os"
    sinks: list[CapabilitySink] = []
    parse_failures: list[str] = []
    if not src.exists():
        return {"identified_sinks": 0, "mediated_sinks": 0, "unmediated_sinks": 0, "coverage": 0.0, "promotion_permitted": False, "parse_failures": ["src/zero_os missing"], "sinks": []}

    for path in sorted(src.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            parse_failures.append(str(path.relative_to(root)))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            guarded = _function_has_guard(node)
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                family = _family(_call_name(child), child)
                if not family:
                    continue
                sinks.append(CapabilitySink(str(path.relative_to(root)), node.name, int(getattr(child, "lineno", 0)), family, guarded))

    mediated = sum(1 for sink in sinks if sink.mediated)
    total = len(sinks)
    unmediated = total - mediated
    coverage = (mediated / total) if total else 1.0
    permitted = total > 0 and unmediated == 0 and not parse_failures
    return {
        "identified_sinks": total,
        "mediated_sinks": mediated,
        "unmediated_sinks": unmediated,
        "coverage": coverage,
        "promotion_permitted": permitted,
        "parse_failures": parse_failures,
        "sinks": [sink.__dict__ for sink in sinks],
        "scope_note": "Static identified-sink coverage only; dynamic dispatch, native code, dependencies, concurrency and hardware remain unresolved.",
    }

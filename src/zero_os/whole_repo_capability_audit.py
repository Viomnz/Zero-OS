from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CapabilitySink:
    path: str
    line: int
    function: str
    sink_family: str
    sink_name: str
    mediated: bool
    mediation_reason: str

    def to_dict(self) -> dict:
        return asdict(self)


_NETWORK_CALLS = {"urlopen", "requests.get", "requests.post", "requests.put", "requests.delete", "httpx.get", "httpx.post"}
_PROCESS_CALLS = {"subprocess.run", "subprocess.Popen", "os.system"}
_WRITE_CALLS = {"write_text", "write_bytes", "unlink", "rename", "replace", "rmtree", "remove", "makedirs", "mkdir"}
_READ_CALLS = {"read_text", "read_bytes", "open"}
_MEDIATORS = {
    "authorize_capability",
    "authorized_capability_context",
    "gate_action",
    "authorize_runtime_mutation",
    "require_scope",
    "network_open",
    "read_secret",
    "read_file",
    "write_file",
    "remove_file",
}


def _call_name(node: ast.Call) -> str:
    target = node.func
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        parts: list[str] = []
        current = target
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    return ""


def _function_name(parents: list[ast.AST]) -> str:
    for parent in reversed(parents):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent.name
    return "<module>"


def _source_window(lines: list[str], lineno: int, radius: int = 25) -> str:
    start = max(0, lineno - radius - 1)
    end = min(len(lines), lineno + radius)
    return "\n".join(lines[start:end])


def _is_credential_context(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ("token", "secret", "credential", "password", "api_key", "auth"))


def _sink_family(call_name: str, context: str) -> str:
    short = call_name.split(".")[-1]
    if call_name in _NETWORK_CALLS or short == "urlopen":
        return "network"
    if call_name in _PROCESS_CALLS or short in {"run", "Popen", "system"} and "subprocess" in context:
        return "process"
    if short in _WRITE_CALLS:
        return "filesystem_write"
    if short in _READ_CALLS and _is_credential_context(context):
        return "credential_read"
    return ""


def _function_has_mediator(tree: ast.AST, target_function: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != target_function:
            continue
        calls = {_call_name(call) for call in ast.walk(node) if isinstance(call, ast.Call)}
        if any(name.split(".")[-1] in _MEDIATORS for name in calls):
            return True
    return False


def audit_python_file(path: Path, root: Path) -> list[CapabilitySink]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
    except (OSError, SyntaxError):
        return []
    lines = text.splitlines()
    sinks: list[CapabilitySink] = []

    parents: list[ast.AST] = []

    def visit(node: ast.AST) -> None:
        parents.append(node)
        if isinstance(node, ast.Call):
            name = _call_name(node)
            window = _source_window(lines, int(getattr(node, "lineno", 1)))
            family = _sink_family(name, window)
            if family:
                function = _function_name(parents[:-1])
                mediated = _function_has_mediator(tree, function) if function != "<module>" else any(mediator in window for mediator in _MEDIATORS)
                reason = "function_contains_capability_mediator" if mediated else "no_capability_mediator_in_function"
                if "secure_primitives.py" in str(path) or "capability_lease.py" in str(path):
                    mediated = True
                    reason = "trusted_capability_primitive"
                sinks.append(
                    CapabilitySink(
                        path=str(path.relative_to(root)),
                        line=int(getattr(node, "lineno", 0)),
                        function=function,
                        sink_family=family,
                        sink_name=name,
                        mediated=mediated,
                        mediation_reason=reason,
                    )
                )
        for child in ast.iter_child_nodes(node):
            visit(child)
        parents.pop()

    visit(tree)
    return sinks


def audit_whole_repository(root: str | Path, *, excluded_parts: Iterable[str] = (".git", ".venv", "venv", "node_modules")) -> dict:
    base = Path(root).resolve()
    excluded = set(str(item) for item in excluded_parts)
    sinks: list[CapabilitySink] = []
    parsed_files = 0
    for path in base.rglob("*.py"):
        if excluded.intersection(path.parts):
            continue
        parsed_files += 1
        sinks.extend(audit_python_file(path, base))

    unmediated = [sink for sink in sinks if not sink.mediated]
    family_counts: dict[str, int] = {}
    unmediated_family_counts: dict[str, int] = {}
    for sink in sinks:
        family_counts[sink.sink_family] = family_counts.get(sink.sink_family, 0) + 1
    for sink in unmediated:
        unmediated_family_counts[sink.sink_family] = unmediated_family_counts.get(sink.sink_family, 0) + 1

    total = len(sinks)
    mediated_count = total - len(unmediated)
    coverage = (mediated_count / total) if total else 1.0
    return {
        "status": "PASS_IDENTIFIED_STATIC_SCOPE" if not unmediated else "BLOCK_PROMOTION",
        "parsed_python_files": parsed_files,
        "identified_sensitive_sinks": total,
        "mediated_sinks": mediated_count,
        "unmediated_sinks": len(unmediated),
        "mediation_coverage": coverage,
        "family_counts": family_counts,
        "unmediated_family_counts": unmediated_family_counts,
        "unmediated": [sink.to_dict() for sink in unmediated],
        "all_sinks": [sink.to_dict() for sink in sinks],
        "promotion_permitted": not unmediated,
        "limitations": [
            "static_python_ast_only",
            "dynamic_dispatch_not_certified",
            "native_code_not_certified",
            "dependency_behavior_not_certified",
            "firmware_and_hardware_not_certified",
            "runtime_independence_not_certified",
        ],
    }

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from zero_os.process_capability_policy import classify_executable


@dataclass(frozen=True)
class DirectTransportFinding:
    path: str
    line: int
    function: str
    family: str
    primitive: str
    required_scope: str
    dynamic_target: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _call_name(call: ast.Call) -> str:
    node = call.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def _function_name(tree: ast.AST, target: ast.AST) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and target in set(ast.walk(node)):
            return node.name
    return "<module>"


def _literal_executable(call: ast.Call) -> tuple[str, bool]:
    if not call.args:
        return "", True
    arg = call.args[0]
    if isinstance(arg, (ast.List, ast.Tuple)) and arg.elts:
        first = arg.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value, False
        return "", True
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        text = arg.value.strip()
        return (text.split()[0] if text else ""), False
    return "", True


def audit_transport_process_migration(root: str | Path, *, excluded_parts: Iterable[str] = (".git", ".venv", "venv", "node_modules")) -> dict:
    base = Path(root).resolve()
    excluded = set(excluded_parts)
    findings: list[DirectTransportFinding] = []
    parsed_files = 0

    for path in base.rglob("*.py"):
        if excluded.intersection(path.parts):
            continue
        rel = str(path.relative_to(base))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        parsed_files += 1
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            short = name.split(".")[-1]
            function = _function_name(tree, node)

            if short == "urlopen" and rel not in {"src/zero_os/secure_primitives.py"}:
                findings.append(DirectTransportFinding(rel, int(getattr(node, "lineno", 0)), function, "raw_network", name, "network:destination_bound"))
                continue

            if name in {"subprocess.run", "subprocess.Popen", "os.system"} or short in {"Popen"}:
                executable, dynamic = _literal_executable(node)
                required = classify_executable(executable) if executable else "process:dynamic_target"
                findings.append(DirectTransportFinding(rel, int(getattr(node, "lineno", 0)), function, "process", name, required, dynamic))

    raw_network = [item for item in findings if item.family == "raw_network"]
    process = [item for item in findings if item.family == "process"]
    dynamic_process = [item for item in process if item.dynamic_target]
    unclassified_process = [item for item in process if item.required_scope in {"process:unclassified", "process:dynamic_target"}]
    process_scope_counts: dict[str, int] = {}
    for item in process:
        process_scope_counts[item.required_scope] = process_scope_counts.get(item.required_scope, 0) + 1

    return {
        "parsed_python_files": parsed_files,
        "raw_network_bypass_count": len(raw_network),
        "process_sink_count": len(process),
        "dynamic_process_target_count": len(dynamic_process),
        "unclassified_process_count": len(unclassified_process),
        "process_scope_counts": process_scope_counts,
        "raw_network": [item.to_dict() for item in raw_network],
        "process": [item.to_dict() for item in process],
        "network_consolidation_complete": len(raw_network) == 0,
        "process_classification_complete": len(unclassified_process) == 0,
        "promotion_permitted": len(raw_network) == 0 and len(unclassified_process) == 0,
        "limitations": [
            "process_execution_is_classified_not_yet_centrally_executed",
            "dynamic_process_targets_block_classification",
            "non_python_transport_not_scanned",
            "runtime_spawn_behavior_not_certified",
        ],
    }

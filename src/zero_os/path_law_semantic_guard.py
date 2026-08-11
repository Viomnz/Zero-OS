from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


AUTHORITY_SINKS = {
    "constitutional_decide",
    "issue_attestation_from_constitution",
    "ticket_from_attestation",
    "lease_from_attestation",
    "issue_execution_ticket",
    "issue_capability_lease",
    "consume_execution_ticket",
    "acknowledge_consumed_execution_ticket",
    "mutate_state",
    "mutate_batch",
}

PATH_HINTS = ("path_law", "path_logic", "choose_path", "select_path", "path_score")


@dataclass(frozen=True)
class SemanticPathFinding:
    path: str
    function: str
    line: int
    reason: str
    target: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _qualified_call(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return "<dynamic>"


def _path_named(name: str, file_path: Path) -> bool:
    low = f"{name} {file_path.name}".lower()
    return any(hint in low for hint in PATH_HINTS)


def audit_path_law_semantic_non_authority(root: str | Path) -> dict[str, Any]:
    """Conservative static reachability audit for Path Law authority isolation.

    Builds an intra-repository call graph, resolves simple import/assignment
    aliases, and marks unknown dynamic dispatch reachable from Path functions as
    contested rather than safe. Static success is not a proof of runtime
    non-reachability.
    """
    base = Path(root).resolve()
    functions: dict[str, tuple[Path, ast.AST]] = {}
    aliases: dict[str, str] = {}
    calls: dict[str, list[tuple[str, int]]] = {}
    dynamic: dict[str, list[int]] = {}
    starts: set[str] = set()

    for file_path in base.rglob("*.py"):
        if any(part in {".git", ".zero_os", "__pycache__", ".venv", "venv"} for part in file_path.parts):
            continue
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        module = str(file_path.relative_to(base)).replace("/", ".").removesuffix(".py")
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    aliases[item.asname or item.name] = item.name
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        aliases[target.id] = aliases.get(node.value.id, node.value.id)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = f"{module}:{node.name}"
                functions[key] = (file_path, node)
                if _path_named(node.name, file_path):
                    starts.add(key)

    by_short: dict[str, set[str]] = {}
    for key in functions:
        by_short.setdefault(key.rsplit(":", 1)[1], set()).add(key)

    for key, (_, node) in functions.items():
        rows: list[tuple[str, int]] = []
        dyn: list[int] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            name = _qualified_call(child)
            if name == "<dynamic>":
                dyn.append(int(getattr(child, "lineno", 0)))
                continue
            resolved = aliases.get(name, name)
            rows.append((resolved, int(getattr(child, "lineno", 0))))
        calls[key] = rows
        dynamic[key] = dyn

    findings: list[SemanticPathFinding] = []
    visited: set[str] = set()
    queue = list(starts)
    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)
        file_path, node = functions[current]
        fn = current.rsplit(":", 1)[1]
        for line in dynamic.get(current, []):
            findings.append(SemanticPathFinding(str(file_path.relative_to(base)), fn, line, "path_authority_reachability_contested_by_dynamic_dispatch"))
        for target, line in calls.get(current, []):
            if target in AUTHORITY_SINKS:
                findings.append(SemanticPathFinding(str(file_path.relative_to(base)), fn, line, "path_logic_reaches_authority_sink", target))
                continue
            matches = by_short.get(target, set())
            if len(matches) == 1:
                queue.extend(matches)
            elif len(matches) > 1:
                findings.append(SemanticPathFinding(str(file_path.relative_to(base)), fn, line, "path_reachability_contested_by_ambiguous_call_target", target))

    return {
        "ok": not findings,
        "status": "PATH_LAW_NON_AUTHORITATIVE_IN_IDENTIFIED_STATIC_REACHABILITY_SCOPE" if not findings else "BLOCK_PROMOTION",
        "promotion_permitted": not findings,
        "path_entry_count": len(starts),
        "reachable_function_count": len(visited),
        "finding_count": len(findings),
        "findings": [item.to_dict() for item in findings],
        "invariant": "Path Law may rank only already-authorized surviving options and must have no reachable path to authority production or certification.",
        "limitations": ["static_intra_repository_analysis", "reflection_and_runtime_code_generation_remain_unresolved", "native_non_python_paths_require_separate_proof"],
    }

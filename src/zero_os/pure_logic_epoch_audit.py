from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


_MUTATION_CALLS = {
    "write_text",
    "write_bytes",
    "unlink",
    "rename",
    "replace",
    "remove",
    "rmdir",
    "makedirs",
    "mkdir",
    "copy",
    "copy2",
    "copytree",
    "move",
    "rmtree",
    "run",
    "Popen",
    "system",
    "_api_post",
    "urlopen",
    "deploy",
    "store_install",
    "run_self_repair",
    "run_recovery",
    "zero_ai_upgrade_system",
    "auto_max_fix_upgrade_everything",
    "set_action_tier",
}

_MUTATION_PREFIXES = (
    "github_",
    "cloud_",
    "write_",
    "save_",
    "delete_",
    "update_",
    "install_",
    "repair_",
    "recover_",
    "deploy_",
)

_AUTHORITY_NAMES = {
    "authorize_runtime_mutation",
    "authorize_action_and_mint_ticket",
    "classify_action",
    "consume_execution_ticket",
}

_EXCLUDED_PATH_PARTS = {"tests", ".venv", "venv", "site-packages", "__pycache__"}


@dataclass(frozen=True)
class MutationFinding:
    path: str
    line: int
    function: str
    call: str
    mediated: bool
    evidence: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class _FileAudit(ast.NodeVisitor):
    def __init__(self, path: Path, text: str) -> None:
        self.path = path
        self.text = text
        self.function_stack: list[str] = []
        self.authority_names_in_file: set[str] = set()
        self.findings: list[MutationFinding] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for item in node.names:
            if item.name in _AUTHORITY_NAMES:
                self.authority_names_in_file.add(item.asname or item.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    @staticmethod
    def _call_name(node: ast.Call) -> str:
        fn = node.func
        if isinstance(fn, ast.Name):
            return fn.id
        if isinstance(fn, ast.Attribute):
            return fn.attr
        return ""

    @staticmethod
    def _body_names(function_node: ast.AST) -> set[str]:
        names: set[str] = set()
        for child in ast.walk(function_node):
            if isinstance(child, ast.Call):
                fn = child.func
                if isinstance(fn, ast.Name):
                    names.add(fn.id)
                elif isinstance(fn, ast.Attribute):
                    names.add(fn.attr)
        return names

    def visit_Call(self, node: ast.Call) -> None:
        call = self._call_name(node)
        is_mutation = call in _MUTATION_CALLS or any(call.startswith(prefix) for prefix in _MUTATION_PREFIXES)
        if is_mutation:
            function = self.function_stack[-1] if self.function_stack else "<module>"
            mediated = False
            evidence: list[str] = []
            parent_function = None
            for ancestor in ast.walk(ast.parse(self.text)):
                if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)) and ancestor.name == function:
                    parent_function = ancestor
                    break
            if parent_function is not None:
                body_names = self._body_names(parent_function)
                hits = sorted(body_names.intersection(_AUTHORITY_NAMES))
                if hits:
                    mediated = True
                    evidence.extend(hits)
            self.findings.append(
                MutationFinding(
                    path=str(self.path),
                    line=int(getattr(node, "lineno", 0) or 0),
                    function=function,
                    call=call,
                    mediated=mediated,
                    evidence=tuple(evidence),
                )
            )
        self.generic_visit(node)


def audit_python_file(path: Path, *, root: Path | None = None) -> list[MutationFinding]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [MutationFinding(str(path), 0, "<parse>", "syntax_error", False, tuple())]
    auditor = _FileAudit(path.relative_to(root) if root else path, text)
    auditor.visit(tree)
    return auditor.findings


def audit_repository(root: str | Path) -> dict:
    root_path = Path(root).resolve()
    source_root = root_path / "src" / "zero_os"
    findings: list[MutationFinding] = []
    if source_root.exists():
        for path in source_root.rglob("*.py"):
            if any(part in _EXCLUDED_PATH_PARTS for part in path.parts):
                continue
            findings.extend(audit_python_file(path, root=root_path))
    unmediated = [item for item in findings if not item.mediated]
    mediated = [item for item in findings if item.mediated]
    total = len(findings)
    coverage = (len(mediated) / total) if total else 1.0
    return {
        "status": "PASS" if not unmediated else "BLOCK_PROMOTION",
        "total_mutation_candidates": total,
        "mediated_candidates": len(mediated),
        "unmediated_candidates": len(unmediated),
        "mediation_coverage": coverage,
        "promotion_permitted": not unmediated,
        "findings": [item.to_dict() for item in findings],
        "unmediated": [item.to_dict() for item in unmediated],
        "limitations": [
            "static AST audit cannot prove runtime completeness",
            "dynamic dispatch, native code, generated code, reflection, and dependencies remain separate scope",
            "call-name heuristics can produce false positives and false negatives",
        ],
    }

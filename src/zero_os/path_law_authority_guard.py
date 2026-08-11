from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathLawFinding:
    path: str
    line: int
    symbol: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# Path Law may rank/select among options that already survived authority checks.
# It must never create epistemic, identity, objective, capability, scope, or
# execution authority. These names are intentionally conservative.
_FORBIDDEN_AUTHORITY_CALLS = {
    "constitutional_decide",
    "issue_attestation_from_constitution",
    "ticket_from_attestation",
    "lease_from_attestation",
    "issue_execution_ticket",
    "issue_capability_lease",
    "mutate_state",
    "mutate_batch",
}

_FORBIDDEN_AUTHORITY_ASSIGNMENTS = {
    "allowed",
    "authorized",
    "authority_granted",
    "scope_certified",
    "identity_verified",
    "objective_authorized",
    "capability_authorized",
    "promotion_permitted",
}

_PATH_HINTS = ("path_law", "path_logic", "choose_path", "select_path", "path_score")


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _is_path_context(name: str, path: Path) -> bool:
    low = f"{name} {path.name}".lower()
    return any(hint in low for hint in _PATH_HINTS)


def audit_path_law_non_authority(root: str | Path) -> dict:
    base = Path(root).resolve()
    findings: list[PathLawFinding] = []
    scanned = 0

    for file_path in base.rglob("*.py"):
        # Ignore generated/cache/vendor state if present.
        if any(part in {".git", ".zero_os", "__pycache__", ".venv", "venv"} for part in file_path.parts):
            continue
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        scanned += 1

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if not _is_path_context(getattr(node, "name", ""), file_path):
                continue

            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    name = _call_name(child)
                    if name in _FORBIDDEN_AUTHORITY_CALLS:
                        findings.append(
                            PathLawFinding(
                                str(file_path.relative_to(base)),
                                int(getattr(child, "lineno", 0)),
                                name,
                                "path_logic_must_not_call_authority_or_minting_primitive",
                            )
                        )
                elif isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id in _FORBIDDEN_AUTHORITY_ASSIGNMENTS:
                            findings.append(
                                PathLawFinding(
                                    str(file_path.relative_to(base)),
                                    int(getattr(child, "lineno", 0)),
                                    target.id,
                                    "path_logic_must_not_assign_final_authority_state",
                                )
                            )
                elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    if child.target.id in _FORBIDDEN_AUTHORITY_ASSIGNMENTS:
                        findings.append(
                            PathLawFinding(
                                str(file_path.relative_to(base)),
                                int(getattr(child, "lineno", 0)),
                                child.target.id,
                                "path_logic_must_not_assign_final_authority_state",
                            )
                        )

    return {
        "ok": not findings,
        "status": "PATH_LAW_NON_AUTHORITATIVE_IN_IDENTIFIED_STATIC_SCOPE" if not findings else "BLOCK_PROMOTION",
        "promotion_permitted": not findings,
        "scanned_python_files": scanned,
        "finding_count": len(findings),
        "findings": [item.to_dict() for item in findings],
        "invariant": "Path Law selects among already-authorized surviving paths; it never grants truth, scope, identity, objective, capability, execution, or promotion authority.",
        "recheck_policy": "run_on_every_candidate_change_and_before_promotion",
        "limitations": [
            "static_ast_scope_only",
            "dynamic_dispatch_not_fully_proven",
            "native_and_non_python_paths_require_separate_checks",
            "runtime_trace_and_tests_remain_required",
        ],
    }

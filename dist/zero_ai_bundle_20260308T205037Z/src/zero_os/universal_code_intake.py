"""Universal code intake for known and unknown programming formats."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass
class IntakeResult:
    target: str
    exists: bool
    language_guess: str
    bytes_size: int
    sha256: str
    token_count: int
    line_count: int
    ascii_ratio: float
    report_path: str


KNOWN_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".m": "objective-c",
    ".scala": "scala",
    ".lua": "lua",
    ".sh": "shell",
    ".ps1": "powershell",
}


def intake_code(cwd: str, target_rel: str) -> IntakeResult:
    base = Path(cwd).resolve()
    target = (base / target_rel).resolve()
    report_dir = base / ".zero_os" / "intake"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{target.stem}.intake.json"

    try:
        target.relative_to(base)
    except ValueError:
        result = IntakeResult(
            target=str(target),
            exists=False,
            language_guess="blocked:path_escape",
            bytes_size=0,
            sha256="",
            token_count=0,
            line_count=0,
            ascii_ratio=0.0,
            report_path=str(report_path),
        )
        report_path.write_text(json.dumps(result.__dict__, indent=2) + "\n", encoding="utf-8")
        return result

    if not target.exists() or not target.is_file():
        result = IntakeResult(
            target=str(target),
            exists=False,
            language_guess="missing",
            bytes_size=0,
            sha256="",
            token_count=0,
            line_count=0,
            ascii_ratio=0.0,
            report_path=str(report_path),
        )
        report_path.write_text(json.dumps(result.__dict__, indent=2) + "\n", encoding="utf-8")
        return result

    data = target.read_bytes()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    tokens = _tokenize(text)
    language = _guess_language(target, text)
    ascii_ratio = _ascii_ratio(text)
    sha = hashlib.sha256(data).hexdigest()

    # Intermediate representation for unknown code: generic token frequency.
    ir = {
        "token_frequency_top20": Counter(tokens).most_common(20),
        "line_prefixes_top20": Counter([ln[:24] for ln in lines if ln.strip()]).most_common(20),
    }

    result = IntakeResult(
        target=str(target),
        exists=True,
        language_guess=language,
        bytes_size=len(data),
        sha256=sha,
        token_count=len(tokens),
        line_count=len(lines),
        ascii_ratio=ascii_ratio,
        report_path=str(report_path),
    )
    payload = {**result.__dict__, "intermediate_representation": ir}
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return result


def _guess_language(path: Path, text: str) -> str:
    ext = path.suffix.lower()
    if ext in KNOWN_BY_EXT:
        return KNOWN_BY_EXT[ext]
    t = text.lower()
    if "#include" in t and "int main" in t:
        return "c/cpp-like"
    if "def " in t and "import " in t:
        return "python-like"
    if "function " in t or "console.log" in t:
        return "javascript-like"
    return "unknown-format"


def _tokenize(text: str) -> list[str]:
    out = []
    cur = []
    for ch in text:
        if ch.isalnum() or ch == "_":
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
    if cur:
        out.append("".join(cur))
    return out


def _ascii_ratio(text: str) -> float:
    if not text:
        return 1.0
    ascii_count = sum(1 for c in text if ord(c) < 128)
    return ascii_count / len(text)


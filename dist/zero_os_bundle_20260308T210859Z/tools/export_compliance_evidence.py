from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REQUIRED = [
    'security/artifacts/sbom.json',
    'security/artifacts/vuln_scan.json',
    'security/artifacts/artifact_signatures.json',
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def export_evidence(root: Path) -> dict:
    checks = []
    for rel in REQUIRED:
        p = root / rel
        checks.append({'path': rel, 'exists': p.exists(), 'size': p.stat().st_size if p.exists() else 0})

    evidence = {
        'ok': all(c['exists'] for c in checks),
        'time_utc': _utc_now(),
        'checks': checks,
        'ci_gate': 'tools/security_gate.py',
        'runbooks': 'docs/SECURITY_RUNBOOKS.md',
    }
    out = root / 'security' / 'artifacts' / 'compliance_evidence.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')

    md = root / 'security' / 'artifacts' / 'compliance_evidence.md'
    lines = ['# Compliance Evidence', '', f"- Generated: {evidence['time_utc']}"]
    for c in checks:
        lines.append(f"- {c['path']}: {'OK' if c['exists'] else 'MISSING'} (size={c['size']})")
    md.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return evidence


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ev = export_evidence(root)
    print('Compliance evidence exported.')
    return 0 if ev['ok'] else 3


if __name__ == '__main__':
    raise SystemExit(main())

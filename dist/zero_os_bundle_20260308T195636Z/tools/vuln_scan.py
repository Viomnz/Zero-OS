from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

KNOWN_VULN = {
    'pyyaml': '6.0',
    'jinja2': '3.1.0',
    'urllib3': '2.0.0',
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_req_line(line: str) -> tuple[str, str] | None:
    m = re.match(r'^\s*([A-Za-z0-9_.-]+)\s*([<>=!~]{1,2})\s*([A-Za-z0-9_.-]+)', line)
    if not m:
        return None
    return m.group(1).lower(), m.group(3)


def scan_requirements(repo_root: Path) -> dict:
    findings = []
    req_files = list(repo_root.rglob('requirements*.txt'))
    for rf in req_files:
        rel = str(rf.relative_to(repo_root)).replace('\\', '/')
        for i, ln in enumerate(rf.read_text(encoding='utf-8', errors='replace').splitlines(), start=1):
            parsed = _parse_req_line(ln)
            if not parsed:
                continue
            name, ver = parsed
            if name in KNOWN_VULN and ver <= KNOWN_VULN[name]:
                findings.append({
                    'file': rel,
                    'line': i,
                    'package': name,
                    'version': ver,
                    'recommended_min': KNOWN_VULN[name],
                    'severity': 'high',
                })
    return {
        'ok': len(findings) == 0,
        'time_utc': _utc_now(),
        'finding_count': len(findings),
        'findings': findings,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / 'security' / 'artifacts'
    out_dir.mkdir(parents=True, exist_ok=True)
    report = scan_requirements(root)
    out = out_dir / 'vuln_scan.json'
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Vulnerability report: {out}')
    if not report['ok']:
        print('Critical/high findings detected.')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def generate_sbom(repo_root: Path) -> dict:
    files = []
    for p in repo_root.rglob('*'):
        if not p.is_file():
            continue
        rel = str(p.relative_to(repo_root)).replace('\\', '/')
        if rel.startswith('.git/') or rel.startswith('.zero_os/production/snapshots/'):
            continue
        files.append({
            'path': rel,
            'size': p.stat().st_size,
            'sha256': _sha256(p),
        })

    return {
        'bomFormat': 'CycloneDX-like',
        'specVersion': '1.5',
        'metadata': {
            'component': {'name': 'Zero-OS', 'type': 'application'},
            'timestamp_utc': _utc_now(),
        },
        'components': files,
        'component_count': len(files),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / 'security' / 'artifacts'
    out_dir.mkdir(parents=True, exist_ok=True)
    sbom = generate_sbom(root)
    out = out_dir / 'sbom.json'
    out.write_text(json.dumps(sbom, indent=2) + '\n', encoding='utf-8')
    print(f'SBOM generated: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

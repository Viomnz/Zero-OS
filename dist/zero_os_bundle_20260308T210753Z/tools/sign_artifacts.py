from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key_path(root: Path) -> Path:
    p = root / '.zero_os' / 'keys' / 'artifact_signing.key'
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(secrets.token_hex(32), encoding='utf-8')
    return p


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def sign(root: Path) -> dict:
    key = _key_path(root).read_text(encoding='utf-8', errors='replace').strip().encode('utf-8')
    artifacts_dir = root / 'security' / 'artifacts'
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for p in sorted(artifacts_dir.glob('*.json')):
        digest = _sha256(p)
        sig = hmac.new(key, digest.encode('utf-8'), hashlib.sha256).hexdigest()
        records.append({'file': p.name, 'sha256': digest, 'signature': sig})
    return {'ok': True, 'time_utc': _utc_now(), 'records': records}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out = sign(root)
    target = root / 'security' / 'artifacts' / 'artifact_signatures.json'
    target.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(f'Artifact signatures written: {target}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

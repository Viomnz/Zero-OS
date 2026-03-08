from __future__ import annotations

import json
from pathlib import Path


DEFAULT_CONFIG = {
    "low_end": {"max_candidates": 4, "node_count": 2, "max_attempts": 6},
    "balanced": {"max_candidates": 9, "node_count": 3, "max_attempts": 9},
    "high_end": {"max_candidates": 9, "node_count": 5, "max_attempts": 9},
    "distributed": {"agreement_threshold": 0.67, "replace_failed_nodes": True},
    "memory_quality": {"compression_threshold_entries": 280, "compression_interval_sec": 30},
    "evolution": {"novelty_prediction_boost": 0.15},
}


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_reliability_config(cwd: str) -> dict:
    path = _runtime(cwd) / "ai_reliability_config.json"
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
        return DEFAULT_CONFIG
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return DEFAULT_CONFIG
    cfg = dict(DEFAULT_CONFIG)
    for k, v in raw.items() if isinstance(raw, dict) else []:
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            merged = dict(cfg[k])
            merged.update(v)
            cfg[k] = merged
        else:
            cfg[k] = v
    return cfg

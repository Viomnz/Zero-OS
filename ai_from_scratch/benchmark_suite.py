from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

try:
    from ai_from_scratch.model import TinyBigramModel
    from ai_from_scratch.tokenizer_dataset import ZeroTokenizer, build_corpus_dataset
except ModuleNotFoundError:
    from model import TinyBigramModel
    from tokenizer_dataset import ZeroTokenizer, build_corpus_dataset


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_MANIFEST = ROOT / "laws" / "model_benchmark_suite.json"
DEFAULT_OUTPUT = ROOT / ".zero_os" / "runtime" / "model_benchmark.json"
DEFAULT_CORPUS_ENTRIES = [
    {"name": "recursion_law", "path": "laws/recursion_law.txt", "weight": 1.0, "family": "law_core"},
    {"name": "universe_laws", "path": "laws/universe_laws_canonical_123.txt", "weight": 1.0, "family": "law_core"},
    {"name": "core_cycle", "path": "laws/universal_law_core_cycle_123.txt", "weight": 0.8, "family": "law_core"},
    {"name": "third_law", "path": "laws/third_universe_law.txt", "weight": 0.7, "family": "law_core"},
    {"name": "strategic_context", "path": "laws/strategic_context_awareness.txt", "weight": 0.8, "family": "strategy_context"},
]
_FAMILY_SAMPLING_MODES = {"weighted", "balanced"}


def _clamp_valid_fraction(value: float) -> float:
    return min(max(float(value), 0.0), 0.5)


def benchmark_cohort_key(architecture: str, tokenizer_mode: str) -> str:
    return f"{str(architecture or '').strip()}|{str(tokenizer_mode or '').strip()}"


def default_manifest_payload() -> dict:
    return {
        "suite": "zero_default_laws_v1",
        "description": "Default Zero AI benchmark suite across local law corpora.",
        "tokenizer_mode": "",
        "lowercase": None,
        "valid_fraction": 0.1,
        "training": {
            "family_sampling": "weighted",
            "adaptive": {
                "enabled": True,
                "history_dir": ".zero_os/benchmarks/model",
                "window": 3,
                "min_runs": 2,
                "max_focus_families": 2,
                "max_stage_weight_scale": 3,
                "min_regression_delta": 0.0,
                "min_regression_ratio": 0.0,
            },
            "curriculum": [
                {
                    "name": "law_core_focus",
                    "weight_scale": 1,
                    "family_weights": {
                        "law_core": 1.2,
                        "strategy_context": 0.9,
                    },
                },
                {
                    "name": "family_balance",
                    "weight_scale": 1,
                    "family_sampling": "balanced",
                },
            ],
        },
        "corpora": list(DEFAULT_CORPUS_ENTRIES),
    }


def ensure_default_manifest(path: str | Path = DEFAULT_BENCHMARK_MANIFEST) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(json.dumps(default_manifest_payload(), indent=2) + "\n", encoding="utf-8")
    return target


def load_benchmark_manifest(path: str | Path = DEFAULT_BENCHMARK_MANIFEST) -> dict:
    manifest_path = ensure_default_manifest(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
    corpora = payload.get("corpora", [])
    if not isinstance(corpora, list) or not corpora:
        raise ValueError("benchmark manifest requires at least one corpus entry")
    return payload


def _corpus_entries(payload: dict) -> list[dict]:
    entries: list[dict] = []
    for index, raw in enumerate(payload.get("corpora", [])):
        if not isinstance(raw, dict):
            continue
        rel = str(raw.get("path", "")).strip()
        if not rel:
            continue
        entries.append(
            {
                "name": str(raw.get("name", f"corpus_{index + 1}")).strip() or f"corpus_{index + 1}",
                "path": rel,
                "weight": float(raw.get("weight", 1.0)),
                "family": str(raw.get("family", "default")).strip() or "default",
            }
        )
    if not entries:
        raise ValueError("benchmark manifest has no valid corpus entries")
    return entries


def _coerce_weight_mapping(raw) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    mapping: dict[str, float] = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if not name:
            continue
        try:
            mapping[name] = float(value)
        except Exception:
            continue
    return mapping


def _coerce_name_set(raw) -> set[str]:
    if not isinstance(raw, list):
        return set()
    return {str(item or "").strip() for item in raw if str(item or "").strip()}


def _normalize_family_sampling(value: str, default: str = "weighted") -> str:
    selected = str(value or default).strip().lower() or default
    return selected if selected in _FAMILY_SAMPLING_MODES else default


def _training_manifest_config(payload: dict) -> dict:
    raw = payload.get("training", {})
    if not isinstance(raw, dict):
        raw = {}
    default_sampling = _normalize_family_sampling(raw.get("family_sampling", "weighted"))
    curriculum: list[dict] = []
    raw_curriculum = raw.get("curriculum", [])
    if isinstance(raw_curriculum, list):
        for index, item in enumerate(raw_curriculum):
            if not isinstance(item, dict):
                continue
            curriculum.append(
                {
                    "name": str(item.get("name", f"stage_{index + 1}")).strip() or f"stage_{index + 1}",
                    "weight_scale": max(1, int(item.get("weight_scale", 1))),
                    "family_sampling": _normalize_family_sampling(item.get("family_sampling", default_sampling), default_sampling),
                    "family_weights": _coerce_weight_mapping(item.get("family_weights")),
                    "corpus_weights": _coerce_weight_mapping(item.get("corpus_weights")),
                    "include_families": sorted(_coerce_name_set(item.get("families", item.get("include_families", [])))),
                    "include_corpora": sorted(_coerce_name_set(item.get("corpora", item.get("include_corpora", [])))),
                }
            )
    if not curriculum:
        curriculum = [
            {
                "name": "base",
                "weight_scale": 1,
                "family_sampling": default_sampling,
                "family_weights": {},
                "corpus_weights": {},
                "include_families": [],
                "include_corpora": [],
            }
        ]
    raw_adaptive = raw.get("adaptive", {})
    if not isinstance(raw_adaptive, dict):
        raw_adaptive = {}
    adaptive = {
        "enabled": bool(raw_adaptive.get("enabled", False)),
        "history_dir": str(raw_adaptive.get("history_dir", "")).strip(),
        "window": max(2, int(raw_adaptive.get("window", 3))),
        "min_runs": max(2, int(raw_adaptive.get("min_runs", 2))),
        "max_focus_families": max(1, int(raw_adaptive.get("max_focus_families", 2))),
        "max_stage_weight_scale": max(1, int(raw_adaptive.get("max_stage_weight_scale", 3))),
        "min_regression_delta": float(raw_adaptive.get("min_regression_delta", 0.0)),
        "min_regression_ratio": float(raw_adaptive.get("min_regression_ratio", 0.0)),
    }
    return {
        "family_sampling": default_sampling,
        "adaptive": adaptive,
        "curriculum": curriculum,
    }


def _stage_entries(entries: list[dict], stage: dict) -> list[dict]:
    include_families = set(stage.get("include_families", []))
    include_corpora = set(stage.get("include_corpora", []))
    family_weights = dict(stage.get("family_weights", {}))
    corpus_weights = dict(stage.get("corpus_weights", {}))
    selected: list[dict] = []
    for entry in entries:
        if include_families and entry["family"] not in include_families:
            continue
        if include_corpora and entry["name"] not in include_corpora:
            continue
        weight = float(entry.get("weight", 1.0))
        weight *= float(family_weights.get(entry["family"], 1.0))
        weight *= float(corpus_weights.get(entry["name"], 1.0))
        if weight <= 0.0:
            continue
        selected.append({**entry, "training_weight": float(weight)})
    if not selected:
        raise ValueError(f"curriculum stage '{stage.get('name', 'stage')}' has no active corpora")

    if stage.get("family_sampling") == "balanced":
        family_totals: dict[str, float] = defaultdict(float)
        for item in selected:
            family_totals[item["family"]] += float(item["training_weight"])
        target_total = float(sum(family_totals.values())) / float(max(1, len(family_totals)))
        balanced: list[dict] = []
        for item in selected:
            total = max(family_totals.get(item["family"], 0.0), 1e-9)
            multiplier = target_total / total if total > 0.0 else 1.0
            balanced.append(
                {
                    **item,
                    "family_balance_multiplier": float(multiplier),
                    "training_weight": float(item["training_weight"]) * float(multiplier),
                }
            )
        selected = balanced
    else:
        selected = [{**item, "family_balance_multiplier": 1.0} for item in selected]
    return selected


def _family_reports(corpora_reports: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for report in corpora_reports:
        grouped.setdefault(str(report.get("family", "default")).strip() or "default", []).append(report)

    families: list[dict] = []
    for family, reports in sorted(grouped.items()):
        valid_summary = _benchmark_split_summary([dict(item["valid"], weight=item["weight"]) for item in reports], "valid")
        train_summary = _benchmark_split_summary([dict(item["train"], weight=item["weight"]) for item in reports], "train")
        primary_split = "valid" if valid_summary["ready"] else "train"
        primary = valid_summary if primary_split == "valid" else train_summary
        families.append(
            {
                "family": family,
                "corpus_count": len(reports),
                "corpus_names": [str(item.get("name", "")) for item in reports],
                "weight_total": float(sum(float(item.get("weight", 1.0)) for item in reports)),
                "train": train_summary,
                "valid": valid_summary,
                "primary_split": primary_split,
                "primary_loss": float(primary["loss"]),
                "primary_perplexity": float(primary["perplexity"]),
            }
        )
    return families


def _benchmark_split_summary(reports: list[dict], split: str) -> dict:
    ready = [item for item in reports if bool(item.get("ready", False))]
    if not ready:
        return {"split": split, "ready": False, "loss": 0.0, "perplexity": 0.0, "token_count": 0, "weight_total": 0.0}
    weight_total = sum(float(item.get("weight", 1.0)) * max(1, int(item.get("token_count", 0))) for item in ready)
    if weight_total <= 0.0:
        weight_total = float(len(ready))
    weighted_loss = 0.0
    weighted_perplexity = 0.0
    token_count = 0
    for item in ready:
        item_weight = float(item.get("weight", 1.0)) * max(1, int(item.get("token_count", 0)))
        weighted_loss += float(item.get("loss", 0.0)) * item_weight
        weighted_perplexity += float(item.get("perplexity", 0.0)) * item_weight
        token_count += int(item.get("token_count", 0))
    return {
        "split": split,
        "ready": True,
        "loss": float(weighted_loss / weight_total),
        "perplexity": float(weighted_perplexity / weight_total),
        "token_count": int(token_count),
        "weight_total": float(weight_total),
    }


def materialize_manifest_training_corpus(
    manifest_path: str | Path = DEFAULT_BENCHMARK_MANIFEST,
    *,
    weight_scale: int = 10,
    architecture: str = "",
    tokenizer_mode: str = "",
    adaptive_history_dir: str = "",
    adaptive_enabled: bool | None = None,
) -> dict:
    manifest = load_benchmark_manifest(manifest_path)
    entries = _corpus_entries(manifest)
    training = _training_manifest_config(manifest)
    effective_tokenizer_mode = str(tokenizer_mode or manifest.get("tokenizer_mode") or "char").strip().lower() or "char"
    adaptive = dict(training.get("adaptive", {}))
    adaptive["enabled"] = bool(adaptive["enabled"] if adaptive_enabled is None else adaptive_enabled)
    if adaptive_history_dir:
        adaptive["history_dir"] = str(adaptive_history_dir).strip()
    adaptive_status = {
        "ok": True,
        "missing": False,
        "applied": False,
        "history_dir": str((ROOT / ".zero_os" / "benchmarks" / "model").resolve()),
        "cohort": benchmark_cohort_key(str(architecture or "").strip(), effective_tokenizer_mode),
        "history_count": 0,
        "required_runs": int(adaptive.get("min_runs", 2)),
        "window": int(adaptive.get("window", 3)),
        "family_signals": [],
        "recommended_stage": {},
        "reason": "adaptive_disabled",
    }
    effective_curriculum = list(training["curriculum"])
    if adaptive["enabled"]:
        history_dir_value = str(adaptive.get("history_dir", "")).strip() or ".zero_os/benchmarks/model"
        history_dir_path = Path(history_dir_value)
        if not history_dir_path.is_absolute():
            history_dir_path = (ROOT / history_dir_path).resolve()
        adaptive_status["history_dir"] = str(history_dir_path)
        try:
            try:
                from ai_from_scratch.benchmark_history import benchmark_adaptive_curriculum_status
            except ModuleNotFoundError:
                from benchmark_history import benchmark_adaptive_curriculum_status

            adaptive_status = benchmark_adaptive_curriculum_status(
                history_dir=history_dir_path,
                architecture=str(architecture or "").strip(),
                tokenizer_mode=effective_tokenizer_mode,
                window=int(adaptive.get("window", 3)),
                min_runs=int(adaptive.get("min_runs", 2)),
                max_focus_families=int(adaptive.get("max_focus_families", 2)),
                min_regression_delta=float(adaptive.get("min_regression_delta", 0.0)),
                min_regression_ratio=float(adaptive.get("min_regression_ratio", 0.0)),
                max_stage_weight_scale=int(adaptive.get("max_stage_weight_scale", 3)),
            )
        except Exception as exc:
            adaptive_status = {
                **adaptive_status,
                "ok": False,
                "applied": False,
                "reason": f"adaptive_error:{exc}",
            }
        recommended_stage = dict(adaptive_status.get("recommended_stage", {}))
        if bool(adaptive_status.get("applied", False)) and recommended_stage:
            effective_curriculum = [recommended_stage] + effective_curriculum
    scale = max(1, int(weight_scale))
    corpora: dict[str, dict] = {}
    stages: list[dict] = []
    parts: list[str] = []
    for index, stage in enumerate(effective_curriculum, start=1):
        stage_entries = _stage_entries(entries, stage)
        stage_parts: list[str] = []
        stage_reports: list[dict] = []
        stage_scale = scale * max(1, int(stage.get("weight_scale", 1)))
        for entry in stage_entries:
            corpus_path = (ROOT / entry["path"]).resolve()
            if not corpus_path.exists():
                raise FileNotFoundError(f"training corpus not found: {corpus_path}")
            text = corpus_path.read_text(encoding="utf-8", errors="replace")
            repeat_count = max(1, int(math.ceil(max(float(entry.get("training_weight", 1.0)), 0.1) * stage_scale)))
            normalized = text.rstrip()
            stage_parts.extend([normalized] * repeat_count)
            stage_report = {
                "name": entry["name"],
                "path": str(corpus_path),
                "family": str(entry.get("family", "default")),
                "weight": float(entry.get("weight", 1.0)),
                "training_weight": float(entry.get("training_weight", 1.0)),
                "family_balance_multiplier": float(entry.get("family_balance_multiplier", 1.0)),
                "repeat_count": repeat_count,
                "char_count": len(text),
            }
            stage_reports.append(stage_report)
            aggregate = corpora.setdefault(
                entry["name"],
                {
                    "name": entry["name"],
                    "path": str(corpus_path),
                    "family": str(entry.get("family", "default")),
                    "weight": float(entry.get("weight", 1.0)),
                    "repeat_count": 0,
                    "char_count": len(text),
                    "stage_repeat_counts": {},
                },
            )
            aggregate["repeat_count"] += repeat_count
            aggregate["stage_repeat_counts"][str(stage.get("name", f"stage_{index}"))] = repeat_count
        parts.extend(stage_parts)
        stages.append(
            {
                "name": str(stage.get("name", f"stage_{index}")),
                "family_sampling": str(stage.get("family_sampling", training["family_sampling"])),
                "weight_scale": max(1, int(stage.get("weight_scale", 1))),
                "corpus_count": len(stage_reports),
                "repeat_count": int(sum(item["repeat_count"] for item in stage_reports)),
                "corpora": stage_reports,
                "adaptive_source": str(stage.get("adaptive_source", "")),
            }
        )
    combined = "\n\n".join(part for part in parts if part)
    if combined and not combined.endswith("\n"):
        combined += "\n"
    return {
        "manifest": manifest,
        "manifest_path": str(Path(manifest_path).resolve()),
        "weight_scale": scale,
        "family_sampling": training["family_sampling"],
        "adaptive": adaptive_status,
        "curriculum": stages,
        "corpora": sorted(corpora.values(), key=lambda item: str(item.get("name", ""))),
        "text": combined,
    }


def build_manifest_training_dataset(
    manifest_path: str | Path = DEFAULT_BENCHMARK_MANIFEST,
    *,
    tokenizer: ZeroTokenizer | None = None,
    tokenizer_mode: str = "",
    lowercase: bool | None = None,
    valid_fraction: float | None = None,
    block_size: int = 8,
    weight_scale: int = 10,
    architecture: str = "",
    adaptive_history_dir: str = "",
    adaptive_enabled: bool | None = None,
):
    if tokenizer is not None:
        selected_tokenizer_mode = tokenizer.mode
        selected_lowercase = tokenizer.lowercase
    else:
        selected_tokenizer_mode = str(tokenizer_mode or "char").strip().lower() or "char"
        selected_lowercase = bool(lowercase) if lowercase is not None else False
    bundle = materialize_manifest_training_corpus(
        manifest_path,
        weight_scale=weight_scale,
        architecture=architecture,
        tokenizer_mode=selected_tokenizer_mode,
        adaptive_history_dir=adaptive_history_dir,
        adaptive_enabled=adaptive_enabled,
    )
    manifest = bundle["manifest"]
    if tokenizer is None:
        selected_tokenizer_mode = str(tokenizer_mode or manifest.get("tokenizer_mode") or "char").strip().lower() or "char"
        manifest_lowercase = manifest.get("lowercase")
        if lowercase is None:
            selected_lowercase = bool(manifest_lowercase) if manifest_lowercase is not None else False
        else:
            selected_lowercase = bool(lowercase)
    selected_valid_fraction = _clamp_valid_fraction(
        valid_fraction if valid_fraction is not None else float(manifest.get("valid_fraction", 0.1))
    )
    metadata = {
        "source_kind": "benchmark_manifest",
        "manifest_path": bundle["manifest_path"],
        "manifest_suite": str(manifest.get("suite", "zero_default_laws_v1")),
        "manifest_description": str(manifest.get("description", "")),
        "training_family_sampling": str(bundle.get("family_sampling", "weighted")),
        "manifest_corpus_count": len(bundle["corpora"]),
        "manifest_weight_scale": int(bundle["weight_scale"]),
        "manifest_corpora": bundle["corpora"],
        "curriculum_stage_count": len(bundle.get("curriculum", [])),
        "curriculum_stages": bundle.get("curriculum", []),
        "adaptive_curriculum_enabled": bool(dict(bundle.get("adaptive", {})).get("reason", "") != "adaptive_disabled"),
        "adaptive_curriculum_applied": bool(dict(bundle.get("adaptive", {})).get("applied", False)),
        "adaptive_curriculum_reason": str(dict(bundle.get("adaptive", {})).get("reason", "")),
        "adaptive_curriculum_history_dir": str(dict(bundle.get("adaptive", {})).get("history_dir", "")),
        "adaptive_curriculum_history_count": int(dict(bundle.get("adaptive", {})).get("history_count", 0)),
        "adaptive_curriculum_window": int(dict(bundle.get("adaptive", {})).get("window", 0)),
        "adaptive_curriculum_cohort": str(dict(bundle.get("adaptive", {})).get("cohort", "")),
        "adaptive_curriculum_stage": dict(bundle.get("adaptive", {})).get("recommended_stage", {}),
        "adaptive_curriculum_family_signals": dict(bundle.get("adaptive", {})).get("family_signals", []),
    }
    dataset = build_corpus_dataset(
        bundle["text"],
        tokenizer=tokenizer,
        tokenizer_mode=selected_tokenizer_mode,
        lowercase=selected_lowercase,
        valid_fraction=selected_valid_fraction,
        source_path=bundle["manifest_path"],
        block_size=block_size,
        metadata=metadata,
    )
    return dataset


def run_benchmark_suite(
    checkpoint_path: str,
    *,
    manifest_path: str | Path = DEFAULT_BENCHMARK_MANIFEST,
    tokenizer_mode: str = "",
    lowercase: bool | None = None,
    valid_fraction: float | None = None,
    write_manifest: bool = True,
) -> dict:
    manifest = load_benchmark_manifest(manifest_path if write_manifest else manifest_path)
    model = TinyBigramModel.load(str(checkpoint_path))
    entries = _corpus_entries(manifest)
    requested_tokenizer_mode = str(tokenizer_mode or manifest.get("tokenizer_mode") or "").strip().lower()
    if requested_tokenizer_mode and requested_tokenizer_mode != model.tokenizer_mode:
        raise ValueError("benchmark tokenizer mode must match checkpoint tokenizer mode")
    selected_tokenizer_mode = model.tokenizer_mode
    manifest_lowercase = manifest.get("lowercase")
    if lowercase is not None and bool(lowercase) != bool(model.tokenizer_lowercase):
        raise ValueError("benchmark lowercase setting must match checkpoint tokenizer normalization")
    if manifest_lowercase is not None and bool(manifest_lowercase) != bool(model.tokenizer_lowercase):
        raise ValueError("benchmark manifest lowercase setting must match checkpoint tokenizer normalization")
    selected_lowercase = bool(model.tokenizer_lowercase)
    selected_valid_fraction = _clamp_valid_fraction(
        _clamp_valid_fraction(valid_fraction)
        if valid_fraction is not None
        else float(manifest.get("valid_fraction", model.dataset_stats.get("valid_fraction", 0.1) if isinstance(model.dataset_stats, dict) else 0.1))
    )
    model_tokenizer = ZeroTokenizer.from_payload(model.tokenizer_payload())
    architecture = str(model.architecture)
    cohort = benchmark_cohort_key(architecture, selected_tokenizer_mode)

    corpora_reports: list[dict] = []
    for entry in entries:
        corpus_path = (ROOT / entry["path"]).resolve()
        if not corpus_path.exists():
            raise FileNotFoundError(f"benchmark corpus not found: {corpus_path}")
        text = corpus_path.read_text(encoding="utf-8", errors="replace")
        dataset = build_corpus_dataset(
            text,
            tokenizer=model_tokenizer,
            valid_fraction=selected_valid_fraction,
            source_path=str(corpus_path),
            block_size=model.block_size,
        )
        train_metrics = model.evaluate_split(dataset.train_ids, split="train")
        valid_metrics = model.evaluate_split(dataset.valid_ids, split="valid")
        primary_split = "valid" if valid_metrics["ready"] else "train"
        primary = valid_metrics if primary_split == "valid" else train_metrics
        corpora_reports.append(
            {
                "name": entry["name"],
                "path": str(corpus_path),
                "weight": float(entry.get("weight", 1.0)),
                "family": str(entry.get("family", "default")),
                "dataset_stats": dataset.stats,
                "train": train_metrics,
                "valid": valid_metrics,
                "primary_split": primary_split,
                "primary_loss": float(primary["loss"]),
                "primary_perplexity": float(primary["perplexity"]),
            }
        )

    valid_summary = _benchmark_split_summary([dict(item["valid"], weight=item["weight"]) for item in corpora_reports], "valid")
    train_summary = _benchmark_split_summary([dict(item["train"], weight=item["weight"]) for item in corpora_reports], "train")
    family_reports = _family_reports(corpora_reports)
    primary_split = "valid" if valid_summary["ready"] else "train"
    primary = valid_summary if primary_split == "valid" else train_summary
    return {
        "suite": str(manifest.get("suite", "zero_default_laws_v1")),
        "description": str(manifest.get("description", "")),
        "checkpoint": str(Path(checkpoint_path).resolve()),
        "manifest_path": str(Path(manifest_path).resolve()),
        "architecture": architecture,
        "tokenizer_mode": selected_tokenizer_mode,
        "cohort": cohort,
        "lowercase": bool(selected_lowercase),
        "valid_fraction": float(selected_valid_fraction),
        "corpus_count": len(corpora_reports),
        "corpora": corpora_reports,
        "family_count": len(family_reports),
        "families": family_reports,
        "train": train_summary,
        "valid": valid_summary,
        "primary_split": primary_split,
        "primary_loss": float(primary["loss"]),
        "primary_perplexity": float(primary["perplexity"]),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Run Zero AI checkpoint benchmarks across multiple local corpora")
    p.add_argument("--ckpt", default="ai_from_scratch/checkpoint.json")
    p.add_argument("--manifest", default=str(DEFAULT_BENCHMARK_MANIFEST))
    p.add_argument("--out", default=str(DEFAULT_OUTPUT))
    p.add_argument("--tokenizer-mode", default="")
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--keep-case", action="store_true")
    p.add_argument("--valid-fraction", type=float, default=-1.0)
    args = p.parse_args()

    lowercase: bool | None = None
    if args.lowercase:
        lowercase = True
    if args.keep_case:
        lowercase = False
    valid_fraction = None if args.valid_fraction < 0.0 else args.valid_fraction
    report = run_benchmark_suite(
        args.ckpt,
        manifest_path=args.manifest,
        tokenizer_mode=args.tokenizer_mode,
        lowercase=lowercase,
        valid_fraction=valid_fraction,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ai_from_scratch.benchmark_suite import build_manifest_training_dataset
    from ai_from_scratch.model import TinyBigramModel
    from ai_from_scratch.tokenizer_dataset import ZeroTokenizer, build_corpus_dataset, load_corpus_dataset
except ModuleNotFoundError:
    from benchmark_suite import build_manifest_training_dataset
    from model import TinyBigramModel
    from tokenizer_dataset import ZeroTokenizer, build_corpus_dataset, load_corpus_dataset


def _infer_valid_fraction(model: TinyBigramModel) -> float:
    stats = dict(model.dataset_stats or {})
    if "valid_fraction" in stats:
        try:
            return min(max(float(stats["valid_fraction"]), 0.0), 0.5)
        except (TypeError, ValueError):
            pass
    token_count = int(stats.get("token_count", 0))
    valid_token_count = int(stats.get("valid_token_count", 0))
    if token_count <= 0:
        return 0.1
    return min(max(float(valid_token_count) / float(token_count), 0.0), 0.5)


def _build_eval_report(model: TinyBigramModel, dataset, dataset_resolution: str) -> dict:
    train_metrics = model.evaluate_split(dataset.train_ids, split="train")
    valid_metrics = model.evaluate_split(dataset.valid_ids, split="valid")
    primary_split = "valid" if valid_metrics["ready"] else "train"
    primary = valid_metrics if primary_split == "valid" else train_metrics
    return {
        "checkpoint": "",
        "dataset_resolution": dataset_resolution,
        "dataset_source_path": dataset.source_path,
        "dataset_artifact_path": getattr(model, "dataset_artifact_path", ""),
        "tokenizer_mode": dataset.tokenizer.mode,
        "train": train_metrics,
        "valid": valid_metrics,
        "primary_split": primary_split,
        "primary_loss": float(primary["loss"]),
        "primary_perplexity": float(primary["perplexity"]),
    }


def _resolve_dataset(model: TinyBigramModel, dataset_path: str, input_path: str):
    dataset_candidate = str(dataset_path or "").strip() or str(model.dataset_artifact_path or "").strip()
    if dataset_candidate:
        dataset_file = Path(dataset_candidate)
        if dataset_file.exists():
            return load_corpus_dataset(str(dataset_file)), "artifact"

    if str((model.dataset_stats or {}).get("source_kind", "")).strip() == "benchmark_manifest":
        manifest_candidate = str(input_path or "").strip() or str((model.dataset_stats or {}).get("manifest_path", "")).strip() or str(model.dataset_source_path or "").strip()
        if manifest_candidate:
            return (
                build_manifest_training_dataset(
                    manifest_candidate,
                    tokenizer=ZeroTokenizer.from_payload(model.tokenizer_payload()),
                    valid_fraction=_infer_valid_fraction(model),
                    block_size=model.block_size,
                    weight_scale=int((model.dataset_stats or {}).get("manifest_weight_scale", 10)),
                ),
                "rebuild",
            )

    source_candidate = str(input_path or "").strip() or str(model.dataset_source_path or "").strip()
    if source_candidate:
        source_file = Path(source_candidate)
        if source_file.exists():
            text = source_file.read_text(encoding="utf-8", errors="replace")
            dataset = build_corpus_dataset(
                text,
                tokenizer=ZeroTokenizer.from_payload(model.tokenizer_payload()),
                valid_fraction=_infer_valid_fraction(model),
                source_path=str(source_file.resolve()),
                block_size=model.block_size,
            )
            return dataset, "rebuild"

    raise FileNotFoundError("dataset artifact or rebuildable source corpus not available")


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate a tiny from-scratch LM on its dataset split")
    p.add_argument("--ckpt", default="ai_from_scratch/checkpoint.json")
    p.add_argument("--dataset", default="")
    p.add_argument("--input", default="")
    args = p.parse_args()

    ckpt = Path(args.ckpt)
    model = TinyBigramModel.load(str(ckpt))
    dataset, resolution = _resolve_dataset(model, args.dataset, args.input)
    report = _build_eval_report(model, dataset, resolution)
    report["checkpoint"] = str(ckpt.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

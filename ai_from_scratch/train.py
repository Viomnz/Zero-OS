from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

try:
    from ai_from_scratch.benchmark_suite import build_manifest_training_dataset
    from ai_from_scratch.model import (
        LEGACY_ARCHITECTURE,
        NATIVE_ARCHITECTURE,
        NATIVE_ATTENTION_ARCHITECTURE,
        NATIVE_MLP_ARCHITECTURE,
        TinyBigramModel,
    )
    from ai_from_scratch.tokenizer_dataset import ZeroTokenizer, build_corpus_dataset, load_corpus_dataset
except ModuleNotFoundError:
    from benchmark_suite import build_manifest_training_dataset
    from model import LEGACY_ARCHITECTURE, NATIVE_ARCHITECTURE, NATIVE_ATTENTION_ARCHITECTURE, NATIVE_MLP_ARCHITECTURE, TinyBigramModel
    from tokenizer_dataset import ZeroTokenizer, build_corpus_dataset, load_corpus_dataset


def _default_dataset_out(model_out: str) -> str:
    path = Path(model_out)
    if path.suffix:
        return str(path.with_suffix(".dataset.json"))
    return str(path.parent / f"{path.name}.dataset.json")


def _build_eval_report(model: TinyBigramModel, dataset) -> dict:
    train_metrics = model.evaluate_split(dataset.train_ids, split="train")
    valid_metrics = model.evaluate_split(dataset.valid_ids, split="valid")
    primary_split = "valid" if valid_metrics["ready"] else "train"
    primary = valid_metrics if primary_split == "valid" else train_metrics
    return {
        "dataset_source_path": dataset.source_path,
        "tokenizer_mode": dataset.tokenizer.mode,
        "train": train_metrics,
        "valid": valid_metrics,
        "primary_split": primary_split,
        "primary_loss": float(primary["loss"]),
        "primary_perplexity": float(primary["perplexity"]),
    }


def _resolve_resume_dataset(
    model: TinyBigramModel,
    input_path: str,
    dataset_path: str,
    manifest_path: str,
    manifest_weight_scale: int,
    adaptive_history_dir: str,
    adaptive_enabled: bool | None,
):
    manifest_candidate = str(manifest_path or "").strip()
    if manifest_candidate:
        return build_manifest_training_dataset(
            manifest_candidate,
            tokenizer=ZeroTokenizer.from_payload(model.tokenizer_payload()),
            valid_fraction=float((model.dataset_stats or {}).get("valid_fraction", 0.1)),
            block_size=model.block_size,
            weight_scale=manifest_weight_scale,
            architecture=str(model.architecture),
            adaptive_history_dir=adaptive_history_dir,
            adaptive_enabled=adaptive_enabled,
        )

    source_candidate = str(input_path or "").strip()
    if source_candidate:
        source_file = Path(source_candidate)
        if source_file.exists():
            text = source_file.read_text(encoding="utf-8", errors="replace")
            return build_corpus_dataset(
                text,
                tokenizer=ZeroTokenizer.from_payload(model.tokenizer_payload()),
                valid_fraction=float((model.dataset_stats or {}).get("valid_fraction", 0.1)),
                source_path=str(source_file.resolve()),
                block_size=model.block_size,
            )

    dataset_candidate = str(dataset_path or "").strip() or str(model.dataset_artifact_path or "").strip()
    if dataset_candidate:
        dataset_file = Path(dataset_candidate)
        if dataset_file.exists():
            return load_corpus_dataset(str(dataset_file))

    if str((model.dataset_stats or {}).get("source_kind", "")).strip() == "benchmark_manifest":
        manifest_candidate = str((model.dataset_stats or {}).get("manifest_path", "")).strip() or str(model.dataset_source_path or "").strip()
        if manifest_candidate:
            return build_manifest_training_dataset(
                manifest_candidate,
                tokenizer=ZeroTokenizer.from_payload(model.tokenizer_payload()),
                valid_fraction=float((model.dataset_stats or {}).get("valid_fraction", 0.1)),
                block_size=model.block_size,
                weight_scale=int((model.dataset_stats or {}).get("manifest_weight_scale", manifest_weight_scale)),
                architecture=str(model.architecture),
                adaptive_history_dir=adaptive_history_dir,
                adaptive_enabled=adaptive_enabled,
            )

    source_candidate = str(model.dataset_source_path or "").strip()
    if source_candidate:
        source_file = Path(source_candidate)
        if source_file.exists():
            text = source_file.read_text(encoding="utf-8", errors="replace")
            return build_corpus_dataset(
                text,
                tokenizer=ZeroTokenizer.from_payload(model.tokenizer_payload()),
                valid_fraction=float((model.dataset_stats or {}).get("valid_fraction", 0.1)),
                source_path=str(source_file.resolve()),
                block_size=model.block_size,
            )

    raise FileNotFoundError("resume checkpoint requires a dataset artifact or input/source corpus path")


def _scheduled_lr(lr_start: float, lr_final: float | None, step_index: int, total_steps: int) -> float:
    if lr_final is None or total_steps <= 1:
        return float(lr_start)
    ratio = float(step_index) / float(max(1, total_steps - 1))
    return float(lr_start) + (float(lr_final) - float(lr_start)) * ratio


def _effective_eval_interval(requested: int, total_steps: int) -> int:
    if requested > 0:
        return int(requested)
    if total_steps <= 0:
        return 0
    return max(1, total_steps // 10)


def main() -> None:
    p = argparse.ArgumentParser(description="Train tiny from-scratch LM")
    p.add_argument("--input", default="")
    p.add_argument("--manifest", default="")
    p.add_argument("--manifest-weight-scale", type=int, default=10)
    p.add_argument("--resume", default="")
    p.add_argument("--adaptive-history-dir", default="")
    p.add_argument("--disable-adaptive-curriculum", action="store_true")
    p.add_argument("--steps", type=int, default=500)
    p.add_argument("--lr", type=float, default=0.1)
    p.add_argument("--lr-final", type=float, default=None)
    p.add_argument(
        "--architecture",
        default=NATIVE_ARCHITECTURE,
        choices=sorted({NATIVE_ARCHITECTURE, NATIVE_ATTENTION_ARCHITECTURE, NATIVE_MLP_ARCHITECTURE, LEGACY_ARCHITECTURE}),
    )
    p.add_argument("--block-size", type=int, default=8)
    p.add_argument("--embed-dim", type=int, default=24)
    p.add_argument("--hidden-dim", type=int, default=64)
    p.add_argument("--heads", type=int, default=4)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--grad-clip", type=float, default=1.0)
    p.add_argument("--tokenizer-mode", default="char", choices=["char", "byte"])
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--valid-fraction", type=float, default=0.1)
    p.add_argument("--keep-best-valid", action="store_true")
    p.add_argument("--eval-interval", type=int, default=0)
    p.add_argument("--out", default="ai_from_scratch/checkpoint.json")
    p.add_argument("--dataset-out", default="")
    args = p.parse_args()

    if not args.resume and not args.input and not args.manifest:
        p.error("--input or --manifest is required unless --resume is provided")

    if args.resume:
        model = TinyBigramModel.load(args.resume)
        dataset = _resolve_resume_dataset(
            model,
            args.input,
            args.dataset_out,
            args.manifest,
            args.manifest_weight_scale,
            args.adaptive_history_dir,
            None if not args.disable_adaptive_curriculum else False,
        )
        print(f"resume={args.resume}")
        if args.manifest:
            print(f"manifest={args.manifest}")
    elif args.manifest:
        dataset = build_manifest_training_dataset(
            args.manifest,
            tokenizer_mode=args.tokenizer_mode,
            lowercase=args.lowercase,
            valid_fraction=args.valid_fraction,
            block_size=args.block_size,
            weight_scale=args.manifest_weight_scale,
            architecture=args.architecture,
            adaptive_history_dir=args.adaptive_history_dir,
            adaptive_enabled=None if not args.disable_adaptive_curriculum else False,
        )
        model = TinyBigramModel.build(
            dataset.source_text,
            architecture=args.architecture,
            block_size=args.block_size,
            embed_dim=args.embed_dim,
            hidden_dim=args.hidden_dim,
            attention_heads=args.heads,
            tokenizer=dataset.tokenizer,
            dataset_source_path=dataset.source_path,
            dataset_stats=dataset.stats,
        )
        print(f"manifest={args.manifest}")
    else:
        text = Path(args.input).read_text(encoding="utf-8", errors="replace")
        dataset = build_corpus_dataset(
            text,
            tokenizer_mode=args.tokenizer_mode,
            lowercase=args.lowercase,
            valid_fraction=args.valid_fraction,
            source_path=str(Path(args.input).resolve()),
            block_size=args.block_size,
        )
        model = TinyBigramModel.build(
            text,
            architecture=args.architecture,
            block_size=args.block_size,
            embed_dim=args.embed_dim,
            hidden_dim=args.hidden_dim,
            attention_heads=args.heads,
            tokenizer=dataset.tokenizer,
            dataset_source_path=dataset.source_path,
            dataset_stats=dataset.stats,
        )

    ids = dataset.train_ids
    progress_interval = max(1, args.steps // 10) if args.steps > 0 else 1
    eval_interval = _effective_eval_interval(args.eval_interval, args.steps)
    best_model = copy.deepcopy(model) if args.keep_best_valid else None
    best_eval_report = _build_eval_report(model, dataset) if args.keep_best_valid else None
    best_primary = float(best_eval_report["primary_perplexity"]) if best_eval_report is not None else None

    for i in range(args.steps):
        rate = _scheduled_lr(args.lr, args.lr_final, i, args.steps)
        loss = model.train_step(
            ids,
            lr=rate,
            batch_size=args.batch_size,
            weight_decay=args.weight_decay,
            grad_clip=args.grad_clip,
        )
        if i % progress_interval == 0 or i == args.steps - 1:
            print(f"step={i} lr={rate:.5f} loss={loss:.4f}")
        if args.keep_best_valid and ((i + 1) % eval_interval == 0 or i == args.steps - 1):
            report = _build_eval_report(model, dataset)
            primary = float(report["primary_perplexity"])
            if best_primary is None or primary < best_primary:
                best_primary = primary
                best_eval_report = report
                best_model = copy.deepcopy(model)
                print(f"best_eval_step={i + 1} primary_ppl={primary:.4f}")

    dataset_out = args.dataset_out or str(model.dataset_artifact_path or "") or _default_dataset_out(args.out)
    if args.keep_best_valid and best_model is not None and best_eval_report is not None:
        model = best_model
        eval_report = best_eval_report
        print(f"restored_best_primary_ppl={best_primary:.4f}")
    else:
        eval_report = _build_eval_report(model, dataset)

    model.dataset_source_path = dataset.source_path
    model.dataset_stats = dataset.stats
    model.dataset_artifact_path = str(Path(dataset_out).resolve())
    model.eval_metrics = eval_report
    model.save(args.out)
    dataset.save(dataset_out, include_ids=True)
    print(f"saved={args.out}")
    print("dataset=" + json.dumps({"dataset_out": dataset_out, "dataset_stats": dataset.stats}, sort_keys=True))
    print("eval=" + json.dumps(eval_report, sort_keys=True))
    print(f"model_info={model.metadata()}")


if __name__ == "__main__":
    main()

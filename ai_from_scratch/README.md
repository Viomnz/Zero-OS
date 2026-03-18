# Tiny AI From Scratch

This is a from-scratch baseline language model built with Python + NumPy (no ML framework).
The default base model is now a fully native character-level multi-head attention model
with embeddings, a feed-forward hidden layer, checkpoint metadata, and legacy bigram compatibility.

## Files
- `model.py`: native character-level base model (multi-head attention + MLP fallback + legacy bigram compatibility)
- `tokenizer_dataset.py`: tokenizer + dataset pipeline (char or byte, train/valid split, dataset artifacts)
- `train.py`: trains on your text corpus
- `eval.py`: evaluates a checkpoint on its dataset split and reports loss + perplexity
- `benchmark_suite.py`: runs a checkpoint across a multi-corpus benchmark suite
- `benchmark_history.py`: records benchmark runs, shows history, and compares trends
- `born_rule_filtration.py`: derives the Born rule from filtration conditions and checks the surviving exponent family
- `relativistic_layer_geometry.py`: derives Lorentz/Minkowski spacetime from classical layered geometry plus invariant causal speed
- `generate.py`: samples text from trained weights

## Quick start
```powershell
python ai_from_scratch/train.py --input laws/recursion_law.txt --steps 500
python ai_from_scratch/generate.py --prompt "Recursion" --length 200
python ai_from_scratch/generate.py --prompt "self awareness pressure balance" --length 200 --enforce-laws
python ai_from_scratch/train.py --input laws/recursion_law.txt --steps 1000 --block-size 12 --embed-dim 32 --hidden-dim 96 --heads 4
python ai_from_scratch/train.py --input laws/recursion_law.txt --steps 500 --tokenizer-mode byte --dataset-out ai_from_scratch/checkpoint.dataset.json
python ai_from_scratch/train.py --manifest laws/model_benchmark_suite.json --steps 20 --lr 0.008 --lr-final 0.002 --keep-best-valid --eval-interval 1
python ai_from_scratch/train.py --resume ai_from_scratch/checkpoint.json --steps 20 --lr 0.012 --lr-final 0.004 --keep-best-valid --eval-interval 1
python ai_from_scratch/train.py --resume ai_from_scratch/checkpoint.json --manifest laws/model_benchmark_suite.json --steps 12 --lr 0.009 --lr-final 0.0025 --keep-best-valid --eval-interval 1
python ai_from_scratch/train.py --manifest laws/model_benchmark_suite.json --steps 12 --adaptive-history-dir .zero_os/benchmarks/model
python ai_from_scratch/eval.py --ckpt ai_from_scratch/checkpoint.json
python ai_from_scratch/benchmark_suite.py --ckpt ai_from_scratch/checkpoint.json
python ai_from_scratch/benchmark_history.py run --ckpt ai_from_scratch/checkpoint.json --label baseline
python ai_from_scratch/benchmark_history.py history
python ai_from_scratch/benchmark_history.py cohorts
python ai_from_scratch/benchmark_history.py families
python ai_from_scratch/benchmark_history.py chart
python ai_from_scratch/benchmark_history.py chart --family law_core
python ai_from_scratch/benchmark_history.py gate --write
python ai_from_scratch/benchmark_history.py alerts --write
python ai_from_scratch/benchmark_history.py dashboard --write
python ai_from_scratch/benchmark_history.py remediation --write
python ai_from_scratch/benchmark_history.py run --ckpt ai_from_scratch/checkpoint.json --label ci --strict-gate
python ai_from_scratch/benchmark_history.py compare --write
```

## Tokenizer + Dataset Pipeline
- Live now in the training/checkpoint path
- Tokenizer modes: `char`, `byte`
- Optional normalization: `--lowercase`
- Train/valid split: `--valid-fraction`
- Dataset artifact: `--dataset-out`
- Native multi-corpus manifest training: `--manifest laws/model_benchmark_suite.json`
- Manifest training now supports curriculum stages and family-balanced sampling through the manifest `training` block
- Manifest training can now inject an adaptive regression-focus stage from same-cohort benchmark history
- Use `--adaptive-history-dir` to point training at a different benchmark history root, or `--disable-adaptive-curriculum` to force static manifest stages
- Checkpoints now persist tokenizer and dataset metadata so generation stays aligned with training

## Eval + Perplexity
- Training now emits split-level `eval=` output for `train` and `valid`
- Resume training can now keep the best validation checkpoint instead of blindly saving the final step
- Resume training can also switch to a new explicit input corpus while preserving checkpoint tokenizer alignment
- Manifest-trained checkpoints can rebuild eval datasets directly from the benchmark manifest when the dataset artifact is missing
- Checkpoints persist the last eval report, dataset source path, and dataset artifact path
- `eval.py` can evaluate a saved checkpoint from its dataset artifact or rebuild the split from the original corpus when needed
- Primary metric is validation perplexity when a validation split exists, otherwise training perplexity

## Benchmark Suite
- Default suite manifest: [model_benchmark_suite.json](/Users/gomez/Documents/New%20folder/laws/model_benchmark_suite.json)
- Benchmarks run one checkpoint across multiple local corpora and compute weighted aggregate train/valid loss + perplexity
- Corpora can be sliced into named `family` groups so the suite reports both whole-suite and family-level metrics
- The suite uses the checkpoint tokenizer contract, so benchmark ids stay aligned with the trained model
- Output is written to `.zero_os/runtime/model_benchmark.json` by default

## Benchmark History
- Recorded runs are stored under `.zero_os/benchmarks/model/`
- `benchmark_history.py run` updates `latest.json`, appends `history.jsonl`, refreshes summaries, and evaluates the benchmark gate
- `benchmark_history.py cohorts` summarizes benchmark cohorts by architecture + tokenizer
- `benchmark_history.py families` shows the latest family slices from the selected run history
- `benchmark_history.py chart` prints richer ASCII trend charts with separate primary, valid, and train series
- `benchmark_history.py chart --family law_core` shows family-level charts across history
- `benchmark_history.py gate` evaluates the latest filtered run against threshold + regression rules
- `benchmark_history.py alerts` routes gate alerts into named lanes like `ci_blocker`, `regression_watch`, and `family_watch`
- `benchmark_history.py dashboard` renders a compact benchmark dashboard from the latest filtered history
- `benchmark_history.py remediation` proposes a safe candidate training run when the latest cohort regresses or the benchmark gate fails
- `benchmark_history.py run --strict-gate` exits non-zero when the benchmark gate fails, which is useful for CI
- `benchmark_history.py compare --write` writes `compare_latest.md` with previous-vs-latest perplexity trends
- Adaptive manifest training now reads same-cohort benchmark history and only focuses extra training on families that actually regressed
- Remediation proposals write a candidate checkpoint path and follow-up benchmark command instead of overwriting the live model
- Zero OS now adds approval-gated remediation execution on top of those proposals through `zero ai benchmark remediation request`, `approve`, `reject`, and `execute`
- Default thresholds live in [model_benchmark_thresholds.json](/Users/gomez/Documents/New%20folder/laws/model_benchmark_thresholds.json)
- Default alert-route policy lives in [model_benchmark_alert_routes.json](/Users/gomez/Documents/New%20folder/laws/model_benchmark_alert_routes.json)
- History exports now include `dashboard_latest.md`, `dashboard_latest.json`, `alert_routes.json`, `gate_latest.json`, `alerts_latest.md`, `families_summary.md`, `family_trend_charts.md`, and `trend_charts.json`
- History exports now also include `remediation_latest.md` and `remediation_latest.json`
- Lower perplexity is treated as improvement

## Universe Law Guard
- `--enforce-laws` forces generation through Universe Laws 1, 2, 3 checks.
- Required cycle terms:
  - Law 1: awareness/self
  - Law 2: pressure/contradiction/stress
  - Law 3: balance/harmony/stability
- If no sample passes within `--max-attempts`, output is marked blocked.

## Physics Derivation Note
- Formal spec: [born_rule_from_filtration.md](/Users/gomez/Documents/New%20folder/docs/physics/born_rule_from_filtration.md)
- Executable checker: [born_rule_filtration.py](/Users/gomez/Documents/New%20folder/ai_from_scratch/born_rule_filtration.py)
- Result: within the power-law candidate family, coarse-grain additivity plus normalization and continuity selects `P(a) = |a|^2`
- Relativistic extension spec: [spacetime_from_classical_layer_geometry.md](/Users/gomez/Documents/New%20folder/docs/physics/spacetime_from_classical_layer_geometry.md)
- Relativistic checker: [relativistic_layer_geometry.py](/Users/gomez/Documents/New%20folder/ai_from_scratch/relativistic_layer_geometry.py)
- Result: within the checked candidate family, invariant causal speed selects Lorentz/Minkowski geometry over the Galilean alternative

## Always-on daemon
Run Zero-AI continuously in background:

```powershell
python ai_from_scratch/daemon_ctl.py start
python ai_from_scratch/daemon_ctl.py status
python ai_from_scratch/daemon_ctl.py task --prompt "self awareness pressure balance"
python ai_from_scratch/daemon_ctl.py task --prompt "scan"
python ai_from_scratch/daemon_ctl.py stop
```

Runtime files:
- `.zero_os/runtime/zero_ai_heartbeat.json`
- `.zero_os/runtime/zero_ai_tasks.txt`
- `.zero_os/runtime/zero_ai_output.txt`
- `.zero_os/runtime/zero_ai_scan_report.json`
- `.zero_os/runtime/zero_ai_monitor.json`
- `.zero_os/runtime/open_system_state.json`
- `.zero_os/backup/latest/*` (second backup snapshot)

## Open-System Logic Loop
Zero-AI now runs an open logic cycle for each prompt:

`Environment -> Input -> Filter -> Adapt/Reject -> Stable State -> Repeat`

- Neutral baseline starts from stable equilibrium.
- Contradiction filter scores conflicting signal pairs.
- Adaptive update accepts low-contradiction input and updates state.
- Re-stabilization converges logic back to equilibrium each cycle.

Daemon output now includes an `[OPEN_SYSTEM_LOGIC]` block per prompt.

## Model status
- Default architecture: `zero_native_char_attention_v1`
- Fully native: Python + NumPy only
- Multi-head attention: yes
- Production-ready checkpoint metadata: yes
- Backward-compatible with legacy `logits` checkpoints: yes
- Backward-compatible with native MLP checkpoints: yes

## Next upgrades
1. Add rotary or relative position encoding
2. Add deeper dataset curation and sampling controls
3. Add benchmark cohort drilldowns and action-triggered remediation from the Zero OS control surfaces
4. Add safe one-click execution for remediation candidates after explicit approval

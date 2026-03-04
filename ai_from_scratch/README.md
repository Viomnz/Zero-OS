# Tiny AI From Scratch

This is a from-scratch baseline language model built with Python + NumPy (no ML framework).

## Files
- `model.py`: tiny character-level model (bigram + trainable logits)
- `train.py`: trains on your text corpus
- `generate.py`: samples text from trained weights

## Quick start
```powershell
python ai_from_scratch/train.py --input laws/recursion_law.txt --steps 500
python ai_from_scratch/generate.py --prompt "Recursion" --length 200
python ai_from_scratch/generate.py --prompt "self awareness pressure balance" --length 200 --enforce-laws
```

## Universe Law Guard
- `--enforce-laws` forces generation through Universe Laws 1, 2, 3 checks.
- Required cycle terms:
  - Law 1: awareness/self
  - Law 2: pressure/contradiction/stress
  - Law 3: balance/harmony/stability
- If no sample passes within `--max-attempts`, output is marked blocked.

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
- `.zero_os/backup/latest/*` (second backup snapshot)

## Next upgrades
1. Add MLP hidden layer
2. Add multi-head attention block
3. Add tokenizer + dataset pipeline
4. Add checkpoint versioning and eval metrics

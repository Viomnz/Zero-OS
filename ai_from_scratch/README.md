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
```

## Next upgrades
1. Add MLP hidden layer
2. Add multi-head attention block
3. Add tokenizer + dataset pipeline
4. Add checkpoint versioning and eval metrics

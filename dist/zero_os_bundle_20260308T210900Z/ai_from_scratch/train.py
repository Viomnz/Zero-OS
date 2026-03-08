from __future__ import annotations

import argparse
from pathlib import Path

from model import TinyBigramModel


def main() -> None:
    p = argparse.ArgumentParser(description="Train tiny from-scratch LM")
    p.add_argument("--input", required=True)
    p.add_argument("--steps", type=int, default=500)
    p.add_argument("--lr", type=float, default=0.1)
    p.add_argument("--out", default="ai_from_scratch/checkpoint.json")
    args = p.parse_args()

    text = Path(args.input).read_text(encoding="utf-8", errors="replace")
    model = TinyBigramModel.build(text)
    ids = model.encode(text)

    for i in range(args.steps):
        loss = model.train_step(ids, lr=args.lr)
        if i % max(1, args.steps // 10) == 0:
            print(f"step={i} loss={loss:.4f}")

    model.save(args.out)
    print(f"saved={args.out}")


if __name__ == "__main__":
    main()

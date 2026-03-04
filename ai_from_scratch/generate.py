from __future__ import annotations

import argparse

from model import TinyBigramModel


def main() -> None:
    p = argparse.ArgumentParser(description="Generate from tiny from-scratch LM")
    p.add_argument("--ckpt", default="ai_from_scratch/checkpoint.json")
    p.add_argument("--prompt", default="R")
    p.add_argument("--length", type=int, default=200)
    p.add_argument("--temperature", type=float, default=1.0)
    args = p.parse_args()

    model = TinyBigramModel.load(args.ckpt)
    out = model.sample(args.prompt, length=args.length, temperature=args.temperature)
    print(out)


if __name__ == "__main__":
    main()

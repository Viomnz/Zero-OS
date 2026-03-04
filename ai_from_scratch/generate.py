from __future__ import annotations

import argparse

from model import TinyBigramModel
from universe_laws_guard import check_universe_laws


def main() -> None:
    p = argparse.ArgumentParser(description="Generate from tiny from-scratch LM")
    p.add_argument("--ckpt", default="ai_from_scratch/checkpoint.json")
    p.add_argument("--prompt", default="R")
    p.add_argument("--length", type=int, default=200)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--max-attempts", type=int, default=20)
    p.add_argument("--enforce-laws", action="store_true")
    args = p.parse_args()

    model = TinyBigramModel.load(args.ckpt)
    if not args.enforce_laws:
        out = model.sample(args.prompt, length=args.length, temperature=args.temperature)
        print(out)
        return

    for i in range(args.max_attempts):
        out = model.sample(
            args.prompt,
            length=args.length,
            temperature=args.temperature,
            seed=123 + i,
        )
        check = check_universe_laws(out)
        if check.passed:
            print("[UNIVERSE_LAWS_PASS]")
            print(out)
            return

    final = check_universe_laws(out)
    print("[UNIVERSE_LAWS_BLOCKED]")
    print(final.reason)
    print(out)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import sys

try:
    from ai_from_scratch.model import TinyBigramModel
    from ai_from_scratch.universe_laws_guard import check_universe_laws
except ModuleNotFoundError:
    from model import TinyBigramModel
    from universe_laws_guard import check_universe_laws


def _emit(text: str) -> None:
    content = str(text)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        print(content)
        return
    except UnicodeEncodeError:
        pass
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write((content + "\n").encode("utf-8", errors="replace"))
        buffer.flush()
        return
    sys.stdout.write(content.encode("ascii", errors="replace").decode("ascii") + "\n")


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
        _emit(out)
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
            _emit("[UNIVERSE_LAWS_PASS]")
            _emit(out)
            return

    final = check_universe_laws(out)
    _emit("[UNIVERSE_LAWS_BLOCKED]")
    _emit(final.reason)
    _emit(out)


if __name__ == "__main__":
    main()

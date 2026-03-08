from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class TinyBigramModel:
    vocab: list[str]
    stoi: dict[str, int]
    itos: dict[int, str]
    logits: np.ndarray

    @classmethod
    def build(cls, text: str, seed: int = 42) -> "TinyBigramModel":
        chars = sorted(set(text))
        stoi = {c: i for i, c in enumerate(chars)}
        itos = {i: c for i, c in enumerate(chars)}
        rng = np.random.default_rng(seed)
        logits = rng.normal(0, 0.01, size=(len(chars), len(chars))).astype(np.float64)
        return cls(vocab=chars, stoi=stoi, itos=itos, logits=logits)

    def encode(self, s: str) -> list[int]:
        return [self.stoi[c] for c in s if c in self.stoi]

    def decode(self, ids: list[int]) -> str:
        return "".join(self.itos[i] for i in ids)

    def train_step(self, ids: list[int], lr: float = 0.1) -> float:
        if len(ids) < 2:
            return 0.0
        total_loss = 0.0
        grad = np.zeros_like(self.logits)
        for a, b in zip(ids[:-1], ids[1:]):
            row = self.logits[a]
            row = row - np.max(row)
            probs = np.exp(row)
            probs = probs / np.sum(probs)
            total_loss += -np.log(probs[b] + 1e-12)
            g = probs.copy()
            g[b] -= 1.0
            grad[a] += g

        n = max(1, len(ids) - 1)
        self.logits -= lr * (grad / n)
        return float(total_loss / n)

    def sample(self, prompt: str, length: int = 200, temperature: float = 1.0, seed: int = 123) -> str:
        rng = np.random.default_rng(seed)
        ids = self.encode(prompt)
        if not ids:
            ids = [0]
        cur = ids[-1]
        out = ids.copy()

        for _ in range(length):
            row = self.logits[cur] / max(temperature, 1e-6)
            row = row - np.max(row)
            probs = np.exp(row)
            probs = probs / np.sum(probs)
            nxt = int(rng.choice(len(self.vocab), p=probs))
            out.append(nxt)
            cur = nxt
        return self.decode(out)

    def save(self, path: str) -> None:
        payload = {
            "vocab": self.vocab,
            "logits": self.logits.tolist(),
        }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TinyBigramModel":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        vocab = payload["vocab"]
        stoi = {c: i for i, c in enumerate(vocab)}
        itos = {i: c for i, c in enumerate(vocab)}
        logits = np.array(payload["logits"], dtype=np.float64)
        return cls(vocab=vocab, stoi=stoi, itos=itos, logits=logits)

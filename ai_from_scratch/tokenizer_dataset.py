from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


_TOKENIZER_MODES = {"char", "byte"}
_BASE_STAT_KEYS = {
    "source_path",
    "tokenizer_mode",
    "lowercase",
    "vocab_size",
    "token_count",
    "train_token_count",
    "valid_token_count",
    "train_example_count",
    "valid_example_count",
    "block_size",
    "valid_fraction",
}


@dataclass
class ZeroTokenizer:
    mode: str
    vocab: list[str]
    lowercase: bool = False
    token_to_id: dict[str, int] = field(init=False)
    id_to_token: dict[int, str] = field(init=False)

    def __post_init__(self) -> None:
        selected = str(self.mode or "char").strip().lower()
        if selected not in _TOKENIZER_MODES:
            raise ValueError(f"unsupported tokenizer mode: {self.mode}")
        self.mode = selected
        self.vocab = list(self.vocab)
        self.token_to_id = {token: idx for idx, token in enumerate(self.vocab)}
        self.id_to_token = {idx: token for idx, token in enumerate(self.vocab)}

    @classmethod
    def build(cls, text: str, mode: str = "char", lowercase: bool = False) -> "ZeroTokenizer":
        selected = str(mode or "char").strip().lower()
        if selected == "byte":
            vocab = [f"b:{value}" for value in range(256)]
            return cls(mode=selected, vocab=vocab, lowercase=lowercase)
        normalized = str(text or "")
        if lowercase:
            normalized = normalized.lower()
        vocab = sorted(set(normalized or " "))
        return cls(mode=selected, vocab=vocab, lowercase=lowercase)

    @classmethod
    def from_payload(cls, payload: dict | None) -> "ZeroTokenizer":
        raw = payload or {}
        return cls(
            mode=str(raw.get("mode", "char")).strip().lower(),
            vocab=list(raw.get("vocab", [])),
            lowercase=bool(raw.get("lowercase", False)),
        )

    def to_payload(self) -> dict:
        return {
            "mode": self.mode,
            "vocab": list(self.vocab),
            "lowercase": bool(self.lowercase),
            "vocab_size": len(self.vocab),
        }

    def _normalize(self, text: str) -> str:
        normalized = str(text or "")
        return normalized.lower() if self.lowercase else normalized

    def tokenize(self, text: str) -> list[str]:
        normalized = self._normalize(text)
        if self.mode == "byte":
            return [f"b:{value}" for value in normalized.encode("utf-8")]
        return list(normalized)

    def encode(self, text: str) -> list[int]:
        ids: list[int] = []
        for token in self.tokenize(text):
            if token in self.token_to_id:
                ids.append(self.token_to_id[token])
        return ids

    def decode_tokens(self, tokens: list[str]) -> str:
        if self.mode == "byte":
            values: list[int] = []
            for token in tokens:
                if isinstance(token, str) and token.startswith("b:"):
                    try:
                        values.append(int(token.split(":", 1)[1]))
                    except ValueError:
                        continue
            return bytes(values).decode("utf-8", errors="replace")
        return "".join(tokens)

    def decode_ids(self, ids: list[int]) -> str:
        tokens = [self.id_to_token[idx] for idx in ids if idx in self.id_to_token]
        return self.decode_tokens(tokens)


@dataclass
class CorpusDataset:
    tokenizer: ZeroTokenizer
    source_text: str
    train_ids: list[int]
    valid_ids: list[int]
    source_path: str = ""
    block_size: int = 8
    valid_fraction: float = 0.1
    metadata: dict = field(default_factory=dict)

    @property
    def stats(self) -> dict:
        total = len(self.train_ids) + len(self.valid_ids)
        payload = {
            "source_path": self.source_path,
            "tokenizer_mode": self.tokenizer.mode,
            "lowercase": bool(self.tokenizer.lowercase),
            "vocab_size": len(self.tokenizer.vocab),
            "token_count": total,
            "train_token_count": len(self.train_ids),
            "valid_token_count": len(self.valid_ids),
            "train_example_count": max(0, len(self.train_ids) - 1),
            "valid_example_count": max(0, len(self.valid_ids) - 1),
            "block_size": int(self.block_size),
            "valid_fraction": float(self.valid_fraction),
        }
        if isinstance(self.metadata, dict):
            payload.update(self.metadata)
        return payload

    def to_payload(self, include_ids: bool = True) -> dict:
        payload = {
            "tokenizer": self.tokenizer.to_payload(),
            "source_path": self.source_path,
            "stats": self.stats,
        }
        if include_ids:
            payload["train_ids"] = list(self.train_ids)
            payload["valid_ids"] = list(self.valid_ids)
        return payload

    def save(self, path: str, include_ids: bool = True) -> None:
        Path(path).write_text(json.dumps(self.to_payload(include_ids=include_ids), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_payload(cls, payload: dict, source_text: str = "") -> "CorpusDataset":
        tokenizer = ZeroTokenizer.from_payload(payload.get("tokenizer", {}))
        stats = payload.get("stats", {}) if isinstance(payload, dict) else {}
        metadata = {}
        if isinstance(stats, dict):
            metadata = {key: value for key, value in stats.items() if key not in _BASE_STAT_KEYS}
        return cls(
            tokenizer=tokenizer,
            source_text=source_text,
            train_ids=list(payload.get("train_ids", [])),
            valid_ids=list(payload.get("valid_ids", [])),
            source_path=str(payload.get("source_path", "")),
            block_size=int(stats.get("block_size", 8)),
            valid_fraction=float(stats.get("valid_fraction", 0.1)),
            metadata=metadata,
        )


def build_corpus_dataset(
    text: str,
    *,
    tokenizer: ZeroTokenizer | None = None,
    tokenizer_mode: str = "char",
    lowercase: bool = False,
    valid_fraction: float = 0.1,
    source_path: str = "",
    block_size: int = 8,
    metadata: dict | None = None,
) -> CorpusDataset:
    active_tokenizer = tokenizer or ZeroTokenizer.build(text, mode=tokenizer_mode, lowercase=lowercase)
    ids = active_tokenizer.encode(text)
    fraction = min(max(float(valid_fraction), 0.0), 0.5)
    if len(ids) <= 1:
        train_ids = list(ids)
        valid_ids: list[int] = []
    else:
        split_at = int(round(len(ids) * (1.0 - fraction)))
        split_at = min(max(1, split_at), len(ids) - 1)
        train_ids = ids[:split_at]
        valid_ids = ids[split_at:]
    return CorpusDataset(
        tokenizer=active_tokenizer,
        source_text=str(text or ""),
        train_ids=train_ids,
        valid_ids=valid_ids,
        source_path=source_path,
        block_size=block_size,
        valid_fraction=fraction,
        metadata=dict(metadata or {}),
    )


def load_corpus_dataset(path: str, source_text: str = "") -> CorpusDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    return CorpusDataset.from_payload(payload, source_text=source_text)

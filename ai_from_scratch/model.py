from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    from ai_from_scratch.tokenizer_dataset import ZeroTokenizer
except ModuleNotFoundError:
    from tokenizer_dataset import ZeroTokenizer


NATIVE_MLP_ARCHITECTURE = "zero_native_char_mlp_v1"
NATIVE_ATTENTION_ARCHITECTURE = "zero_native_char_attention_v1"
NATIVE_ARCHITECTURE = NATIVE_ATTENTION_ARCHITECTURE
LEGACY_ARCHITECTURE = "zero_legacy_bigram_v1"
DEFAULT_ATTENTION_HEADS = 4
_SUPPORTED_ARCHITECTURES = {
    NATIVE_MLP_ARCHITECTURE,
    NATIVE_ATTENTION_ARCHITECTURE,
    LEGACY_ARCHITECTURE,
    "legacy_table_v1",
}


def _softmax_rows(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)


def _as_float_array(value: object) -> np.ndarray:
    return np.array(value, dtype=np.float64)


def _clip(grad: np.ndarray, limit: float) -> np.ndarray:
    return np.clip(grad, -limit, limit)


def _resolve_attention_heads(embed_dim: int, requested_heads: int) -> int:
    requested = max(1, int(requested_heads))
    upper = min(max(1, int(embed_dim)), requested)
    for heads in range(upper, 0, -1):
        if int(embed_dim) % heads == 0:
            return heads
    return 1


def _reshape_heads(values: np.ndarray, heads: int) -> np.ndarray:
    batch, tokens, embed_dim = values.shape
    head_dim = embed_dim // max(1, heads)
    return values.reshape(batch, tokens, heads, head_dim).transpose(0, 2, 1, 3)


def _merge_heads(values: np.ndarray) -> np.ndarray:
    batch, heads, tokens, head_dim = values.shape
    return values.transpose(0, 2, 1, 3).reshape(batch, tokens, heads * head_dim)


def inspect_checkpoint_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "checkpoint malformed", "architecture": "", "native": False}

    vocab = payload.get("vocab")
    if not isinstance(vocab, list):
        vocab = []
    tokenizer_payload = payload.get("tokenizer", {})
    if isinstance(tokenizer_payload, dict):
        tokenizer_vocab = tokenizer_payload.get("vocab")
        if not vocab and isinstance(tokenizer_vocab, list):
            vocab = list(tokenizer_vocab)
        tokenizer_mode = str(tokenizer_payload.get("mode", "char")).strip().lower() or "char"
        tokenizer_lowercase = bool(tokenizer_payload.get("lowercase", False))
    else:
        tokenizer_mode = "char"
        tokenizer_lowercase = False
    architecture = str(payload.get("architecture", "")).strip() or LEGACY_ARCHITECTURE

    if "table" in payload and isinstance(payload.get("table"), list):
        return {
            "ok": True,
            "reason": "legacy table checkpoint",
            "architecture": "legacy_table_v1",
            "native": False,
            "vocab_size": int(payload.get("vocab_size", len(vocab))),
            "block_size": 1,
            "embed_dim": 0,
            "hidden_dim": 0,
            "heads": 0,
            "tokenizer_mode": tokenizer_mode,
            "tokenizer_lowercase": tokenizer_lowercase,
        }

    if "logits" in payload and isinstance(vocab, list) and vocab:
        return {
            "ok": True,
            "reason": "legacy bigram checkpoint",
            "architecture": architecture if architecture in _SUPPORTED_ARCHITECTURES else LEGACY_ARCHITECTURE,
            "native": False,
            "vocab_size": len(vocab),
            "block_size": int(payload.get("block_size", 1)),
            "embed_dim": int(payload.get("embed_dim", 0)),
            "hidden_dim": int(payload.get("hidden_dim", 0)),
            "heads": 0,
            "tokenizer_mode": tokenizer_mode,
            "tokenizer_lowercase": tokenizer_lowercase,
        }

    weights = payload.get("weights")
    if isinstance(vocab, list) and vocab and isinstance(weights, dict):
        if architecture == NATIVE_MLP_ARCHITECTURE:
            required = ("embeddings", "w1", "b1", "w2", "b2")
            if all(isinstance(weights.get(key), list) for key in required):
                return {
                    "ok": True,
                    "reason": "native mlp checkpoint",
                    "architecture": architecture,
                    "native": True,
                    "vocab_size": len(vocab),
                    "block_size": int(payload.get("block_size", 8)),
                    "embed_dim": int(payload.get("embed_dim", 24)),
                    "hidden_dim": int(payload.get("hidden_dim", 64)),
                    "heads": 0,
                    "tokenizer_mode": tokenizer_mode,
                    "tokenizer_lowercase": tokenizer_lowercase,
                }
        if architecture == NATIVE_ATTENTION_ARCHITECTURE:
            required = (
                "embeddings",
                "position_embeddings",
                "q_proj",
                "k_proj",
                "v_proj",
                "attention_out",
                "w1",
                "b1",
                "w2",
                "b2",
                "lm_head",
                "lm_bias",
            )
            if all(isinstance(weights.get(key), list) for key in required):
                return {
                    "ok": True,
                    "reason": "native attention checkpoint",
                    "architecture": architecture,
                    "native": True,
                    "vocab_size": len(vocab),
                    "block_size": int(payload.get("block_size", 8)),
                    "embed_dim": int(payload.get("embed_dim", 24)),
                    "hidden_dim": int(payload.get("hidden_dim", 64)),
                    "heads": int(payload.get("heads", DEFAULT_ATTENTION_HEADS)),
                    "tokenizer_mode": tokenizer_mode,
                    "tokenizer_lowercase": tokenizer_lowercase,
                }

    return {"ok": False, "reason": "checkpoint malformed", "architecture": architecture, "native": False}


@dataclass
class TinyBigramModel:
    vocab: list[str]
    stoi: dict[str, int]
    itos: dict[int, str]
    architecture: str
    logits: np.ndarray | None = None
    block_size: int = 8
    embed_dim: int = 24
    hidden_dim: int = 64
    embeddings: np.ndarray | None = None
    position_embeddings: np.ndarray | None = None
    q_proj: np.ndarray | None = None
    k_proj: np.ndarray | None = None
    v_proj: np.ndarray | None = None
    attention_out: np.ndarray | None = None
    w1: np.ndarray | None = None
    b1: np.ndarray | None = None
    w2: np.ndarray | None = None
    b2: np.ndarray | None = None
    lm_head: np.ndarray | None = None
    lm_bias: np.ndarray | None = None
    attention_heads: int = DEFAULT_ATTENTION_HEADS
    training_steps: int = 0
    tokenizer_mode: str = "char"
    tokenizer_lowercase: bool = False
    dataset_source_path: str = ""
    dataset_artifact_path: str = ""
    dataset_stats: dict | None = None
    eval_metrics: dict | None = None

    @classmethod
    def build(
        cls,
        text: str,
        seed: int = 42,
        architecture: str = NATIVE_ARCHITECTURE,
        block_size: int = 8,
        embed_dim: int = 24,
        hidden_dim: int = 64,
        attention_heads: int = DEFAULT_ATTENTION_HEADS,
        tokenizer: ZeroTokenizer | None = None,
        dataset_source_path: str = "",
        dataset_artifact_path: str = "",
        dataset_stats: dict | None = None,
        eval_metrics: dict | None = None,
    ) -> "TinyBigramModel":
        active_tokenizer = tokenizer or ZeroTokenizer.build(text, mode="char", lowercase=False)
        chars = list(active_tokenizer.vocab or [" "])
        stoi = {c: i for i, c in enumerate(chars)}
        itos = {i: c for i, c in enumerate(chars)}
        rng = np.random.default_rng(seed)
        vocab_size = len(chars)
        selected = str(architecture or NATIVE_ARCHITECTURE).strip() or NATIVE_ARCHITECTURE

        if selected == LEGACY_ARCHITECTURE:
            logits = rng.normal(0.0, 0.01, size=(vocab_size, vocab_size)).astype(np.float64)
            return cls(
                vocab=chars,
                stoi=stoi,
                itos=itos,
                architecture=LEGACY_ARCHITECTURE,
                logits=logits,
                block_size=1,
                embed_dim=0,
                hidden_dim=0,
                attention_heads=0,
                tokenizer_mode=active_tokenizer.mode,
                tokenizer_lowercase=bool(active_tokenizer.lowercase),
                dataset_source_path=str(dataset_source_path or ""),
                dataset_artifact_path=str(dataset_artifact_path or ""),
                dataset_stats=dict(dataset_stats or {}),
                eval_metrics=dict(eval_metrics or {}),
            )

        effective_block = max(2, int(block_size))
        effective_embed = max(8, int(embed_dim))
        effective_hidden = max(16, int(hidden_dim))
        embeddings = rng.normal(0.0, 0.05, size=(vocab_size, effective_embed)).astype(np.float64)

        if selected == NATIVE_MLP_ARCHITECTURE:
            w1_scale = np.sqrt(2.0 / max(1.0, float((effective_block * effective_embed) + effective_hidden)))
            w2_scale = np.sqrt(2.0 / max(1.0, float(effective_hidden + vocab_size)))
            w1 = rng.normal(0.0, w1_scale, size=(effective_block * effective_embed, effective_hidden)).astype(np.float64)
            b1 = np.zeros(effective_hidden, dtype=np.float64)
            w2 = rng.normal(0.0, w2_scale, size=(effective_hidden, vocab_size)).astype(np.float64)
            b2 = np.zeros(vocab_size, dtype=np.float64)
            return cls(
                vocab=chars,
                stoi=stoi,
                itos=itos,
                architecture=NATIVE_MLP_ARCHITECTURE,
                block_size=effective_block,
                embed_dim=effective_embed,
                hidden_dim=effective_hidden,
                embeddings=embeddings,
                w1=w1,
                b1=b1,
                w2=w2,
                b2=b2,
                attention_heads=0,
                tokenizer_mode=active_tokenizer.mode,
                tokenizer_lowercase=bool(active_tokenizer.lowercase),
                dataset_source_path=str(dataset_source_path or ""),
                dataset_artifact_path=str(dataset_artifact_path or ""),
                dataset_stats=dict(dataset_stats or {}),
                eval_metrics=dict(eval_metrics or {}),
            )

        effective_heads = _resolve_attention_heads(effective_embed, attention_heads)
        attn_scale = np.sqrt(2.0 / max(1.0, float(effective_embed * 2)))
        ff1_scale = np.sqrt(2.0 / max(1.0, float(effective_embed + effective_hidden)))
        ff2_scale = np.sqrt(2.0 / max(1.0, float(effective_hidden + effective_embed)))
        lm_scale = np.sqrt(2.0 / max(1.0, float(effective_embed + vocab_size)))
        position_embeddings = rng.normal(0.0, 0.02, size=(effective_block, effective_embed)).astype(np.float64)
        q_proj = rng.normal(0.0, attn_scale, size=(effective_embed, effective_embed)).astype(np.float64)
        k_proj = rng.normal(0.0, attn_scale, size=(effective_embed, effective_embed)).astype(np.float64)
        v_proj = rng.normal(0.0, attn_scale, size=(effective_embed, effective_embed)).astype(np.float64)
        attention_out = rng.normal(0.0, attn_scale, size=(effective_embed, effective_embed)).astype(np.float64)
        w1 = rng.normal(0.0, ff1_scale, size=(effective_embed, effective_hidden)).astype(np.float64)
        b1 = np.zeros(effective_hidden, dtype=np.float64)
        w2 = rng.normal(0.0, ff2_scale, size=(effective_hidden, effective_embed)).astype(np.float64)
        b2 = np.zeros(effective_embed, dtype=np.float64)
        lm_head = rng.normal(0.0, lm_scale, size=(effective_embed, vocab_size)).astype(np.float64)
        lm_bias = np.zeros(vocab_size, dtype=np.float64)
        return cls(
            vocab=chars,
            stoi=stoi,
            itos=itos,
            architecture=NATIVE_ATTENTION_ARCHITECTURE,
            block_size=effective_block,
            embed_dim=effective_embed,
            hidden_dim=effective_hidden,
            embeddings=embeddings,
            position_embeddings=position_embeddings,
            q_proj=q_proj,
            k_proj=k_proj,
            v_proj=v_proj,
            attention_out=attention_out,
            w1=w1,
            b1=b1,
            w2=w2,
            b2=b2,
            lm_head=lm_head,
            lm_bias=lm_bias,
            attention_heads=effective_heads,
            tokenizer_mode=active_tokenizer.mode,
            tokenizer_lowercase=bool(active_tokenizer.lowercase),
            dataset_source_path=str(dataset_source_path or ""),
            dataset_artifact_path=str(dataset_artifact_path or ""),
            dataset_stats=dict(dataset_stats or {}),
            eval_metrics=dict(eval_metrics or {}),
        )

    @property
    def native_mlp(self) -> bool:
        return self.architecture == NATIVE_MLP_ARCHITECTURE and self.embeddings is not None and self.q_proj is None

    @property
    def native_attention(self) -> bool:
        return self.architecture == NATIVE_ATTENTION_ARCHITECTURE and self.q_proj is not None

    @property
    def fully_native(self) -> bool:
        return bool(self.native_mlp or self.native_attention)

    @property
    def attention_head_dim(self) -> int:
        if not self.native_attention:
            return 0
        return int(self.embed_dim // max(1, self.attention_heads))

    def metadata(self) -> dict:
        primary_eval = self.primary_eval_summary()
        return {
            "architecture": self.architecture,
            "fully_native": bool(self.fully_native),
            "production_grade": bool(self.fully_native),
            "vocab_size": len(self.vocab),
            "block_size": int(self.block_size),
            "embed_dim": int(self.embed_dim),
            "hidden_dim": int(self.hidden_dim),
            "attention_block": bool(self.native_attention),
            "attention_heads": int(self.attention_heads if self.native_attention else 0),
            "attention_head_dim": int(self.attention_head_dim),
            "mlp_hidden_layer": bool(self.native_mlp or self.native_attention),
            "training_steps": int(self.training_steps),
            "tokenizer_mode": self.tokenizer_mode,
            "tokenizer_lowercase": bool(self.tokenizer_lowercase),
            "dataset_source_path": self.dataset_source_path,
            "dataset_artifact_path": self.dataset_artifact_path,
            "dataset_stats": dict(self.dataset_stats or {}),
            "eval_ready": bool(primary_eval.get("ready", False)),
            "primary_eval_split": primary_eval.get("split", ""),
            "primary_eval_loss": float(primary_eval.get("loss", 0.0)),
            "primary_eval_perplexity": float(primary_eval.get("perplexity", 0.0)),
        }

    def tokenizer_payload(self) -> dict:
        return {
            "mode": self.tokenizer_mode,
            "vocab": list(self.vocab),
            "lowercase": bool(self.tokenizer_lowercase),
            "vocab_size": len(self.vocab),
        }

    def _tokenizer(self) -> ZeroTokenizer:
        return ZeroTokenizer.from_payload(self.tokenizer_payload())

    def primary_eval_summary(self) -> dict:
        metrics = dict(self.eval_metrics or {})
        primary = str(metrics.get("primary_split", "")).strip().lower()
        if primary and isinstance(metrics.get(primary), dict):
            return dict(metrics[primary])
        for candidate in ("valid", "train"):
            if isinstance(metrics.get(candidate), dict) and bool(metrics[candidate].get("ready", False)):
                return dict(metrics[candidate])
        return {"split": "", "loss": 0.0, "perplexity": 0.0, "ready": False}

    def encode(self, s: str) -> list[int]:
        return self._tokenizer().encode(s)

    def decode(self, ids: list[int]) -> str:
        return self._tokenizer().decode_ids(ids)

    def _prepare_contexts(self, ids: list[int]) -> tuple[np.ndarray, np.ndarray]:
        if len(ids) < 2:
            return np.zeros((0, self.block_size), dtype=np.int64), np.zeros((0,), dtype=np.int64)
        contexts = np.zeros((len(ids) - 1, self.block_size), dtype=np.int64)
        targets = np.array(ids[1:], dtype=np.int64)
        for idx in range(1, len(ids)):
            window = ids[max(0, idx - self.block_size) : idx]
            if window:
                contexts[idx - 1, -len(window) :] = window
        return contexts, targets

    def _forward_mlp(self, contexts: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if contexts.size == 0:
            return (
                np.zeros((0, self.block_size * self.embed_dim), dtype=np.float64),
                np.zeros((0, self.hidden_dim), dtype=np.float64),
                np.zeros((0, len(self.vocab)), dtype=np.float64),
            )
        x = self.embeddings[contexts].reshape(len(contexts), self.block_size * self.embed_dim)
        hidden_pre = x @ self.w1 + self.b1
        hidden = np.tanh(hidden_pre)
        logits = hidden @ self.w2 + self.b2
        return x, hidden, logits

    def _forward_attention(self, contexts: np.ndarray) -> dict:
        batch = len(contexts)
        heads = max(1, int(self.attention_heads))
        head_dim = max(1, int(self.attention_head_dim))
        if batch == 0:
            zero_bte = np.zeros((0, self.block_size, self.embed_dim), dtype=np.float64)
            zero_bhtd = np.zeros((0, heads, self.block_size, head_dim), dtype=np.float64)
            zero_bhtt = np.zeros((0, heads, self.block_size, self.block_size), dtype=np.float64)
            return {
                "tokens": zero_bte,
                "q_lin": zero_bte,
                "k_lin": zero_bte,
                "v_lin": zero_bte,
                "q": zero_bhtd,
                "k": zero_bhtd,
                "v": zero_bhtd,
                "attn_probs": zero_bhtt,
                "attn_context_heads": zero_bhtd,
                "attn_context": zero_bte,
                "attn_out": zero_bte,
                "residual1": zero_bte,
                "hidden": np.zeros((0, self.block_size, self.hidden_dim), dtype=np.float64),
                "ff_out": zero_bte,
                "residual2": zero_bte,
                "last": np.zeros((0, self.embed_dim), dtype=np.float64),
                "logits": np.zeros((0, len(self.vocab)), dtype=np.float64),
                "mask": np.tril(np.ones((self.block_size, self.block_size), dtype=np.float64)),
            }
        tokens = self.embeddings[contexts] + self.position_embeddings[np.newaxis, :, :]
        q_lin = np.matmul(tokens, self.q_proj)
        k_lin = np.matmul(tokens, self.k_proj)
        v_lin = np.matmul(tokens, self.v_proj)
        q = _reshape_heads(q_lin, heads)
        k = _reshape_heads(k_lin, heads)
        v = _reshape_heads(v_lin, heads)
        scale = np.sqrt(float(head_dim))
        scores = np.matmul(q, np.swapaxes(k, -1, -2)) / max(scale, 1e-6)
        mask = np.tril(np.ones((self.block_size, self.block_size), dtype=np.float64))
        masked_scores = np.where(mask[np.newaxis, np.newaxis, :, :] > 0.0, scores, -1e9)
        attn_probs = _softmax_rows(masked_scores)
        attn_context_heads = np.matmul(attn_probs, v)
        attn_context = _merge_heads(attn_context_heads)
        attn_out = np.matmul(attn_context, self.attention_out)
        residual1 = tokens + attn_out
        hidden_pre = np.matmul(residual1, self.w1) + self.b1
        hidden = np.tanh(hidden_pre)
        ff_out = np.matmul(hidden, self.w2) + self.b2
        residual2 = residual1 + ff_out
        last = residual2[:, -1, :]
        logits = last @ self.lm_head + self.lm_bias
        return {
            "tokens": tokens,
            "q_lin": q_lin,
            "k_lin": k_lin,
            "v_lin": v_lin,
            "q": q,
            "k": k,
            "v": v,
            "attn_probs": attn_probs,
            "attn_context_heads": attn_context_heads,
            "attn_context": attn_context,
            "attn_out": attn_out,
            "residual1": residual1,
            "hidden": hidden,
            "ff_out": ff_out,
            "residual2": residual2,
            "last": last,
            "logits": logits,
            "mask": mask,
        }

    def _sample_context(self, contexts: np.ndarray, targets: np.ndarray, batch_size: int) -> tuple[np.ndarray, np.ndarray]:
        if 0 < batch_size < len(targets):
            rng = np.random.default_rng(1000 + int(self.training_steps))
            picked = np.sort(rng.choice(len(targets), size=int(batch_size), replace=False))
            return contexts[picked], targets[picked]
        return contexts, targets

    def _train_step_mlp(
        self,
        ids: list[int],
        lr: float,
        batch_size: int,
        weight_decay: float,
        grad_clip: float,
    ) -> float:
        if len(ids) < 2:
            return 0.0
        contexts, targets = self._prepare_contexts(ids)
        if len(targets) == 0:
            return 0.0
        contexts, targets = self._sample_context(contexts, targets, batch_size)

        x, hidden, logits = self._forward_mlp(contexts)
        probs = _softmax_rows(logits)
        loss = float(-np.mean(np.log(probs[np.arange(len(targets)), targets] + 1e-12)))

        dlogits = probs.copy()
        dlogits[np.arange(len(targets)), targets] -= 1.0
        dlogits /= max(1, len(targets))

        grad_w2 = hidden.T @ dlogits + (float(weight_decay) * self.w2)
        grad_b2 = np.sum(dlogits, axis=0)
        dhidden = dlogits @ self.w2.T
        dhidden_pre = dhidden * (1.0 - (hidden * hidden))
        grad_w1 = x.T @ dhidden_pre + (float(weight_decay) * self.w1)
        grad_b1 = np.sum(dhidden_pre, axis=0)
        dx = dhidden_pre @ self.w1.T
        grad_embeddings = np.zeros_like(self.embeddings)
        dx = dx.reshape(len(targets), self.block_size, self.embed_dim)
        for pos in range(self.block_size):
            np.add.at(grad_embeddings, contexts[:, pos], dx[:, pos, :])
        grad_embeddings += float(weight_decay) * self.embeddings

        if grad_clip > 0.0:
            limit = float(grad_clip)
            grad_w2 = _clip(grad_w2, limit)
            grad_b2 = _clip(grad_b2, limit)
            grad_w1 = _clip(grad_w1, limit)
            grad_b1 = _clip(grad_b1, limit)
            grad_embeddings = _clip(grad_embeddings, limit)

        rate = float(lr)
        self.w2 -= rate * grad_w2
        self.b2 -= rate * grad_b2
        self.w1 -= rate * grad_w1
        self.b1 -= rate * grad_b1
        self.embeddings -= rate * grad_embeddings
        self.training_steps += 1
        return loss

    def _train_step_attention(
        self,
        ids: list[int],
        lr: float,
        batch_size: int,
        weight_decay: float,
        grad_clip: float,
    ) -> float:
        if len(ids) < 2:
            return 0.0
        contexts, targets = self._prepare_contexts(ids)
        if len(targets) == 0:
            return 0.0
        contexts, targets = self._sample_context(contexts, targets, batch_size)

        cache = self._forward_attention(contexts)
        logits = cache["logits"]
        probs = _softmax_rows(logits)
        loss = float(-np.mean(np.log(probs[np.arange(len(targets)), targets] + 1e-12)))

        dlogits = probs.copy()
        dlogits[np.arange(len(targets)), targets] -= 1.0
        dlogits /= max(1, len(targets))

        grad_lm_head = cache["last"].T @ dlogits + (float(weight_decay) * self.lm_head)
        grad_lm_bias = np.sum(dlogits, axis=0)
        dlast = dlogits @ self.lm_head.T

        dresidual2 = np.zeros_like(cache["residual2"])
        dresidual2[:, -1, :] = dlast

        dresidual1 = dresidual2.copy()
        dff_out = dresidual2
        grad_w2 = np.matmul(cache["hidden"].reshape(-1, self.hidden_dim).T, dff_out.reshape(-1, self.embed_dim))
        grad_w2 += float(weight_decay) * self.w2
        grad_b2 = np.sum(dff_out, axis=(0, 1))
        dhidden = np.matmul(dff_out, self.w2.T)
        dhidden_pre = dhidden * (1.0 - (cache["hidden"] * cache["hidden"]))
        grad_w1 = np.matmul(cache["residual1"].reshape(-1, self.embed_dim).T, dhidden_pre.reshape(-1, self.hidden_dim))
        grad_w1 += float(weight_decay) * self.w1
        grad_b1 = np.sum(dhidden_pre, axis=(0, 1))
        dresidual1 += np.matmul(dhidden_pre, self.w1.T)

        dtokens = dresidual1.copy()
        dattn_out = dresidual1
        grad_attention_out = np.matmul(cache["attn_context"].reshape(-1, self.embed_dim).T, dattn_out.reshape(-1, self.embed_dim))
        grad_attention_out += float(weight_decay) * self.attention_out
        dattn_context = np.matmul(dattn_out, self.attention_out.T)
        dattn_context_heads = _reshape_heads(dattn_context, max(1, self.attention_heads))

        dattn_probs = np.matmul(dattn_context_heads, np.swapaxes(cache["v"], -1, -2))
        dv = np.matmul(np.swapaxes(cache["attn_probs"], -1, -2), dattn_context_heads)
        dot = np.sum(dattn_probs * cache["attn_probs"], axis=-1, keepdims=True)
        dscores = cache["attn_probs"] * (dattn_probs - dot)
        dscores *= cache["mask"][np.newaxis, np.newaxis, :, :]
        scale = np.sqrt(float(max(1, self.attention_head_dim)))
        dq = np.matmul(dscores, cache["k"]) / max(scale, 1e-6)
        dk = np.matmul(np.swapaxes(dscores, -1, -2), cache["q"]) / max(scale, 1e-6)

        dq_lin = _merge_heads(dq)
        dk_lin = _merge_heads(dk)
        dv_lin = _merge_heads(dv)
        grad_q_proj = np.matmul(cache["tokens"].reshape(-1, self.embed_dim).T, dq_lin.reshape(-1, self.embed_dim))
        grad_q_proj += float(weight_decay) * self.q_proj
        grad_k_proj = np.matmul(cache["tokens"].reshape(-1, self.embed_dim).T, dk_lin.reshape(-1, self.embed_dim))
        grad_k_proj += float(weight_decay) * self.k_proj
        grad_v_proj = np.matmul(cache["tokens"].reshape(-1, self.embed_dim).T, dv_lin.reshape(-1, self.embed_dim))
        grad_v_proj += float(weight_decay) * self.v_proj

        dtokens += np.matmul(dq_lin, self.q_proj.T)
        dtokens += np.matmul(dk_lin, self.k_proj.T)
        dtokens += np.matmul(dv_lin, self.v_proj.T)

        grad_position_embeddings = np.sum(dtokens, axis=0) + (float(weight_decay) * self.position_embeddings)
        grad_embeddings = np.zeros_like(self.embeddings)
        for pos in range(self.block_size):
            np.add.at(grad_embeddings, contexts[:, pos], dtokens[:, pos, :])
        grad_embeddings += float(weight_decay) * self.embeddings

        if grad_clip > 0.0:
            limit = float(grad_clip)
            grad_lm_head = _clip(grad_lm_head, limit)
            grad_lm_bias = _clip(grad_lm_bias, limit)
            grad_w2 = _clip(grad_w2, limit)
            grad_b2 = _clip(grad_b2, limit)
            grad_w1 = _clip(grad_w1, limit)
            grad_b1 = _clip(grad_b1, limit)
            grad_attention_out = _clip(grad_attention_out, limit)
            grad_q_proj = _clip(grad_q_proj, limit)
            grad_k_proj = _clip(grad_k_proj, limit)
            grad_v_proj = _clip(grad_v_proj, limit)
            grad_position_embeddings = _clip(grad_position_embeddings, limit)
            grad_embeddings = _clip(grad_embeddings, limit)

        rate = float(lr)
        self.lm_head -= rate * grad_lm_head
        self.lm_bias -= rate * grad_lm_bias
        self.w2 -= rate * grad_w2
        self.b2 -= rate * grad_b2
        self.w1 -= rate * grad_w1
        self.b1 -= rate * grad_b1
        self.attention_out -= rate * grad_attention_out
        self.q_proj -= rate * grad_q_proj
        self.k_proj -= rate * grad_k_proj
        self.v_proj -= rate * grad_v_proj
        self.position_embeddings -= rate * grad_position_embeddings
        self.embeddings -= rate * grad_embeddings
        self.training_steps += 1
        return loss

    def train_step(
        self,
        ids: list[int],
        lr: float = 0.1,
        batch_size: int = 64,
        weight_decay: float = 1e-4,
        grad_clip: float = 1.0,
    ) -> float:
        if len(ids) < 2:
            return 0.0
        if self.native_attention:
            return self._train_step_attention(ids, lr, batch_size, weight_decay, grad_clip)
        if self.native_mlp:
            return self._train_step_mlp(ids, lr, batch_size, weight_decay, grad_clip)

        total_loss = 0.0
        grad = np.zeros_like(self.logits)
        for a, b in zip(ids[:-1], ids[1:]):
            row = self.logits[a]
            probs = _softmax_rows(row.reshape(1, -1))[0]
            total_loss += -np.log(probs[b] + 1e-12)
            g = probs.copy()
            g[b] -= 1.0
            grad[a] += g
        n = max(1, len(ids) - 1)
        self.logits -= float(lr) * (grad / n)
        self.training_steps += 1
        return float(total_loss / n)

    def evaluate_loss(self, ids: list[int]) -> float:
        if len(ids) < 2:
            return 0.0
        if self.native_attention:
            contexts, targets = self._prepare_contexts(ids)
            if len(targets) == 0:
                return 0.0
            logits = self._forward_attention(contexts)["logits"]
            probs = _softmax_rows(logits)
            return float(-np.mean(np.log(probs[np.arange(len(targets)), targets] + 1e-12)))
        if self.native_mlp:
            contexts, targets = self._prepare_contexts(ids)
            if len(targets) == 0:
                return 0.0
            logits = self._forward_mlp(contexts)[2]
            probs = _softmax_rows(logits)
            return float(-np.mean(np.log(probs[np.arange(len(targets)), targets] + 1e-12)))

        total_loss = 0.0
        for a, b in zip(ids[:-1], ids[1:]):
            row = self.logits[a]
            probs = _softmax_rows(row.reshape(1, -1))[0]
            total_loss += -np.log(probs[b] + 1e-12)
        return float(total_loss / max(1, len(ids) - 1))

    def evaluate_split(self, ids: list[int], split: str = "eval") -> dict:
        token_count = int(len(ids))
        example_count = max(0, token_count - 1)
        ready = token_count >= 2
        loss = float(self.evaluate_loss(ids)) if ready else 0.0
        perplexity = float(np.exp(min(loss, 50.0))) if ready else 0.0
        return {
            "split": str(split or "eval"),
            "ready": bool(ready),
            "token_count": token_count,
            "example_count": int(example_count),
            "loss": float(loss),
            "perplexity": float(perplexity),
        }

    def _next_logits(self, context_ids: list[int]) -> np.ndarray:
        context = np.zeros((1, self.block_size), dtype=np.int64)
        trimmed = context_ids[-self.block_size :]
        if trimmed:
            context[0, -len(trimmed) :] = np.array(trimmed, dtype=np.int64)
        if self.native_attention:
            return self._forward_attention(context)["logits"][0]
        if self.native_mlp:
            return self._forward_mlp(context)[2][0]
        return self.logits[context_ids[-1]]

    def sample(self, prompt: str, length: int = 200, temperature: float = 1.0, seed: int = 123) -> str:
        rng = np.random.default_rng(seed)
        ids = self.encode(prompt)
        if not ids:
            ids = [0]
        out = ids.copy()

        if not self.native_attention and not self.native_mlp:
            cur = ids[-1]
            for _ in range(length):
                row = self.logits[cur] / max(temperature, 1e-6)
                probs = _softmax_rows(row.reshape(1, -1))[0]
                nxt = int(rng.choice(len(self.vocab), p=probs))
                out.append(nxt)
                cur = nxt
            return self.decode(out)

        for _ in range(length):
            row = self._next_logits(out) / max(temperature, 1e-6)
            probs = _softmax_rows(row.reshape(1, -1))[0]
            nxt = int(rng.choice(len(self.vocab), p=probs))
            out.append(nxt)
        return self.decode(out)

    def save(self, path: str) -> None:
        payload = {
            "version": 5,
            "architecture": self.architecture,
            "vocab": self.vocab,
            "tokenizer": self.tokenizer_payload(),
            "dataset": {
                "source_path": self.dataset_source_path,
                "artifact_path": self.dataset_artifact_path,
                "stats": dict(self.dataset_stats or {}),
            },
            "eval_metrics": dict(self.eval_metrics or {}),
            "training_steps": int(self.training_steps),
            "model_info": self.metadata(),
            "block_size": int(self.block_size),
            "embed_dim": int(self.embed_dim),
            "hidden_dim": int(self.hidden_dim),
        }
        if not self.native_attention and not self.native_mlp:
            payload["logits"] = self.logits.tolist()
            payload["block_size"] = 1
            payload["embed_dim"] = 0
            payload["hidden_dim"] = 0
        elif self.native_mlp:
            payload["weights"] = {
                "embeddings": self.embeddings.tolist(),
                "w1": self.w1.tolist(),
                "b1": self.b1.tolist(),
                "w2": self.w2.tolist(),
                "b2": self.b2.tolist(),
            }
        else:
            payload["heads"] = int(self.attention_heads)
            payload["weights"] = {
                "embeddings": self.embeddings.tolist(),
                "position_embeddings": self.position_embeddings.tolist(),
                "q_proj": self.q_proj.tolist(),
                "k_proj": self.k_proj.tolist(),
                "v_proj": self.v_proj.tolist(),
                "attention_out": self.attention_out.tolist(),
                "w1": self.w1.tolist(),
                "b1": self.b1.tolist(),
                "w2": self.w2.tolist(),
                "b2": self.b2.tolist(),
                "lm_head": self.lm_head.tolist(),
                "lm_bias": self.lm_bias.tolist(),
            }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TinyBigramModel":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        summary = inspect_checkpoint_payload(payload)
        if not summary.get("ok", False):
            raise ValueError(summary.get("reason", "checkpoint malformed"))

        architecture = str(summary.get("architecture", LEGACY_ARCHITECTURE))
        tokenizer_payload = payload.get("tokenizer", {})
        vocab = payload.get("vocab") or []
        if not vocab and isinstance(tokenizer_payload, dict):
            vocab = list(tokenizer_payload.get("vocab", []))
        tokenizer_mode = "char"
        tokenizer_lowercase = False
        if isinstance(tokenizer_payload, dict):
            tokenizer_mode = str(tokenizer_payload.get("mode", "char")).strip().lower() or "char"
            tokenizer_lowercase = bool(tokenizer_payload.get("lowercase", False))
        dataset_payload = payload.get("dataset", {})
        dataset_source_path = ""
        dataset_artifact_path = ""
        dataset_stats = {}
        if isinstance(dataset_payload, dict):
            dataset_source_path = str(dataset_payload.get("source_path", ""))
            dataset_artifact_path = str(dataset_payload.get("artifact_path", ""))
            if isinstance(dataset_payload.get("stats"), dict):
                dataset_stats = dict(dataset_payload.get("stats", {}))
        eval_metrics = payload.get("eval_metrics", {})
        if not isinstance(eval_metrics, dict):
            eval_metrics = {}
        if architecture == "legacy_table_v1":
            table = _as_float_array(payload["table"])
            if not vocab:
                vocab = [chr(ord("a") + i) for i in range(int(payload.get("vocab_size", table.shape[0])))]
            stoi = {c: i for i, c in enumerate(vocab)}
            itos = {i: c for i, c in enumerate(vocab)}
            return cls(
                vocab=vocab,
                stoi=stoi,
                itos=itos,
                architecture=LEGACY_ARCHITECTURE,
                logits=table,
                block_size=1,
                embed_dim=0,
                hidden_dim=0,
                attention_heads=0,
                tokenizer_mode=tokenizer_mode,
                tokenizer_lowercase=tokenizer_lowercase,
                dataset_source_path=dataset_source_path,
                dataset_artifact_path=dataset_artifact_path,
                dataset_stats=dataset_stats,
                eval_metrics=eval_metrics,
            )

        stoi = {c: i for i, c in enumerate(vocab)}
        itos = {i: c for i, c in enumerate(vocab)}
        training_steps = int(payload.get("training_steps", 0))
        if architecture == NATIVE_MLP_ARCHITECTURE:
            weights = payload["weights"]
            return cls(
                vocab=vocab,
                stoi=stoi,
                itos=itos,
                architecture=NATIVE_MLP_ARCHITECTURE,
                block_size=int(payload.get("block_size", 8)),
                embed_dim=int(payload.get("embed_dim", 24)),
                hidden_dim=int(payload.get("hidden_dim", 64)),
                embeddings=_as_float_array(weights["embeddings"]),
                w1=_as_float_array(weights["w1"]),
                b1=_as_float_array(weights["b1"]),
                w2=_as_float_array(weights["w2"]),
                b2=_as_float_array(weights["b2"]),
                attention_heads=0,
                training_steps=training_steps,
                tokenizer_mode=tokenizer_mode,
                tokenizer_lowercase=tokenizer_lowercase,
                dataset_source_path=dataset_source_path,
                dataset_artifact_path=dataset_artifact_path,
                dataset_stats=dataset_stats,
                eval_metrics=eval_metrics,
            )
        if architecture == NATIVE_ATTENTION_ARCHITECTURE:
            weights = payload["weights"]
            return cls(
                vocab=vocab,
                stoi=stoi,
                itos=itos,
                architecture=NATIVE_ATTENTION_ARCHITECTURE,
                block_size=int(payload.get("block_size", 8)),
                embed_dim=int(payload.get("embed_dim", 24)),
                hidden_dim=int(payload.get("hidden_dim", 64)),
                embeddings=_as_float_array(weights["embeddings"]),
                position_embeddings=_as_float_array(weights["position_embeddings"]),
                q_proj=_as_float_array(weights["q_proj"]),
                k_proj=_as_float_array(weights["k_proj"]),
                v_proj=_as_float_array(weights["v_proj"]),
                attention_out=_as_float_array(weights["attention_out"]),
                w1=_as_float_array(weights["w1"]),
                b1=_as_float_array(weights["b1"]),
                w2=_as_float_array(weights["w2"]),
                b2=_as_float_array(weights["b2"]),
                lm_head=_as_float_array(weights["lm_head"]),
                lm_bias=_as_float_array(weights["lm_bias"]),
                attention_heads=int(payload.get("heads", DEFAULT_ATTENTION_HEADS)),
                training_steps=training_steps,
                tokenizer_mode=tokenizer_mode,
                tokenizer_lowercase=tokenizer_lowercase,
                dataset_source_path=dataset_source_path,
                dataset_artifact_path=dataset_artifact_path,
                dataset_stats=dataset_stats,
                eval_metrics=eval_metrics,
            )

        logits = _as_float_array(payload["logits"])
        return cls(
            vocab=vocab,
            stoi=stoi,
            itos=itos,
            architecture=LEGACY_ARCHITECTURE,
            logits=logits,
            block_size=1,
            embed_dim=0,
            hidden_dim=0,
            attention_heads=0,
            training_steps=training_steps,
            tokenizer_mode=tokenizer_mode,
            tokenizer_lowercase=tokenizer_lowercase,
            dataset_source_path=dataset_source_path,
            dataset_artifact_path=dataset_artifact_path,
            dataset_stats=dataset_stats,
            eval_metrics=eval_metrics,
        )

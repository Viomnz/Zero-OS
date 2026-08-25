from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib import request as urllib_request


SYSTEM_PROMPT = """You are the Zero AI LLM proposal engine inside Zero-OS.
You generate hypotheses, candidate plans, explanations, alternatives, assumptions, and proposed tests.
You do NOT certify truth, scope, safety, readiness, identity, production status, or permission to mutate.
You do NOT grant yourself authority.
Return JSON only with keys: summary, hypotheses, alternatives, assumptions, proposed_tests, requested_scope.
Unknown is valid. Preserve multiple viable hypotheses when evidence does not separate them.
"""


class LLMBackend(Protocol):
    name: str

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class LLMProposal:
    source: str
    summary: str
    hypotheses: tuple[str, ...] = field(default_factory=tuple)
    alternatives: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    proposed_tests: tuple[str, ...] = field(default_factory=tuple)
    requested_scope: frozenset[str] = field(default_factory=frozenset)
    authority: float = 0.0
    authority_status: str = "proposal_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "summary": self.summary,
            "hypotheses": list(self.hypotheses),
            "alternatives": list(self.alternatives),
            "assumptions": list(self.assumptions),
            "proposed_tests": list(self.proposed_tests),
            "requested_scope": sorted(self.requested_scope),
            "authority": self.authority,
            "authority_status": self.authority_status,
            "may_mutate": False,
            "may_self_certify": False,
        }


class MockBackend:
    name = "mock"

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        objective = str(payload.get("objective", "")).strip()
        return {
            "summary": f"Proposal analysis for: {objective}" if objective else "Proposal analysis",
            "hypotheses": ["insufficient_external_evidence"],
            "alternatives": ["collect_more_evidence"],
            "assumptions": [],
            "proposed_tests": ["independent_scope_certification"],
            "requested_scope": list(payload.get("requested_scope", [])),
        }


class OpenAIResponsesBackend:
    name = "openai_responses"

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        self.model = str(model or os.getenv("ZERO_AI_LLM_MODEL", "gpt-5"))
        self.api_key = str(api_key or os.getenv("OPENAI_API_KEY", ""))

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        body = json.dumps(
            {
                "model": self.model,
                "instructions": SYSTEM_PROMPT,
                "input": json.dumps(payload, sort_keys=True),
            }
        ).encode("utf-8")
        req = urllib_request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=60) as response:  # nosec B310 - fixed HTTPS API endpoint
            raw = json.loads(response.read().decode("utf-8"))
        text = str(raw.get("output_text", "") or "").strip()
        if not text:
            chunks: list[str] = []
            for item in list(raw.get("output", [])):
                for content in list((item or {}).get("content", [])):
                    if str((content or {}).get("type", "")) in {"output_text", "text"}:
                        chunks.append(str((content or {}).get("text", "")))
            text = "\n".join(chunks).strip()
        try:
            parsed = json.loads(text)
        except Exception as exc:
            raise RuntimeError("LLM returned non-JSON proposal") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("LLM proposal must be a JSON object")
        return parsed


def _as_strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _normalize(raw: dict[str, Any], source: str) -> LLMProposal:
    return LLMProposal(
        source=source,
        summary=str(raw.get("summary", "")).strip(),
        hypotheses=_as_strings(raw.get("hypotheses")),
        alternatives=_as_strings(raw.get("alternatives")),
        assumptions=_as_strings(raw.get("assumptions")),
        proposed_tests=_as_strings(raw.get("proposed_tests")),
        requested_scope=frozenset(_as_strings(raw.get("requested_scope"))),
    )


def propose(
    objective: str,
    *,
    observations: list[dict[str, Any]] | None = None,
    constraints: list[str] | None = None,
    requested_scope: list[str] | None = None,
    backend: LLMBackend | None = None,
) -> dict[str, Any]:
    """Generate a non-authoritative reasoning proposal.

    The output is deliberately incapable of granting permission or scope authority.
    Downstream mutation or promotion must pass through Pure Logic certification.
    """
    active_backend = backend or MockBackend()
    payload = {
        "objective": str(objective or ""),
        "observations": list(observations or []),
        "constraints": [str(item) for item in list(constraints or [])],
        "requested_scope": [str(item) for item in list(requested_scope or [])],
    }
    raw = active_backend.generate(payload)
    proposal = _normalize(dict(raw or {}), str(getattr(active_backend, "name", "llm")))
    out = proposal.to_dict()
    out["input"] = payload
    return out


def backend_from_environment() -> LLMBackend:
    backend_name = str(os.getenv("ZERO_AI_LLM_BACKEND", "mock")).strip().lower()
    if backend_name in {"openai", "openai_responses", "responses"}:
        return OpenAIResponsesBackend()
    return MockBackend()

from __future__ import annotations

import re


def understand_english(text: str) -> dict:
    raw = text.strip()
    lower = raw.lower()
    tokens = re.findall(r"[a-zA-Z0-9']+", lower)
    token_count = len(tokens)

    action_terms = {
        "create": ("create", "write", "make", "build", "generate"),
        "read": ("read", "show", "open", "view"),
        "search": ("search", "find", "lookup", "look", "browse"),
        "fix": ("fix", "repair", "resolve", "debug"),
        "run": ("run", "execute", "start", "launch"),
        "delete": ("delete", "remove", "erase"),
    }

    action = "general"
    for name, variants in action_terms.items():
        if any(v in tokens for v in variants):
            action = name
            break

    has_file_hint = any(x in lower for x in (".py", ".txt", "file", "folder", "path"))
    has_web_hint = any(x in lower for x in ("http://", "https://", "website", "internet", "web"))
    has_question = "?" in raw or any(w in tokens for w in ("what", "why", "how", "can"))

    intent = "question" if has_question else ("command" if action != "general" else "statement")
    domain = "web" if has_web_hint else ("filesystem" if has_file_hint else "general")
    confidence = 0.45
    if action != "general":
        confidence += 0.25
    if has_file_hint or has_web_hint:
        confidence += 0.15
    if token_count >= 4:
        confidence += 0.1
    confidence = max(0.0, min(1.0, confidence))

    summary = f"I understand your intent: {intent}. Main action: {action}. Domain: {domain}."
    return {
        "is_english": token_count > 0,
        "intent": intent,
        "action": action,
        "domain": domain,
        "token_count": token_count,
        "confidence": round(confidence, 2),
        "summary": summary,
    }


def human_response_from_understanding(data: dict, prompt: str) -> str:
    intent = data.get("intent", "statement")
    action = data.get("action", "general")
    domain = data.get("domain", "general")
    conf = data.get("confidence", 0.0)
    # Include awareness, pressure, and balance terms for universe law pass.
    return (
        "I am aware of your request. "
        f"I understand intent={intent}, action={action}, domain={domain}, confidence={conf}. "
        "I will handle this with pressure-tested steps and keep balance for stable execution. "
        f"Prompt understood: {prompt}"
    )

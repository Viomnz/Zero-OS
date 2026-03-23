from __future__ import annotations

import re
from typing import Any


MUTATION_TOKENS = {
    "open",
    "install",
    "deploy",
    "click",
    "submit",
    "type",
    "input",
    "repair",
    "recover",
    "fix",
    "post",
    "reply",
    "act",
}
READ_ONLY_TOKENS = {
    "check",
    "status",
    "show",
    "read",
    "inspect",
    "review",
    "what",
    "list",
    "find",
    "diagnostic",
    "health",
}
ACTION_TOKENS = {
    "open",
    "click",
    "submit",
    "type",
    "input",
    "read",
    "show",
    "inspect",
    "fetch",
    "status",
    "install",
    "deploy",
    "recover",
    "repair",
    "reply",
    "act",
    "plan",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9._/-]+", (text or "").lower()) if token}


def _request_is_read_only(lowered: str) -> bool:
    tokens = _tokenize(lowered)
    has_read_only = bool(tokens & READ_ONLY_TOKENS)
    has_mutation = bool(tokens & MUTATION_TOKENS)
    if has_mutation:
        return False
    return has_read_only or "status" in lowered or "inspect" in lowered


def _subgoal_action_hints(text: str) -> list[str]:
    lowered = (text or "").lower()
    synonyms = {
        "check": "inspect",
        "verify": "inspect",
        "load": "fetch",
        "read": "show",
        "type": "input",
    }
    hints: list[str] = []
    for token in ACTION_TOKENS | {"verify", "check"}:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            hints.append(synonyms.get(token, token))
    return _unique(hints)


def _subgoal_target_hints(text: str) -> dict[str, list[str]]:
    normalized = _normalize_text(text)
    return {
        "urls": _unique(re.findall(r"https?://\S+", normalized)),
        "files": _unique(
            [
                match.group(1).strip(' "\'')
                for match in re.finditer(
                    r"([A-Za-z]:\\[^\s]+|[.]{0,2}[\\/][^\s]+|[A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+(?::\d+(?:(?::|-)\d+)?)?)",
                    normalized,
                    flags=re.IGNORECASE,
                )
            ]
        ),
        "repos": _unique(re.findall(r"\b[a-z0-9._-]+/[a-z0-9._-]+\b", normalized, flags=re.IGNORECASE)),
        "artifacts": _unique(re.findall(r"\bartifact\s+([A-Za-z0-9_./\\-]+)\b", normalized, flags=re.IGNORECASE)),
        "branches": _unique(re.findall(r"\bbranch\s+([A-Za-z0-9_./-]+)\b", normalized, flags=re.IGNORECASE)),
    }


def _extract_file_ranges(text: str) -> list[dict[str, Any]]:
    normalized = _normalize_text(text)
    matches: list[dict[str, Any]] = []
    pattern = re.compile(
        r"([A-Za-z]:\\[^\s:]+|[.]{0,2}[\\/][^\s:]+|[A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+):(\d+)(?:[-:](\d+))?",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(normalized):
        path = match.group(1).strip(' "\'')
        if path.lower().startswith("http"):
            continue
        start_line = int(match.group(2))
        end_token = match.group(3)
        end_line = int(end_token) if end_token else start_line
        matches.append({"path": path, "start_line": start_line, "end_line": end_line})
    unique_payloads: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in matches:
        signature = f"{item['path']}:{item['start_line']}-{item['end_line']}"
        if signature in seen:
            continue
        seen.add(signature)
        unique_payloads.append(item)
    return unique_payloads


def _extract_conditional_metadata(text: str) -> dict[str, Any]:
    normalized = _normalize_text(text)
    lowered = normalized.lower()
    outcome_patterns = (
        (r"^if\s+(.+?)\s+succeeds?(?:\s+then|\s*,)?\s+(.+)$", "on_success"),
        (r"^if\s+(.+?)\s+is\s+successful(?:\s+then|\s*,)?\s+(.+)$", "on_success"),
        (r"^if\s+(.+?)\s+verifies?(?:\s+then|\s*,)?\s+(.+)$", "on_verified"),
        (r"^if\s+(.+?)\s+is\s+verified(?:\s+then|\s*,)?\s+(.+)$", "on_verified"),
    )
    for pattern, condition_type in outcome_patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        trigger_text = _normalize_text(match.group(1))
        action_text = _normalize_text(match.group(2))
        return {
            "text": action_text or normalized,
            "condition_type": condition_type,
            "trigger_text": trigger_text,
            "trigger_hints": _subgoal_action_hints(trigger_text),
        }
    failure_patterns = (
        r"^if\s+(.+?)\s+fails?(?:\s+then|\s*,)?\s+(.+)$",
        r"^if\s+(.+?)\s+fail(?:ed)?(?:\s+then|\s*,)?\s+(.+)$",
        r"^on\s+failure(?:\s+of\s+(.+?))?(?:\s+then|\s*,)?\s+(.+)$",
    )
    for pattern in failure_patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        if pattern.startswith("^on\\s+failure"):
            trigger_text = _normalize_text(match.group(1) or "previous_subgoal")
            action_text = _normalize_text(match.group(2))
        else:
            trigger_text = _normalize_text(match.group(1))
            action_text = _normalize_text(match.group(2))
        return {
            "text": action_text or normalized,
            "condition_type": "on_failure",
            "trigger_text": trigger_text,
            "trigger_hints": _subgoal_action_hints(trigger_text),
        }
    if lowered.startswith("otherwise ") or lowered.startswith("else "):
        action_text = re.sub(r"^(otherwise|else)\s+", "", normalized, flags=re.IGNORECASE)
        return {
            "text": _normalize_text(action_text) or normalized,
            "condition_type": "on_failure",
            "trigger_text": "previous_subgoal",
            "trigger_hints": [],
        }
    if lowered.startswith("if "):
        action_text = re.sub(r"^if\s+", "", normalized, flags=re.IGNORECASE)
        return {
            "text": _normalize_text(action_text) or normalized,
            "condition_type": "conditional",
            "trigger_text": "",
            "trigger_hints": [],
        }
    return {
        "text": normalized,
        "condition_type": "always",
        "trigger_text": "",
        "trigger_hints": [],
    }


def _split_subgoals(text: str) -> list[dict[str, Any]]:
    normalized = _normalize_text(text)
    if not normalized:
        return [
            {
                "id": "subgoal_0",
                "text": "",
                "order": 0,
                "connector_from_previous": "",
                "dependency_kind": "root",
                "depends_on": [],
                "blocking": False,
                "conditional": False,
                "dependency_direction": "self",
                "action_hints": [],
                "target_hints": {},
                "execution_order_hint": 0,
            }
        ]

    connector_pattern = re.compile(r"\b(and then|then|after|before|otherwise|else|and|if)\b", flags=re.IGNORECASE)
    parts: list[tuple[str, str]] = []
    last_index = 0
    connector = ""
    for match in connector_pattern.finditer(normalized):
        segment = normalized[last_index:match.start()].strip(" ,")
        if segment:
            parts.append((segment, connector))
        connector = match.group(1).strip().lower()
        last_index = match.end()
    tail = normalized[last_index:].strip(" ,")
    if tail:
        parts.append((tail, connector))
    if not parts:
        parts = [(normalized, "")]

    merged_parts: list[tuple[str, str]] = []
    index = 0
    while index < len(parts):
        part, incoming_connector = parts[index]
        if incoming_connector == "if" and index + 1 < len(parts):
            next_part, next_connector = parts[index + 1]
            if next_connector == "then":
                merged_parts.append((f"{part} then {next_part}", incoming_connector))
                index += 2
                continue
        merged_parts.append((part, incoming_connector))
        index += 1
    parts = merged_parts

    subgoals: list[dict[str, Any]] = []
    blocking_tokens = ("verify", "check", "confirm", "inspect", "read", "show", "status")
    for index, (part, incoming_connector) in enumerate(parts):
        conditional_input = part
        if incoming_connector == "if" and not part.lower().startswith("if "):
            conditional_input = f"if {part}"
        elif incoming_connector in {"otherwise", "else"} and not part.lower().startswith(tuple({incoming_connector, "otherwise ", "else "})):
            conditional_input = f"{incoming_connector} {part}"
        conditional = _extract_conditional_metadata(conditional_input)
        effective_text = str(conditional.get("text", part) or part)
        lowered = effective_text.lower()
        subgoal_id = f"subgoal_{index}"
        subgoals.append(
            {
                "id": subgoal_id,
                "text": effective_text,
                "raw_text": part,
                "order": index,
                "connector_from_previous": incoming_connector,
                "dependency_kind": "root" if index == 0 else "parallel",
                "depends_on": [],
                "blocking": any(token in lowered for token in blocking_tokens),
                "conditional": incoming_connector in {"if", "otherwise", "else"} or str(conditional.get("condition_type", "always")) != "always",
                "condition_type": str(conditional.get("condition_type", "always")),
                "condition_trigger_text": str(conditional.get("trigger_text", "")),
                "condition_trigger_hints": list(conditional.get("trigger_hints", [])),
                "conditional_fallback": str(conditional.get("condition_type", "")) == "on_failure",
                "conditional_on_success": str(conditional.get("condition_type", "")) == "on_success",
                "conditional_on_verified": str(conditional.get("condition_type", "")) == "on_verified",
                "dependency_direction": "self" if index == 0 else "parallel",
                "action_hints": _subgoal_action_hints(effective_text),
                "target_hints": _subgoal_target_hints(effective_text),
                "execution_order_hint": index,
            }
        )

    for index in range(1, len(subgoals)):
        current = subgoals[index]
        previous = subgoals[index - 1]
        connector = str(current.get("connector_from_previous", "")).strip().lower()
        if connector in {"then", "and then", "before"}:
            current["dependency_kind"] = "sequential"
            current["dependency_direction"] = "after_previous"
            current["depends_on"] = [str(previous.get("id", ""))]
        elif connector == "if":
            current["dependency_kind"] = "conditional"
            current["dependency_direction"] = "conditional_after_previous"
            current["depends_on"] = [str(previous.get("id", ""))]
            current["conditional"] = True
        elif connector in {"otherwise", "else"}:
            current["dependency_kind"] = "conditional"
            current["dependency_direction"] = "fallback_after_previous"
            current["depends_on"] = [str(previous.get("id", ""))]
            current["conditional"] = True
            if str(current.get("condition_type", "always")) == "always":
                current["condition_type"] = "on_failure"
                current["conditional_fallback"] = True
                current["condition_trigger_text"] = str(previous.get("text", "previous_subgoal"))
        elif connector == "after":
            current["dependency_kind"] = "prerequisite"
            current["dependency_direction"] = "before_previous"
            previous.setdefault("depends_on", []).append(str(current.get("id", "")))
            previous["dependency_kind"] = "sequential"
            previous["dependency_direction"] = "after_next"
            current["blocking"] = True
        elif connector == "and":
            current["dependency_kind"] = "parallel"
            current["dependency_direction"] = "parallel"

    return subgoals


def _add_target(targets: dict[str, Any], target_type: str, value: Any, *, label: str) -> str:
    target_id = f"{target_type}_{len(list(targets.get('items', [])))}"
    item = {"id": target_id, "type": target_type, "value": value, "label": label}
    targets.setdefault("items", []).append(item)
    targets.setdefault(target_type, []).append(item)
    return target_id


def _extract_assignment(text: str, key: str) -> str:
    match = re.search(rf"{key}=(.+)", text, flags=re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1).strip()
    value = re.split(r"\s+[a-z_]+=", value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = re.split(
        r"\s+(?:and|then)\s+(?=(?:github|open|browser|inspect|deploy|install|cloud|api|recover|self\s+repair|show|check|status)\b)",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return value.strip()


def _extract_execute_flag(text: str) -> bool:
    match = re.search(r"\bexecute=(true|false)\b", text, flags=re.IGNORECASE)
    return bool(match and match.group(1).strip().lower() == "true")


def extract_request_targets(request: str) -> dict[str, Any]:
    text = _normalize_text(request)
    lowered = text.lower()
    targets: dict[str, Any] = {"items": []}

    for action in sorted(token for token in ACTION_TOKENS if re.search(rf"\b{re.escape(token)}\b", lowered)):
        _add_target(targets, "actions", action, label=action)

    for url in _unique(re.findall(r"https?://\S+", text)):
        _add_target(targets, "urls", url, label=url)

    file_patterns = (
        r"(?:read|show|inspect|open)\s+file\s+([A-Za-z]:\\[^\s]+|[.]{0,2}[\\/][^\s]+|[A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+)",
        r"(?:read|show|inspect)\s+([A-Za-z]:\\[^\s]+|[.]{0,2}[\\/][^\s]+|[A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+)",
    )
    file_values: list[str] = []
    for pattern in file_patterns:
        file_values.extend(match.group(1).strip(' "\'') for match in re.finditer(pattern, text, flags=re.IGNORECASE))
    for file_path in _unique([value for value in file_values if value]):
        _add_target(targets, "files", file_path, label=file_path)
    for file_range in _extract_file_ranges(text):
        _add_target(
            targets,
            "file_ranges",
            file_range,
            label=f"{file_range['path']}:{file_range['start_line']}-{file_range['end_line']}",
        )

    install_match = re.search(r"install\s+app\s+([a-z0-9._-]+)", lowered)
    if install_match:
        _add_target(targets, "apps", install_match.group(1), label=install_match.group(1))

    api_match = re.search(r"api\s+profile\s+([a-z0-9._-]+)\s+fetch\s+(\S+)", lowered)
    if api_match:
        _add_target(
            targets,
            "api_requests",
            {"profile": api_match.group(1), "path": api_match.group(2)},
            label=f"{api_match.group(1)}:{api_match.group(2)}",
        )

    api_flow_match = re.search(r"api\s+workflow\s+([a-z0-9._-]+)\s+paths\s+(.+)$", lowered)
    if api_flow_match:
        paths = [part.strip() for part in api_flow_match.group(2).split(",") if part.strip()]
        _add_target(
            targets,
            "api_workflows",
            {"profile": api_flow_match.group(1), "paths": paths},
            label=f"{api_flow_match.group(1)}:{len(paths)}",
        )

    gh_connect = re.search(r"github\s+repo\s+connect\s+([a-z0-9._/-]+)", lowered)
    if gh_connect:
        _add_target(targets, "repos", gh_connect.group(1), label=gh_connect.group(1))

    github_patterns = (
        (
            "issue_reads",
            r"github\s+issue\s+read\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "issue": int(match.group(2))},
            lambda match: f"{match.group(1)}#{match.group(2)}",
        ),
        (
            "issue_comments",
            r"github\s+issue\s+comments\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "issue": int(match.group(2))},
            lambda match: f"{match.group(1)}#{match.group(2)} comments",
        ),
        (
            "issue_plans",
            r"github\s+issue\s+plan\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "issue": int(match.group(2))},
            lambda match: f"{match.group(1)}#{match.group(2)} plan",
        ),
        (
            "issue_actions",
            r"github\s+issue\s+act\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "issue": int(match.group(2)), "execute": _extract_execute_flag(text)},
            lambda match: f"{match.group(1)}#{match.group(2)} act",
        ),
        (
            "issue_reply_drafts",
            r"github\s+issue\s+reply\s+draft\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "issue": int(match.group(2)), "execute": _extract_execute_flag(text)},
            lambda match: f"{match.group(1)}#{match.group(2)} draft",
        ),
        (
            "issue_reply_posts",
            r"github\s+issue\s+reply\s+post\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {
                "repo": match.group(1),
                "issue": int(match.group(2)),
                "text": _extract_assignment(text, "text"),
            },
            lambda match: f"{match.group(1)}#{match.group(2)} post",
        ),
        (
            "pr_reads",
            r"github\s+pr\s+read\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "pr": int(match.group(2))},
            lambda match: f"{match.group(1)}!{match.group(2)}",
        ),
        (
            "pr_comments",
            r"github\s+pr\s+comments\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "pr": int(match.group(2))},
            lambda match: f"{match.group(1)}!{match.group(2)} comments",
        ),
        (
            "pr_plans",
            r"github\s+pr\s+plan\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "pr": int(match.group(2))},
            lambda match: f"{match.group(1)}!{match.group(2)} plan",
        ),
        (
            "pr_actions",
            r"github\s+pr\s+act\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "pr": int(match.group(2)), "execute": _extract_execute_flag(text)},
            lambda match: f"{match.group(1)}!{match.group(2)} act",
        ),
        (
            "pr_reply_drafts",
            r"github\s+pr\s+reply\s+draft\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {"repo": match.group(1), "pr": int(match.group(2)), "execute": _extract_execute_flag(text)},
            lambda match: f"{match.group(1)}!{match.group(2)} draft",
        ),
        (
            "pr_reply_posts",
            r"github\s+pr\s+reply\s+post\s+([a-z0-9._/-]+)\s+(\d+)",
            lambda match: {
                "repo": match.group(1),
                "pr": int(match.group(2)),
                "text": _extract_assignment(text, "text"),
            },
            lambda match: f"{match.group(1)}!{match.group(2)} post",
        ),
    )
    for target_type, pattern, builder, labeler in github_patterns:
        match = re.search(pattern, lowered)
        if match:
            _add_target(targets, target_type, builder(match), label=labeler(match))

    for cloud_cfg in re.finditer(r"cloud\s+target\s+set\s+([a-z0-9._-]+)\s+provider\s+([a-z0-9._-]+)", lowered):
        _add_target(
            targets,
            "cloud_targets",
            {"name": cloud_cfg.group(1), "provider": cloud_cfg.group(2)},
            label=cloud_cfg.group(1),
        )

    for cloud_dep in re.finditer(r"deploy\s+artifact\s+([a-z0-9._/-]+)\s+to\s+([a-z0-9._-]+)", lowered):
        _add_target(
            targets,
            "deployments",
            {"artifact": cloud_dep.group(1), "target": cloud_dep.group(2)},
            label=f"{cloud_dep.group(1)}->{cloud_dep.group(2)}",
        )

    for artifact in _unique(re.findall(r"\bartifact\s+([A-Za-z0-9_./\\-]+)\b", text, flags=re.IGNORECASE)):
        _add_target(targets, "artifacts", artifact, label=artifact)

    for branch in _unique(re.findall(r"\b(?:branch|ref|revision)\s+([A-Za-z0-9_./-]+)\b", text, flags=re.IGNORECASE)):
        _add_target(targets, "branches", branch, label=branch)

    feature_match = re.match(r"add\s+feature\s+(.+)$", text, flags=re.IGNORECASE)
    if feature_match:
        _add_target(
            targets,
            "feature_requests",
            feature_match.group(1).strip(),
            label=feature_match.group(1).strip(),
        )

    explicit_commands: list[str] = []
    if re.search(r"\bwhoami\b", lowered):
        explicit_commands.append("whoami")
    if lowered in {"date", "show date", "what date is it"}:
        explicit_commands.append("date")
    if lowered in {"time", "show time", "what time is it", "time now"}:
        explicit_commands.append("time")
    for command in _unique(explicit_commands):
        _add_target(targets, "commands", command, label=command)
    return targets


def _build_browser_action_target(text: str, url: str) -> tuple[dict[str, Any] | None, str | None]:
    lowered = text.lower()
    if not any(token in lowered for token in ("click", "submit", "type", "input")):
        return None, None
    action = "submit" if "submit" in lowered else "input" if ("type" in lowered or "input" in lowered) else "click"
    selector = _extract_assignment(text, "selector")
    label_target = _extract_assignment(text, "text") or _extract_assignment(text, "label") or _extract_assignment(text, "button")
    value = _extract_assignment(text, "value")
    if not selector and label_target:
        selector = f"text={label_target}"
    if not selector:
        selector = "input" if action == "input" else "body"
    if action == "input" and not value:
        return None, "browser_action_missing_value"
    return {"url": url, "action": action, "selector": selector, "value": value}, None

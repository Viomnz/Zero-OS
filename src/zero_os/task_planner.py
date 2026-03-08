from __future__ import annotations

import re
from zero_os.playbook_memory import lookup
from zero_os.structured_intent import extract_intent


def build_plan(request: str) -> dict:
    text = request.strip()
    lowered = text.lower()
    intent = extract_intent(request)
    remembered = lookup(".", intent["intent"])
    steps: list[dict] = []
    if remembered.get("ok", False):
        steps.extend(list(remembered["plan"].get("steps", [])))
    if intent["intent"] == "tools" or any(token in lowered for token in ("tools", "capabilities", "what can you do")):
        steps.append({"kind": "tool_registry", "target": "registry"})
    if intent["intent"] == "web" or "http://" in lowered or "https://" in lowered:
        urls = re.findall(r"https?://\S+", text)
        for url in urls:
            steps.append({"kind": "web_verify", "target": url})
            if any(token in lowered for token in ("fetch", "open", "read", "load")):
                steps.append({"kind": "web_fetch", "target": url})
                if "open" in lowered:
                    steps.append({"kind": "browser_open", "target": url})
                if any(token in lowered for token in ("click", "submit", "type")):
                    steps.append({"kind": "browser_action", "target": {"action": "click", "selector": "body"}})
    if intent["intent"] == "status" or any(token in lowered for token in ("status", "diagnostic", "health", "check")):
        steps.append({"kind": "system_status", "target": "health"})
    if any(token in lowered for token in ("browser status", "tabs", "session")):
        steps.append({"kind": "browser_status", "target": "browser"})
    if any(token in lowered for token in ("inspect page", "dom inspect")) and ("http://" in lowered or "https://" in lowered):
        for url in re.findall(r"https?://\S+", text):
            steps.append({"kind": "browser_dom_inspect", "target": url})
    if intent["intent"] == "store_status" or "native store status" in lowered or "store status" in lowered:
        steps.append({"kind": "store_status", "target": "native_store"})
    install_match = re.search(r"install\s+app\s+([a-z0-9._-]+)", lowered)
    if install_match:
        steps.append({"kind": "store_install", "target": install_match.group(1)})
    if intent["intent"] == "self_repair" or any(token in lowered for token in ("repair", "self repair")):
        steps.append({"kind": "self_repair", "target": "runtime"})
    if intent["intent"] == "recover" or any(token in lowered for token in ("recover", "recovery")):
        steps.append({"kind": "recover", "target": "runtime"})
    api_match = re.search(r"api\s+profile\s+([a-z0-9._-]+)\s+fetch\s+(\S+)", lowered)
    if api_match:
        steps.append({"kind": "api_request", "target": {"profile": api_match.group(1), "path": api_match.group(2)}})
    api_flow_match = re.search(r"api\s+workflow\s+([a-z0-9._-]+)\s+paths\s+(.+)$", lowered)
    if api_flow_match:
        parts = [p.strip() for p in api_flow_match.group(2).split(",") if p.strip()]
        steps.append({"kind": "api_workflow", "target": {"profile": api_flow_match.group(1), "paths": parts}})
    gh_match = re.search(r"github\s+repo\s+connect\s+([a-z0-9._/-]+)", lowered)
    if gh_match:
        steps.append({"kind": "github_connect", "target": gh_match.group(1)})
    gh_issues = re.search(r"github\s+issues\s+([a-z0-9._/-]+)", lowered)
    if gh_issues:
        steps.append({"kind": "github_issues", "target": gh_issues.group(1)})
    cloud_cfg = re.search(r"cloud\s+target\s+set\s+([a-z0-9._-]+)\s+provider\s+([a-z0-9._-]+)", lowered)
    if cloud_cfg:
        steps.append({"kind": "cloud_target_set", "target": {"name": cloud_cfg.group(1), "provider": cloud_cfg.group(2)}})
    cloud_dep = re.search(r"deploy\s+artifact\s+([a-z0-9._/-]+)\s+to\s+([a-z0-9._-]+)", lowered)
    if cloud_dep:
        steps.append({"kind": "cloud_deploy", "target": {"artifact": cloud_dep.group(1), "target": cloud_dep.group(2)}})
    if any(token in lowered for token in ("read file", "show ", "whoami", "date", "time")):
        steps.append({"kind": "highway_dispatch", "target": text})
    if any(token in lowered for token in ("fix", "repair", "recover")):
        steps.append({"kind": "autonomy_gate", "target": text})
    if not steps:
        steps.append({"kind": "observe", "target": text})
    return {"ok": True, "request": text, "intent": intent, "steps": steps}

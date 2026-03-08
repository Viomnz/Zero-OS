"""Agent capability that chains tasks through the same highway."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from zero_os.types import Result, Task


DispatchFn = Callable[[str, str], Result]


class AgentCapability:
    name = "agent"

    def __init__(self, dispatch_non_agent: DispatchFn) -> None:
        self._dispatch_non_agent = dispatch_non_agent

    def can_handle(self, task: Task) -> bool:
        text = task.text.lower().strip()
        if text.startswith("zero ai agent monitor triad balance"):
            return False
        return (
            text.startswith("agent ")
            or text.startswith("agent:")
            or text.startswith("codex ")
            or text.startswith("codex:")
            or text.startswith("zero ai agent ")
            or "plan and execute" in text
        )

    def run(self, task: Task) -> Result:
        text = task.text.strip()
        lower = text.lower().strip()
        if lower.startswith("codex ") or lower.startswith("codex:") or lower.startswith("zero ai agent "):
            return self._run_codex_style(task)

        normalized = text.removeprefix("agent:").removeprefix("agent ").strip()
        if normalized.lower().startswith("plan and execute"):
            normalized = normalized[16:].strip(" :")

        steps = [s.strip() for s in normalized.split(" then ") if s.strip()]
        if not steps:
            return Result(self.name, "No executable steps provided.")
        if task.mode == "heavy":
            max_steps = {"low": 5, "balanced": 10, "high": 14}.get(
                task.performance_profile, 10
            )
        else:
            max_steps = {"low": 2, "balanced": 3, "high": 5}.get(
                task.performance_profile, 3
            )
        steps = steps[:max_steps]

        lines: list[str] = []
        for i, step in enumerate(steps, start=1):
            result = self._dispatch_non_agent(step, task.cwd)
            lines.append(f"{i}. [{result.capability}] {step}")
            lines.append(f"   {result.summary}")

        if len([s.strip() for s in normalized.split(' then ') if s.strip()]) > max_steps:
            lines.append(f"Truncated to {max_steps} steps in {task.mode} mode.")
        return Result(self.name, "\n".join(lines))

    def _run_codex_style(self, task: Task) -> Result:
        raw = task.text.strip()
        goal = re.sub(r"^(codex:|codex |zero ai agent )", "", raw, flags=re.IGNORECASE).strip()
        intelligence = self._load_intelligence(task.cwd)
        suggest_match = re.match(r"^suggest route\s*:\s*(.+)$", goal, flags=re.IGNORECASE)
        option_match = re.match(r"^option\s+(\d+)\s*:\s*(.+)$", goal, flags=re.IGNORECASE)

        if suggest_match:
            suggest_goal = suggest_match.group(1).strip()
            options = self._rank_options(self._route_options(suggest_goal), suggest_goal, intelligence)
            lines = ["codex_style: suggest_only", f"route_options: {len(options)}"]
            for idx, opt in enumerate(options, start=1):
                lines.append(f"option {idx}: " + " -> ".join(opt))
            return Result(self.name, "\n".join(lines))

        option_index = 1
        if option_match:
            option_index = max(1, int(option_match.group(1)))
            goal = option_match.group(2).strip()

        explicit_steps = self._split_steps(goal)
        options = self._rank_options(self._route_options(goal), goal, intelligence)
        if explicit_steps:
            steps = explicit_steps
            selected_idx = 0
        else:
            chosen = min(option_index, len(options)) if options else 1
            steps = options[chosen - 1] if options else self._plan_steps(goal)
            selected_idx = chosen

        max_steps = {"low": 6, "balanced": 12, "high": 20}.get(task.performance_profile, 12)
        steps = [s for s in steps if s][:max_steps]
        if not steps:
            return Result(self.name, "No codex steps provided.")

        lines: list[str] = ["codex_style: enabled"]
        proactive = self._proactive_suggestions(task.cwd, task)
        if proactive:
            lines.append("proactive_suggestions:")
            for item in proactive:
                lines.append(f"- {item}")
        if options:
            if explicit_steps:
                selected_idx = 0
            lines.append(f"route_options: {len(options)} (auto-selected: {selected_idx})")
            for idx, opt in enumerate(options, start=1):
                lines.append(f"option {idx}: " + " -> ".join(opt))
        for i, step in enumerate(steps, start=1):
            result = self._dispatch_non_agent(step, task.cwd)
            lines.append(f"{i}. [{result.capability}] {step}")
            lines.append(f"   {result.summary}")

        lines.append("verification:")
        verify = self._dispatch_non_agent("audit status", task.cwd)
        lines.append(f"- [{verify.capability}] audit status")
        lines.append(f"  {verify.summary}")
        readiness = self._dispatch_non_agent("os readiness", task.cwd)
        lines.append(f"- [{readiness.capability}] os readiness")
        lines.append(f"  {readiness.summary}")
        self._record_execution(task.cwd, goal, steps, selected_idx, lines)
        return Result(self.name, "\n".join(lines))

    @staticmethod
    def _split_steps(text: str) -> list[str]:
        if not text:
            return []
        if " then " in text.lower():
            return [s.strip() for s in re.split(r"\bthen\b", text, flags=re.IGNORECASE) if s.strip()]
        if "&&" in text:
            return [s.strip() for s in text.split("&&") if s.strip()]
        if ";" in text:
            return [s.strip() for s in text.split(";") if s.strip()]
        return []

    @staticmethod
    def _plan_steps(goal: str) -> list[str]:
        g = goal.strip()
        gl = g.lower()
        steps = ["os readiness"]

        if not g:
            return steps + ["list files"]

        if gl.startswith(("create file ", "new file ", "write ", "append to ", "add to ", "read file ", "show ")):
            steps.append(g)
            return steps

        if "search " in gl or "find " in gl or "look up " in gl:
            query = re.sub(r"^(search|find|look up)\s+", "", g, flags=re.IGNORECASE).strip()
            steps.append(f"search {query or g}")
            return steps

        if "fetch " in gl or gl.startswith("http://") or gl.startswith("https://"):
            if gl.startswith(("http://", "https://")):
                steps.append(f"fetch {g}")
            else:
                steps.append(g if gl.startswith("fetch ") else f"fetch {g}")
            return steps

        m_create = re.search(r"create\s+(.+?)\s+file\s+(.+)$", g, flags=re.IGNORECASE)
        if m_create:
            content = m_create.group(1).strip()
            path = m_create.group(2).strip().strip("\"'")
            steps.append(f"create file {path} with {content}")
            steps.append(f"read file {path}")
            return steps

        m_read = re.search(r"read\s+(.+)$", g, flags=re.IGNORECASE)
        if m_read and "." in m_read.group(1):
            path = m_read.group(1).strip().strip("\"'")
            steps.append(f"read file {path}")
            return steps

        if "readiness" in gl or "health" in gl or "status" in gl:
            steps.append("os readiness --json")
            steps.append("audit status")
            return steps

        if "plugin" in gl and "scaffold" in gl:
            steps.append(g)
            return steps

        # Fallback: run goal directly and preserve codex verification.
        steps.append(g)
        return steps

    @staticmethod
    def _route_options(goal: str) -> list[list[str]]:
        g = goal.strip()
        gl = g.lower()
        if not g:
            return [["os readiness", "list files"]]

        options: list[list[str]] = []
        planned = AgentCapability._plan_steps(g)
        options.append(planned)

        if "create" in gl and "file" in gl:
            canonical = AgentCapability._plan_steps(g)
            create_step = next((s for s in canonical if s.lower().startswith("create file ")), "")
            read_step = next((s for s in canonical if s.lower().startswith("read file ")), "")
            if create_step:
                options.append(["os readiness --json", create_step, "audit status"])
                options.append(["os readiness", create_step, read_step] if read_step else ["os readiness", create_step])
                if read_step:
                    options.append([create_step, read_step, "audit status"])
        elif "search" in gl or "find" in gl or "look up" in gl:
            q = re.sub(r"^(search|find|look up)\s+", "", g, flags=re.IGNORECASE).strip() or g
            options.append(["search " + q])
            options.append(["search " + q, "remember top web results for " + q])
            options.append(["os readiness", "search " + q, "audit status"])
        elif "readiness" in gl or "security" in gl or "status" in gl:
            options.append(["os readiness --json"])
            options.append(["os readiness", "audit status"])
            options.append(["os readiness", "os readiness --json", "audit status"])
        else:
            options.append(["os readiness", g])
            options.append([g, "audit status"])
            options.append(["os readiness --json", g, "audit status"])

        uniq: list[list[str]] = []
        seen = set()
        for opt in options:
            key = "||".join(opt)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(opt)
            if len(uniq) >= 9:
                break
        return uniq

    @staticmethod
    def _runtime_path(cwd: str) -> Path:
        p = Path(cwd).resolve() / ".zero_os" / "runtime" / "agent_intelligence.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_intelligence(self, cwd: str) -> dict:
        p = self._runtime_path(cwd)
        if not p.exists():
            data = {
                "history": [],
                "route_stats": {},
                "user_profile": {
                    "heavy_ratio": 0.0,
                    "top_goal_kinds": {},
                },
            }
            p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return data
        try:
            return json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {"history": [], "route_stats": {}, "user_profile": {"heavy_ratio": 0.0, "top_goal_kinds": {}}}

    def _save_intelligence(self, cwd: str, data: dict) -> None:
        self._runtime_path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _goal_kind(goal: str) -> str:
        gl = goal.lower()
        if "search" in gl or "find" in gl or "look up" in gl:
            return "web"
        if "create" in gl or "file" in gl or "read" in gl or "write" in gl:
            return "code"
        if "readiness" in gl or "status" in gl or "security" in gl:
            return "system"
        return "general"

    def _rank_options(self, options: list[list[str]], goal: str, intelligence: dict) -> list[list[str]]:
        if not options:
            return options
        kind = self._goal_kind(goal)
        stats = intelligence.get("route_stats", {})
        # Preserve authored order until a route has enough history.
        min_runs = 3
        has_confident_stats = False
        for opt in options:
            key = kind + "|" + "||".join(opt)
            entry = stats.get(key, {"runs": 0})
            if int(entry.get("runs", 0)) >= min_runs:
                has_confident_stats = True
                break
        if not has_confident_stats:
            return options
        scored = []
        for opt in options:
            key = kind + "|" + "||".join(opt)
            entry = stats.get(key, {"success": 0, "runs": 0})
            runs = max(1, int(entry.get("runs", 0)))
            success = int(entry.get("success", 0))
            score = success / runs
            scored.append((score, -len(opt), opt))
        scored.sort(reverse=True)
        return [x[2] for x in scored]

    def _record_execution(self, cwd: str, goal: str, steps: list[str], selected_idx: int, output_lines: list[str]) -> None:
        data = self._load_intelligence(cwd)
        kind = self._goal_kind(goal)
        ts = datetime.now(timezone.utc).isoformat()
        success = 1
        text = "\n".join(output_lines).lower()
        if "blocked" in text or "fail" in text or "error" in text:
            success = 0

        entry = {
            "time_utc": ts,
            "goal": goal,
            "goal_kind": kind,
            "selected_option": selected_idx,
            "steps": steps,
            "success": success,
        }
        history = data.get("history", [])
        history.append(entry)
        data["history"] = history[-300:]

        route_key = kind + "|" + "||".join(steps)
        stats = data.get("route_stats", {})
        current = stats.get(route_key, {"runs": 0, "success": 0})
        current["runs"] = int(current.get("runs", 0)) + 1
        current["success"] = int(current.get("success", 0)) + success
        stats[route_key] = current
        data["route_stats"] = stats

        profile = data.get("user_profile", {"heavy_ratio": 0.0, "top_goal_kinds": {}})
        kinds = profile.get("top_goal_kinds", {})
        kinds[kind] = int(kinds.get(kind, 0)) + 1
        profile["top_goal_kinds"] = kinds
        # Estimate heavy usage from long route selections.
        heavy_count = sum(1 for h in data["history"] if len(h.get("steps", [])) >= 3)
        total = max(1, len(data["history"]))
        profile["heavy_ratio"] = round(heavy_count / total, 3)
        data["user_profile"] = profile
        self._save_intelligence(cwd, data)

    def _proactive_suggestions(self, cwd: str, task: Task) -> list[str]:
        tips: list[str] = []
        base = Path(cwd).resolve()
        runtime = base / ".zero_os" / "runtime"
        if not (runtime / "agent_integrity_baseline.json").exists():
            tips.append("Run baseline-agent to activate trusted restore.")
        if not (runtime / "security_report.json").exists():
            tips.append("Run security-agent to initialize layered security report.")
        if task.mode == "casual":
            tips.append("Use heavy mode for bigger chained execution: mode set heavy.")
        state = self._load_intelligence(cwd).get("user_profile", {})
        heavy_ratio = float(state.get("heavy_ratio", 0.0))
        if heavy_ratio > 0.7 and task.mode != "heavy":
            tips.append("Your usage is heavy-route dominant. Keep mode heavy for best throughput.")
        return tips[:4]

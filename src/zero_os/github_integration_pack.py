from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from zero_os.fast_path_cache import cached_compute
from zero_os.state_cache import json_state_revision


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "integrations" / "github.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"repos": {}, "events": []}, indent=2) + "\n", encoding="utf-8")
    return path


def _load(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def _save(cwd: str, data: dict) -> None:
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _repo_config(cwd: str, repo: str) -> dict:
    data = _load(cwd)
    return dict(data.get("repos", {}).get(repo, {}))


def _headers(token: str = "") -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "zero-os-github-intake",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _api_get(url: str, token: str = "") -> tuple[int, Any]:
    req = request.Request(url, headers=_headers(token), method="GET")
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except Exception:
                payload = {"message": raw.strip() or str(exc)}
            return exc.code, payload
        finally:
            close = getattr(exc, "close", None)
            if callable(close):
                close()
    except Exception as exc:
        return 0, {"message": str(exc)}


def _api_post(url: str, payload: dict[str, Any], token: str = "") -> tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8")
    headers = _headers(token)
    headers["Content-Type"] = "application/json"
    req = request.Request(url, headers=headers, data=data, method="POST")
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw.strip() else {}
            except Exception:
                body = {"message": raw.strip() or str(exc)}
            return exc.code, body
        finally:
            close = getattr(exc, "close", None)
            if callable(close):
                close()
    except Exception as exc:
        return 0, {"message": str(exc)}


def _build_reply_text(kind: str, item: dict[str, Any], plan: dict[str, Any], action: dict[str, Any] | None = None) -> str:
    label = "PR" if kind == "pull_request" else "issue"
    number = int(item.get("number", 0))
    title = str(item.get("title", "")).strip()
    steps = list(plan.get("steps", []))
    actionable = list((action or {}).get("actionable_steps", []))
    executed = bool(action and action.get("execution"))
    lines = [
        f"Zero AI reviewed this {label} request.",
    ]
    if title:
        heading = "PR" if label == "PR" else "Issue"
        lines.append(f"{heading} #{number}: {title}")
    if steps:
        lines.append(f"Planned steps: {len(steps)}")
    if actionable:
        lines.append(f"Local actionable steps: {len(actionable)}")
    if executed:
        summary = str((action or {}).get("summary", "")).strip()
        if summary:
            lines.append(f"Execution summary: {summary}")
        else:
            lines.append("Execution summary: local guarded actions ran.")
    else:
        lines.append("Status: analysis and planning only. No GitHub writeback or local execution was performed automatically.")
    lines.append("Reply generated in safe mode. Post explicitly if you want this sent to GitHub.")
    return "\n".join(lines).strip()


def _build_status(cwd: str) -> dict:
    return _load(cwd)


def status(cwd: str) -> dict:
    path = _path(cwd)
    data, cache_meta = cached_compute(
        "github_integration_status",
        str(path),
        lambda: {"github_integration": json_state_revision(path)},
        lambda: _build_status(cwd),
        ttl_seconds=None,
    )
    data = dict(data)
    data["fast_path_cache"] = {"hit": bool(cache_meta.get("hit", False))}
    return data


def connect_repo(cwd: str, repo: str, token: str = "") -> dict:
    data = _load(cwd)
    repo_name = repo.strip()
    cfg = data.setdefault("repos", {}).setdefault(repo_name, {})
    if token:
        cfg["token"] = token.strip()
    cfg["token_set"] = bool(cfg.get("token"))
    cfg["connected"] = True
    cfg["updated_utc"] = _utc_now()
    _save(cwd, data)
    return {"ok": True, "repo": repo_name, "token_set": cfg["token_set"]}


def issue_summary(cwd: str, repo: str, state: str = "open", limit: int = 10) -> dict:
    repo_name = repo.strip()
    token = str(_repo_config(cwd, repo_name).get("token", ""))
    params = parse.urlencode({"state": state, "per_page": max(1, min(100, int(limit)))})
    status_code, payload = _api_get(f"https://api.github.com/repos/{repo_name}/issues?{params}", token)
    if status_code != 200 or not isinstance(payload, list):
        return {"ok": False, "repo": repo_name, "status": status_code, "error": payload}
    issues = []
    for item in payload:
        if "pull_request" in item:
            continue
        issues.append(
            {
                "id": int(item.get("number", 0)),
                "title": str(item.get("title", "")),
                "state": str(item.get("state", "")),
                "user": str((item.get("user") or {}).get("login", "")),
                "created_at": str(item.get("created_at", "")),
                "updated_at": str(item.get("updated_at", "")),
                "url": str(item.get("html_url", "")),
            }
        )
    return {"ok": True, "repo": repo_name, "issues": issues[: max(1, min(100, int(limit)))]}


def pr_summary(cwd: str, repo: str, state: str = "open", limit: int = 10) -> dict:
    repo_name = repo.strip()
    token = str(_repo_config(cwd, repo_name).get("token", ""))
    params = parse.urlencode({"state": state, "per_page": max(1, min(100, int(limit)))})
    status_code, payload = _api_get(f"https://api.github.com/repos/{repo_name}/pulls?{params}", token)
    if status_code != 200 or not isinstance(payload, list):
        return {"ok": False, "repo": repo_name, "status": status_code, "error": payload}
    pulls = []
    for item in payload:
        pulls.append(
            {
                "id": int(item.get("number", 0)),
                "title": str(item.get("title", "")),
                "state": str(item.get("state", "")),
                "user": str((item.get("user") or {}).get("login", "")),
                "created_at": str(item.get("created_at", "")),
                "updated_at": str(item.get("updated_at", "")),
                "url": str(item.get("html_url", "")),
                "draft": bool(item.get("draft", False)),
            }
        )
    return {"ok": True, "repo": repo_name, "pull_requests": pulls[: max(1, min(100, int(limit)))]}


def pr_comments(cwd: str, repo: str, pr_number: int, limit: int = 20) -> dict:
    repo_name = repo.strip()
    token = str(_repo_config(cwd, repo_name).get("token", ""))
    params = parse.urlencode({"per_page": max(1, min(100, int(limit)))})
    issue_status, issue_payload = _api_get(
        f"https://api.github.com/repos/{repo_name}/issues/{int(pr_number)}/comments?{params}",
        token,
    )
    review_status, review_payload = _api_get(
        f"https://api.github.com/repos/{repo_name}/pulls/{int(pr_number)}/comments?{params}",
        token,
    )
    if issue_status != 200 or not isinstance(issue_payload, list):
        issue_payload = []
    if review_status != 200 or not isinstance(review_payload, list):
        review_payload = []
    comments = []
    for item in issue_payload:
        comments.append(
            {
                "kind": "issue_comment",
                "user": str((item.get("user") or {}).get("login", "")),
                "body": str(item.get("body") or "").strip(),
                "created_at": str(item.get("created_at", "")),
                "url": str(item.get("html_url", "")),
            }
        )
    for item in review_payload:
        comments.append(
            {
                "kind": "review_comment",
                "user": str((item.get("user") or {}).get("login", "")),
                "body": str(item.get("body") or "").strip(),
                "created_at": str(item.get("created_at", "")),
                "path": str(item.get("path") or ""),
                "url": str(item.get("html_url", "")),
            }
        )
    comments.sort(key=lambda item: item.get("created_at", ""))
    return {"ok": True, "repo": repo_name, "pull_request": int(pr_number), "comments": comments[: max(1, min(200, int(limit) * 2))]}


def issue_comments(cwd: str, repo: str, issue_number: int, limit: int = 20) -> dict:
    repo_name = repo.strip()
    token = str(_repo_config(cwd, repo_name).get("token", ""))
    params = parse.urlencode({"per_page": max(1, min(100, int(limit)))})
    status_code, payload = _api_get(
        f"https://api.github.com/repos/{repo_name}/issues/{int(issue_number)}/comments?{params}",
        token,
    )
    if status_code != 200 or not isinstance(payload, list):
        return {"ok": False, "repo": repo_name, "issue": int(issue_number), "status": status_code, "error": payload}
    comments = []
    for item in payload:
        comments.append(
            {
                "kind": "issue_comment",
                "user": str((item.get("user") or {}).get("login", "")),
                "body": str(item.get("body") or "").strip(),
                "created_at": str(item.get("created_at", "")),
                "url": str(item.get("html_url", "")),
            }
        )
    comments.sort(key=lambda item: item.get("created_at", ""))
    return {"ok": True, "repo": repo_name, "issue": int(issue_number), "comments": comments[: max(1, min(100, int(limit)))]}


def issue_read(cwd: str, repo: str, issue_number: int) -> dict:
    repo_name = repo.strip()
    token = str(_repo_config(cwd, repo_name).get("token", ""))
    status_code, payload = _api_get(f"https://api.github.com/repos/{repo_name}/issues/{int(issue_number)}", token)
    if status_code != 200 or not isinstance(payload, dict):
        return {"ok": False, "repo": repo_name, "issue": int(issue_number), "status": status_code, "error": payload}
    if "pull_request" in payload:
        return {"ok": False, "repo": repo_name, "issue": int(issue_number), "reason": "pull_request_not_supported_yet"}
    comments = issue_comments(cwd, repo_name, issue_number, limit=20)
    body = str(payload.get("body") or "").strip()
    title = str(payload.get("title") or "").strip()
    comment_lines = []
    for item in comments.get("comments", []):
        body_text = str(item.get("body", "")).strip()
        user = str(item.get("user", "")).strip()
        if body_text:
            prefix = f"{user}: " if user else ""
            comment_lines.append(prefix + body_text)
    comment_text = "\n".join(comment_lines[-10:])
    request_text = "\n\n".join(part for part in [title, body, comment_text] if part).strip()
    return {
        "ok": True,
        "repo": repo_name,
        "issue": {
            "number": int(payload.get("number", issue_number)),
            "title": title,
            "body": body,
            "state": str(payload.get("state", "")),
            "user": str((payload.get("user") or {}).get("login", "")),
            "labels": [str((label or {}).get("name", "")) for label in payload.get("labels", []) if isinstance(label, dict)],
            "url": str(payload.get("html_url", "")),
            "request_text": request_text,
            "comments": comments.get("comments", []),
        },
    }


def pr_read(cwd: str, repo: str, pr_number: int) -> dict:
    repo_name = repo.strip()
    token = str(_repo_config(cwd, repo_name).get("token", ""))
    status_code, payload = _api_get(f"https://api.github.com/repos/{repo_name}/pulls/{int(pr_number)}", token)
    if status_code != 200 or not isinstance(payload, dict):
        return {"ok": False, "repo": repo_name, "pull_request": int(pr_number), "status": status_code, "error": payload}
    comments = pr_comments(cwd, repo_name, pr_number, limit=20)
    body = str(payload.get("body") or "").strip()
    title = str(payload.get("title") or "").strip()
    comment_lines = []
    for item in comments.get("comments", []):
        body_text = str(item.get("body", "")).strip()
        user = str(item.get("user", "")).strip()
        if body_text:
            prefix = f"{user}: " if user else ""
            comment_lines.append(prefix + body_text)
    comment_text = "\n".join(comment_lines[-10:])
    request_text = "\n\n".join(part for part in [title, body, comment_text] if part).strip()
    return {
        "ok": True,
        "repo": repo_name,
        "pull_request": {
            "number": int(payload.get("number", pr_number)),
            "title": title,
            "body": body,
            "state": str(payload.get("state", "")),
            "user": str((payload.get("user") or {}).get("login", "")),
            "draft": bool(payload.get("draft", False)),
            "labels": [str((label or {}).get("name", "")) for label in payload.get("labels", []) if isinstance(label, dict)],
            "url": str(payload.get("html_url", "")),
            "request_text": request_text,
            "comments": comments.get("comments", []),
        },
    }


def issue_plan(cwd: str, repo: str, issue_number: int) -> dict:
    from zero_os.task_planner import build_plan

    issue = issue_read(cwd, repo, issue_number)
    if not issue.get("ok", False):
        return issue
    request_text = issue["issue"].get("request_text", "")
    plan = build_plan(request_text, cwd)
    return {
        "ok": True,
        "repo": repo,
        "issue": issue["issue"],
        "plan": plan,
        "mode": "read_and_plan_only",
    }


def pr_plan(cwd: str, repo: str, pr_number: int) -> dict:
    from zero_os.task_planner import build_plan

    pr = pr_read(cwd, repo, pr_number)
    if not pr.get("ok", False):
        return pr
    request_text = pr["pull_request"].get("request_text", "")
    plan = build_plan(request_text, cwd)
    return {
        "ok": True,
        "repo": repo,
        "pull_request": pr["pull_request"],
        "plan": plan,
        "mode": "read_and_plan_only",
    }


def issue_act(cwd: str, repo: str, issue_number: int, execute: bool = False) -> dict:
    from zero_os.result_synthesizer import synthesize_result
    from zero_os.unified_action_engine import execute_step

    planned = issue_plan(cwd, repo, issue_number)
    if not planned.get("ok", False):
        return planned
    steps = list(planned.get("plan", {}).get("steps", []))
    actionable = [
        step for step in steps if step.get("kind") not in {"github_connect", "github_issues"}
    ]
    if not execute:
        return {
            "ok": True,
            "repo": repo,
            "issue": planned["issue"],
            "plan": planned["plan"],
            "actionable_steps": actionable,
            "mode": "preview_only",
        }
    results = [execute_step(cwd, step) for step in actionable]
    run = {"ok": all(bool(item.get("ok", False)) for item in results) if results else True, "results": results}
    return {
        "ok": run["ok"],
        "repo": repo,
        "issue": planned["issue"],
        "plan": planned["plan"],
        "actionable_steps": actionable,
        "execution": run,
        "summary": synthesize_result(run),
        "mode": "local_actions_only",
    }


def pr_act(cwd: str, repo: str, pr_number: int, execute: bool = False) -> dict:
    from zero_os.result_synthesizer import synthesize_result
    from zero_os.unified_action_engine import execute_step

    planned = pr_plan(cwd, repo, pr_number)
    if not planned.get("ok", False):
        return planned
    steps = list(planned.get("plan", {}).get("steps", []))
    actionable = [
        step for step in steps if step.get("kind") not in {"github_connect", "github_issues", "github_prs"}
    ]
    if not execute:
        return {
            "ok": True,
            "repo": repo,
            "pull_request": planned["pull_request"],
            "plan": planned["plan"],
            "actionable_steps": actionable,
            "mode": "preview_only",
        }
    results = [execute_step(cwd, step) for step in actionable]
    run = {"ok": all(bool(item.get("ok", False)) for item in results) if results else True, "results": results}
    return {
        "ok": run["ok"],
        "repo": repo,
        "pull_request": planned["pull_request"],
        "plan": planned["plan"],
        "actionable_steps": actionable,
        "execution": run,
        "summary": synthesize_result(run),
        "mode": "local_actions_only",
    }


def issue_reply_draft(cwd: str, repo: str, issue_number: int, execute: bool = False) -> dict:
    planned = issue_plan(cwd, repo, issue_number)
    if not planned.get("ok", False):
        return planned
    action = issue_act(cwd, repo, issue_number, execute=True) if execute else None
    issue = planned["issue"]
    body = _build_reply_text("issue", issue, planned.get("plan", {}), action)
    return {
        "ok": True,
        "repo": repo,
        "issue": issue,
        "plan": planned.get("plan", {}),
        "draft": {
            "body": body,
            "execute": bool(execute),
            "preview_only": not execute,
        },
        "execution": (action or {}).get("execution"),
        "summary": (action or {}).get("summary"),
        "mode": "draft_only",
    }


def pr_reply_draft(cwd: str, repo: str, pr_number: int, execute: bool = False) -> dict:
    planned = pr_plan(cwd, repo, pr_number)
    if not planned.get("ok", False):
        return planned
    action = pr_act(cwd, repo, pr_number, execute=True) if execute else None
    pr = planned["pull_request"]
    body = _build_reply_text("pull_request", pr, planned.get("plan", {}), action)
    return {
        "ok": True,
        "repo": repo,
        "pull_request": pr,
        "plan": planned.get("plan", {}),
        "draft": {
            "body": body,
            "execute": bool(execute),
            "preview_only": not execute,
        },
        "execution": (action or {}).get("execution"),
        "summary": (action or {}).get("summary"),
        "mode": "draft_only",
    }


def issue_reply_post(cwd: str, repo: str, issue_number: int, text: str) -> dict:
    repo_name = repo.strip()
    token = str(_repo_config(cwd, repo_name).get("token", "")).strip()
    if not token:
        return {"ok": False, "repo": repo_name, "issue": int(issue_number), "reason": "token_required"}
    body = str(text).strip()
    if not body:
        return {"ok": False, "repo": repo_name, "issue": int(issue_number), "reason": "empty_reply"}
    status_code, payload = _api_post(
        f"https://api.github.com/repos/{repo_name}/issues/{int(issue_number)}/comments",
        {"body": body},
        token,
    )
    if status_code not in {200, 201} or not isinstance(payload, dict):
        return {"ok": False, "repo": repo_name, "issue": int(issue_number), "status": status_code, "error": payload}
    return {
        "ok": True,
        "repo": repo_name,
        "issue": int(issue_number),
        "comment": {
            "id": int(payload.get("id", 0)),
            "url": str(payload.get("html_url", "")),
            "created_at": str(payload.get("created_at", "")),
            "body": str(payload.get("body", "")),
        },
        "mode": "posted",
    }


def pr_reply_post(cwd: str, repo: str, pr_number: int, text: str) -> dict:
    posted = issue_reply_post(cwd, repo, pr_number, text)
    if not posted.get("ok", False):
        return {"ok": False, "repo": repo, "pull_request": int(pr_number), **{k: v for k, v in posted.items() if k not in {"issue", "repo"}}}
    return {
        "ok": True,
        "repo": repo,
        "pull_request": int(pr_number),
        "comment": posted.get("comment", {}),
        "mode": "posted",
    }

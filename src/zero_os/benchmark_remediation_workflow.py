from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.approval_workflow import decide as approval_decide, latest_approved, request_approval, status as approval_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workflow_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "benchmark_remediation_workflow.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_workflow_state(cwd: str) -> dict[str, Any]:
    path = _workflow_path(cwd)
    if not path.exists():
        return {
            "schema_version": 1,
            "updated_utc": "",
            "latest": {},
            "execution_history": [],
            "executed_approval_ids": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("schema_version", 1)
    payload.setdefault("updated_utc", "")
    payload.setdefault("latest", {})
    payload.setdefault("execution_history", [])
    payload.setdefault("executed_approval_ids", [])
    return payload


def _save_workflow_state(cwd: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload["updated_utc"] = _utc_now()
    _workflow_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _benchmark_history_api():
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    from ai_from_scratch.benchmark_history import benchmark_remediation_status

    return benchmark_remediation_status


def _pending_or_latest_approval(cwd: str) -> dict[str, Any]:
    approvals = approval_status(cwd)
    pending = None
    approved = None
    for item in reversed(list(approvals.get("items", []))):
        if str(item.get("action", "")) != "benchmark_remediation_execute":
            continue
        if pending is None and str(item.get("state", "")) == "pending":
            pending = item
        if approved is None and str(item.get("state", "")) == "approved":
            approved = item
        if pending is not None and approved is not None:
            break
    return {
        "pending": pending or {},
        "approved": approved or {},
        "approval_count": sum(1 for item in approvals.get("items", []) if str(item.get("action", "")) == "benchmark_remediation_execute"),
    }


def _latest_pending_approval(cwd: str) -> dict[str, Any]:
    approvals = approval_status(cwd)
    for item in reversed(list(approvals.get("items", []))):
        if str(item.get("action", "")) != "benchmark_remediation_execute":
            continue
        if str(item.get("state", "")) == "pending":
            return {"ok": True, "approval": item}
    return {"ok": False, "reason": "no_pending_approval"}


def _augment_status(cwd: str, remediation: dict[str, Any]) -> dict[str, Any]:
    state = _load_workflow_state(cwd)
    approvals = _pending_or_latest_approval(cwd)
    pending = dict(approvals.get("pending") or {})
    approved = dict(approvals.get("approved") or {})
    executed_ids = {str(item) for item in state.get("executed_approval_ids", [])}
    approved_ready = bool(approved) and str(approved.get("id", "")) not in executed_ids
    latest_execution = dict(state.get("latest") or {})
    payload = {
        **remediation,
        "approval": {
            "pending": pending,
            "approved": approved,
            "approved_ready": approved_ready,
            "approval_count": int(approvals.get("approval_count", 0)),
        },
        "execution": {
            "latest": latest_execution,
            "history_count": len(list(state.get("execution_history", []))),
            "executed_approval_count": len(executed_ids),
        },
        "workflow_path": str(_workflow_path(cwd).resolve()),
    }
    return payload


def status(cwd: str, *, write: bool = False) -> dict[str, Any]:
    benchmark_remediation_status = _benchmark_history_api()
    remediation = benchmark_remediation_status(
        history_dir=Path(cwd).resolve() / ".zero_os" / "benchmarks" / "model",
        write=write,
    )
    payload = _augment_status(cwd, remediation)
    if write:
        state = _load_workflow_state(cwd)
        state["latest_status"] = payload
        _save_workflow_state(cwd, state)
    return payload


def request(cwd: str) -> dict[str, Any]:
    current = status(cwd, write=True)
    if bool(current.get("missing", False)):
        return {"ok": False, "reason": "missing_history", "status": current}
    if str(current.get("status", "")) != "proposed":
        return {"ok": False, "reason": "no_proposal", "status": current}

    pending = dict(dict(current.get("approval", {})).get("pending") or {})
    if pending:
        return {"ok": True, "requested": False, "reason": "pending_exists", "approval": pending, "status": current}

    approval = request_approval(
        cwd,
        "benchmark_remediation_execute",
        f"Execute benchmark remediation candidate for {current.get('latest_run_label', 'benchmark')}",
        payload={
            "remediation": current,
            "proposal": dict(current.get("proposal") or {}),
            "latest_run_label": str(current.get("latest_run_label", "")),
            "cohort": str(current.get("cohort", "")),
        },
    )
    updated = status(cwd, write=True)
    return {"ok": True, "requested": True, "approval": approval.get("approval", {}), "status": updated}


def decide(cwd: str, approve: bool) -> dict[str, Any]:
    pending = _latest_pending_approval(cwd)
    if not pending.get("ok", False):
        return {"ok": False, "reason": "no_pending_approval", "status": status(cwd, write=True)}
    approval = dict(pending.get("approval") or {})
    decided = approval_decide(cwd, str(approval.get("id", "")), approve)
    return {
        "ok": bool(decided.get("ok", False)),
        "approval": decided.get("approval", {}),
        "status": status(cwd, write=True),
    }


def execute(cwd: str) -> dict[str, Any]:
    current = status(cwd, write=True)
    approved_info = latest_approved(cwd, action="benchmark_remediation_execute")
    if not approved_info.get("ok", False):
        return {"ok": False, "reason": "approval_required", "status": current}
    approval = dict(approved_info.get("approval") or {})

    state = _load_workflow_state(cwd)
    executed_ids = {str(item) for item in state.get("executed_approval_ids", [])}
    approval_id = str(approval.get("id", "")).strip()
    if approval_id in executed_ids:
        return {"ok": False, "reason": "approval_already_used", "approval": approval, "status": current}

    approval_payload = dict(approval.get("payload") or {})
    approved_run_label = str(approval_payload.get("latest_run_label", "")).strip()
    approved_cohort = str(approval_payload.get("cohort", "")).strip()
    if approved_run_label and approved_run_label != str(current.get("latest_run_label", "")).strip():
        return {"ok": False, "reason": "stale_approval_run_label", "approval": approval, "status": current}
    if approved_cohort and approved_cohort != str(current.get("cohort", "")).strip():
        return {"ok": False, "reason": "stale_approval_cohort", "approval": approval, "status": current}

    proposal = dict(approval_payload.get("proposal") or current.get("proposal") or {})
    train_argv = list(proposal.get("train_argv") or [])
    benchmark_argv = list(proposal.get("benchmark_argv") or [])
    if not train_argv or not benchmark_argv:
        return {"ok": False, "reason": "missing_commands", "approval": approval, "status": current}

    started_utc = _utc_now()
    train_run = subprocess.run(train_argv, cwd=str(Path(cwd).resolve()), capture_output=True, text=True, check=False)
    if train_run.returncode != 0:
        execution = {
            "approval_id": approval_id,
            "started_utc": started_utc,
            "finished_utc": _utc_now(),
            "ok": False,
            "stage": "train",
            "train_returncode": int(train_run.returncode),
            "train_stdout_tail": train_run.stdout[-4000:],
            "train_stderr_tail": train_run.stderr[-4000:],
            "proposal": proposal,
        }
        state["latest"] = execution
        history = list(state.get("execution_history", []))
        history.append(execution)
        state["execution_history"] = history[-12:]
        _save_workflow_state(cwd, state)
        return {"ok": False, "reason": "train_failed", "execution": execution, "approval": approval, "status": status(cwd, write=True)}

    benchmark_run = subprocess.run(benchmark_argv, cwd=str(Path(cwd).resolve()), capture_output=True, text=True, check=False)
    execution = {
        "approval_id": approval_id,
        "started_utc": started_utc,
        "finished_utc": _utc_now(),
        "ok": benchmark_run.returncode == 0,
        "stage": "benchmark",
        "train_returncode": int(train_run.returncode),
        "benchmark_returncode": int(benchmark_run.returncode),
        "train_stdout_tail": train_run.stdout[-2000:],
        "train_stderr_tail": train_run.stderr[-2000:],
        "benchmark_stdout_tail": benchmark_run.stdout[-4000:],
        "benchmark_stderr_tail": benchmark_run.stderr[-4000:],
        "proposal": proposal,
    }
    history = list(state.get("execution_history", []))
    history.append(execution)
    state["latest"] = execution
    state["execution_history"] = history[-12:]
    if execution["ok"]:
        used = list(state.get("executed_approval_ids", []))
        used.append(approval_id)
        state["executed_approval_ids"] = used[-40:]
    _save_workflow_state(cwd, state)
    return {
        "ok": bool(execution["ok"]),
        "approval": approval,
        "execution": execution,
        "status": status(cwd, write=True),
    }

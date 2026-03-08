from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "runtime_economy.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "actors": {},
        "ledger": [],
        "balances": {},
        "reward_policy": {
            "compute_credit_per_unit": 1.0,
            "bandwidth_credit_per_unit": 0.5,
            "optimization_credit_per_unit": 2.0,
        },
    }


def _load(cwd: str) -> dict:
    p = _state_path(cwd)
    if not p.exists():
        d = _default_state()
        _save(cwd, d)
        return d
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        d = _default_state()
        _save(cwd, d)
        return d


def _save(cwd: str, state: dict) -> None:
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _credit(s: dict, actor_id: str, amount: float, reason: str) -> dict:
    s["balances"][actor_id] = float(s["balances"].get(actor_id, 0.0)) + float(amount)
    rec = {"id": str(uuid.uuid4())[:12], "time_utc": _utc_now(), "actor_id": actor_id, "amount": float(amount), "reason": reason}
    s["ledger"].append(rec)
    s["ledger"] = s["ledger"][-5000:]
    return rec


def status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "actors": len(s["actors"]), "ledger_entries": len(s["ledger"]), "balances": s["balances"], "reward_policy": s["reward_policy"]}


def actor_register(cwd: str, role: str, name: str) -> dict:
    s = _load(cwd)
    r = role.strip().lower()
    if r not in {"developer", "runtime_node_operator", "storage_node", "optimization_node"}:
        return {"ok": False, "reason": "invalid role"}
    aid = str(uuid.uuid4())[:12]
    s["actors"][aid] = {"role": r, "name": name.strip(), "registered_utc": _utc_now()}
    s["balances"][aid] = 0.0
    _save(cwd, s)
    return {"ok": True, "actor_id": aid, "actor": s["actors"][aid]}


def contribution_record(cwd: str, actor_id: str, kind: str, units: float) -> dict:
    s = _load(cwd)
    if actor_id not in s["actors"]:
        return {"ok": False, "reason": "actor not found"}
    k = kind.strip().lower()
    u = float(units)
    if u <= 0:
        return {"ok": False, "reason": "units must be >0"}
    pol = s["reward_policy"]
    if k == "compute":
        amount = u * float(pol["compute_credit_per_unit"])
    elif k == "bandwidth":
        amount = u * float(pol["bandwidth_credit_per_unit"])
    elif k == "optimization":
        amount = u * float(pol["optimization_credit_per_unit"])
    else:
        return {"ok": False, "reason": "kind must be compute|bandwidth|optimization"}
    rec = _credit(s, actor_id, amount, f"contribution:{k}:{u}")
    _save(cwd, s)
    return {"ok": True, "entry": rec, "balance": s["balances"][actor_id]}


def payout(cwd: str, actor_id: str, amount: float) -> dict:
    s = _load(cwd)
    if actor_id not in s["actors"]:
        return {"ok": False, "reason": "actor not found"}
    amt = float(amount)
    bal = float(s["balances"].get(actor_id, 0.0))
    if amt <= 0 or amt > bal:
        return {"ok": False, "reason": "invalid amount"}
    rec = _credit(s, actor_id, -amt, "payout")
    _save(cwd, s)
    return {"ok": True, "entry": rec, "balance": s["balances"][actor_id]}

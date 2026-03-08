from __future__ import annotations

from datetime import datetime, timezone

from zero_os.brain_awareness import build_brain_awareness
from zero_os.harmony import zero_ai_harmony_status
from zero_os.knowledge_map import build_knowledge_index, knowledge_status
from zero_os.maturity import maturity_scaffold_all, maturity_status
from zero_os.recovery import zero_ai_backup_create, zero_ai_backup_status
from zero_os.security_hardening import zero_ai_security_apply, zero_ai_security_status
from zero_os.consciousness_core import consciousness_tick, consciousness_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def zero_ai_sync_all(cwd: str) -> dict:
    mat = maturity_scaffold_all(cwd)
    sec = zero_ai_security_apply(cwd)
    backup = zero_ai_backup_create(cwd)
    kbuild = build_knowledge_index(cwd, max_files=50000)
    conscious = consciousness_tick(cwd, prompt="zero ai fix all synchronization")
    harmony = zero_ai_harmony_status(cwd, autocorrect=True)
    brain = build_brain_awareness(cwd)
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "actions": {
            "maturity_scaffold": mat,
            "security_apply": sec,
            "backup_create": backup,
            "knowledge_build": kbuild,
            "consciousness_tick": conscious,
            "harmony": harmony,
            "brain_awareness": brain,
        },
        "status": {
            "maturity": maturity_status(cwd),
            "security": zero_ai_security_status(cwd),
            "backup": zero_ai_backup_status(cwd),
            "knowledge": knowledge_status(cwd),
            "consciousness": consciousness_status(cwd),
            "harmony": zero_ai_harmony_status(cwd, autocorrect=False),
        },
    }

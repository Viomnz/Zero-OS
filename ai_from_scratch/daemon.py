from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from src/ for monitor integration.
BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model import TinyBigramModel
from agent_guard import check_health, quarantine_compromise, restore_compromised
from boundary_scope import evaluate_scope
from english_dictionary import pure_logic_dictionary_step
from english_understanding import human_response_from_understanding, understand_english
from boot_initialization import run_boot_initialization
from communication_interface import goal_alignment, receive_input
from execution_layer import execute_decision
from calibration_layer import run_calibration
from context_awareness import detect_context
from degradation_detection import run_degradation_detection
from distributed_intelligence import run_distributed_reasoning
from internal_zero_reasoner import run_internal_reasoning, set_reasoner_mode, set_reasoner_profile
from knowledge_integration import integrate_knowledge
from learning_feedback import apply_learning_feedback
from meta_reasoning import run_meta_reasoning
from outcome_observation_layer import observe_outcome
from priority_arbitration import arbitrate_priority
from safe_state_layer import evaluate_safe_state
from security_integrity_layer import security_integrity_check
from security_core import assess_security, record_event
from shutdown_recovery import prepare_shutdown_recovery
from traceability_layer import log_decision_trace
from zero_os.cure_firewall import audit_status
from zero_os.production_core import auto_merge_queue_run, ai_files_smart_tick, auto_optimize_tick
from scan import run_scan
from universe_laws_guard import check_universe_laws


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _monitor_and_backup(base: Path, runtime: Path) -> None:
    monitor_file = runtime / "zero_ai_monitor.json"
    backup_root = base / ".zero_os" / "backup" / "latest"
    backup_root.mkdir(parents=True, exist_ok=True)

    beacons_dir = base / ".zero_os" / "beacons"
    beacon_count = len(list(beacons_dir.glob("*.json"))) if beacons_dir.exists() else 0
    audit = audit_status(str(base))
    _write_json(
        monitor_file,
        {
            "time_utc": _utc_now(),
            "beacon_count": beacon_count,
            "audit_status": audit,
            "mode": "assistant+monitor+backup",
        },
    )

    targets = [
        runtime / "zero_ai_heartbeat.json",
        runtime / "zero_ai_output.txt",
        runtime / "zero_ai_tasks.txt",
        runtime / "zero_ai_scan_report.json",
        monitor_file,
        base / "laws" / "profile.json",
        base / "laws" / "recursion_law.txt",
    ]
    for src in targets:
        if src.exists() and src.is_file():
            shutil.copy2(src, backup_root / src.name)


def main() -> None:
    base = Path.cwd()
    runtime = _runtime_dir(base)
    heartbeat = runtime / "zero_ai_heartbeat.json"
    pidfile = runtime / "zero_ai.pid"
    inbox = runtime / "zero_ai_tasks.txt"
    outbox = runtime / "zero_ai_output.txt"
    stopfile = runtime / "zero_ai.stop"
    ckpt = base / "ai_from_scratch" / "checkpoint.json"

    pidfile.write_text(str(os.getpid()), encoding="utf-8")
    if not inbox.exists():
        inbox.write_text("", encoding="utf-8")

    model = TinyBigramModel.load(str(ckpt)) if ckpt.exists() else None
    boot = run_boot_initialization(str(base))
    processed_lines = len(inbox.read_text(encoding="utf-8", errors="replace").splitlines())
    next_monitor = 0.0
    final_status = "stopped"
    final_reason = ""

    while True:
        if stopfile.exists():
            stopfile.unlink(missing_ok=True)
            final_status = "stopped"
            final_reason = "manual_stop"
            break

        if model is None and ckpt.exists():
            model = TinyBigramModel.load(str(ckpt))

        _write_json(
            heartbeat,
            {
                "status": "running" if boot.get("ok", False) else "safe_mode",
                "pid": os.getpid(),
                "time_utc": _utc_now(),
                "checkpoint_loaded": model is not None,
                "boot_ok": bool(boot.get("ok", False)),
                "boot_report": str(runtime / "boot_initialization.json"),
                "inbox": str(inbox),
                "outbox": str(outbox),
                "monitor": str(runtime / "zero_ai_monitor.json"),
                "backup": str(base / ".zero_os" / "backup" / "latest"),
            },
        )

        now_ts = time.time()
        if now_ts >= next_monitor:
            _monitor_and_backup(base, runtime)
            sec = assess_security(base, processed_lines)
            if sec.get("alerts"):
                record_event(base, "WARN", "security_alerts", {"alerts": sec["alerts"]})
            if not sec.get("healthy", True):
                record_event(base, "CRITICAL", "security_containment", sec)
                with outbox.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc_now()}] [SECURITY_CONTAINMENT]\n")
                    handle.write(json.dumps(sec, indent=2) + "\n\n")
                final_status = "contained"
                final_reason = "security policy violation"
                break

            auto_opt = auto_optimize_tick(str(base))
            if auto_opt.get("ran"):
                with outbox.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc_now()}] [AUTO_OPTIMIZE]\n")
                    handle.write(json.dumps(auto_opt, indent=2) + "\n\n")
            auto_merge = auto_merge_queue_run(str(base))
            if auto_merge.get("ran") and int(auto_merge.get("merged_count", 0)) > 0:
                with outbox.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc_now()}] [AUTO_MERGE]\n")
                    handle.write(json.dumps(auto_merge, indent=2) + "\n\n")
            ai_files = ai_files_smart_tick(str(base))
            if ai_files.get("ran"):
                with outbox.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc_now()}] [AI_FILES_SMART]\n")
                    handle.write(json.dumps(ai_files, indent=2) + "\n\n")

            health = check_health(base)
            if not health.get("healthy", False):
                record_event(base, "CRITICAL", "integrity_compromised", health)
                quarantine = quarantine_compromise(base, health)
                with outbox.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc_now()}] [AGENT_COMPROMISED]\n")
                    handle.write(json.dumps(health, indent=2) + "\n\n")
                    handle.write(f"[{_utc_now()}] [QUARANTINE]\n")
                    handle.write(json.dumps(quarantine, indent=2) + "\n\n")
                _write_json(
                    heartbeat,
                    {
                        "status": "compromised",
                        "pid": os.getpid(),
                        "time_utc": _utc_now(),
                        "reason": "integrity check failed",
                        "health_report": str(runtime / "agent_health.json"),
                        "quarantine_manifest": quarantine["manifest"],
                        "quarantine_dir": quarantine["quarantine_dir"],
                    },
                )
                restore = restore_compromised(base, health)
                post_restore = check_health(base)
                if post_restore.get("healthy", False):
                    cmd = ["python", str(base / "ai_from_scratch" / "daemon.py")]
                    subprocess.Popen(
                        cmd,
                        cwd=str(base),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    with outbox.open("a", encoding="utf-8") as handle:
                        handle.write(f"[{_utc_now()}] [AGENT_REPLACED]\n")
                        handle.write(json.dumps(restore, indent=2) + "\n\n")
                    final_status = "replaced"
                    final_reason = "integrity failed, restored from trusted baseline and spawned replacement"
                else:
                    with outbox.open("a", encoding="utf-8") as handle:
                        handle.write(f"[{_utc_now()}] [AGENT_ELIMINATED]\n")
                        handle.write(json.dumps(restore, indent=2) + "\n")
                        handle.write(json.dumps(post_restore, indent=2) + "\n\n")
                    final_status = "eliminated"
                    final_reason = "integrity failed, restore failed, agent terminated"
                break
            next_monitor = now_ts + 10.0

        lines = inbox.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > processed_lines and model is not None:
            new_lines = lines[processed_lines:]
            for raw in new_lines:
                packet = receive_input(raw)
                prompt = packet.content
                if not prompt:
                    continue
                with outbox.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc_now()}] [BOOT_INITIALIZATION]\n")
                    handle.write(json.dumps(boot, indent=2) + "\n")
                    if not boot.get("ok", False):
                        handle.write("[SAFE_MODE_STARTUP_BLOCK]\n")
                        handle.write("startup checks failed; execution paused until restart with valid state\n\n")
                        time.sleep(2)
                        continue
                    handle.write(f"[{_utc_now()}] prompt={prompt}\n")
                    scope = evaluate_scope(str(base), prompt, packet.channel)
                    handle.write("[BOUNDARY_SCOPE]\n")
                    handle.write(json.dumps(scope, indent=2) + "\n")
                    if not scope.get("inside_scope", False):
                        decision = str(scope.get("decision", "reject"))
                        if decision == "defer":
                            handle.write("[DEFERRED_BY_SCOPE]\n")
                            handle.write("outside active scope; requires external handling\n\n")
                        else:
                            handle.write("[REJECTED_BY_SCOPE]\n")
                            handle.write("outside allowed scope\n\n")
                        continue
                    sec_gate = security_integrity_check(base, prompt, packet.channel)
                    handle.write("[SECURITY_INTEGRITY]\n")
                    handle.write(json.dumps(sec_gate, indent=2) + "\n")
                    if not sec_gate.get("ok", False):
                        handle.write("[REJECTED_BY_SECURITY_INTEGRITY]\n")
                        handle.write(json.dumps(sec_gate, indent=2) + "\n\n")
                        continue
                    calibration = run_calibration(str(base))
                    profile_target = calibration.get("actions", {}).get("set_profile")
                    mode_target = calibration.get("actions", {}).get("set_mode")
                    if profile_target:
                        set_reasoner_profile(str(base), profile_target)
                    if mode_target:
                        set_reasoner_mode(str(base), mode_target)
                    handle.write("[CALIBRATION]\n")
                    handle.write(json.dumps(calibration, indent=2) + "\n")
                    degradation = run_degradation_detection(str(base))
                    d_profile = degradation.get("actions", {}).get("set_profile")
                    d_mode = degradation.get("actions", {}).get("set_mode")
                    if d_profile:
                        set_reasoner_profile(str(base), d_profile)
                    if d_mode:
                        set_reasoner_mode(str(base), d_mode)
                    handle.write("[DEGRADATION_DETECTION]\n")
                    handle.write(json.dumps(degradation, indent=2) + "\n")
                    goal = goal_alignment(packet)
                    handle.write("[COMM_INTERFACE_IN]\n")
                    handle.write(
                        json.dumps(
                            {
                                "channel": packet.channel,
                                "safe": packet.safe,
                                "reason": packet.reason,
                                "goal_alignment": goal,
                            },
                            indent=2,
                        )
                        + "\n"
                    )
                    if not goal.get("pass", False):
                        handle.write("[REJECTED_BY_INTERFACE]\n")
                        handle.write(goal.get("reason", "blocked") + "\n\n")
                        continue
                    context = detect_context(str(base), prompt, packet.channel)
                    handle.write("[CONTEXT_AWARENESS]\n")
                    handle.write(json.dumps(context, indent=2) + "\n")
                    ctx_params = context.get("reasoning_parameters", {})
                    if ctx_params.get("force_profile"):
                        set_reasoner_profile(str(base), str(ctx_params["force_profile"]))
                    if ctx_params.get("force_mode"):
                        set_reasoner_mode(str(base), str(ctx_params["force_mode"]))
                    knowledge = integrate_knowledge(str(base), prompt, packet.channel)
                    integrated_prompt = str(knowledge.get("unified_model", {}).get("unified_text", prompt)).strip() or prompt
                    handle.write("[KNOWLEDGE_INTEGRATION]\n")
                    handle.write(json.dumps(knowledge, indent=2) + "\n")
                    if prompt.lower().startswith("scan"):
                        report = run_scan(base)
                        status = "[SCAN_PASS]" if report["syntax_error_count"] == 0 and report["tests_passed"] else "[SCAN_FAIL]"
                        handle.write(status + "\n")
                        handle.write(
                            f"syntax_error_count={report['syntax_error_count']}\n"
                            f"tests_passed={report['tests_passed']}\n"
                            "report=.zero_os/runtime/zero_ai_scan_report.json\n\n"
                        )
                    else:
                        d = pure_logic_dictionary_step(str(base), prompt)
                        if d.get("mode") in {"lookup", "auto_add"} or prompt.lower().startswith("define "):
                            handle.write("[ENGLISH_DICTIONARY]\n")
                            handle.write(json.dumps(d, indent=2) + "\n\n")
                            continue
                        understanding = understand_english(integrated_prompt)
                        handle.write("[ENGLISH_UNDERSTANDING]\n")
                        handle.write(json.dumps(understanding, indent=2) + "\n")
                        primary = human_response_from_understanding(understanding, integrated_prompt)
                        candidates = [primary]
                        max_candidates = int(ctx_params.get("max_candidates", 9))
                        for i in range(1, max_candidates + 1):
                            candidates.append(model.sample(integrated_prompt, length=180, temperature=1.0, seed=100 + i))
                        meta = run_meta_reasoning(str(base), integrated_prompt, candidates)
                        handle.write("[META_REASONING]\n")
                        handle.write(json.dumps(meta, indent=2) + "\n")
                        ranked = meta.get("ranked", [])
                        if ranked:
                            ordered = [r.get("candidate", "") for r in ranked if r.get("candidate")]
                            if ordered:
                                candidates = ordered
                        if meta.get("strategy") == "compressed_path":
                            candidates = candidates[:6]

                        distributed = run_distributed_reasoning(
                            str(base),
                            integrated_prompt,
                            candidates,
                            node_count=3,
                            agreement_threshold=0.67,
                        )
                        gate = distributed.selected_gate
                        handle.write("[DISTRIBUTED_INTELLIGENCE]\n")
                        handle.write(json.dumps(distributed.report, indent=2) + "\n")
                        arbitration = arbitrate_priority(str(base), integrated_prompt, candidates, context)
                        handle.write("[PRIORITY_ARBITRATION]\n")
                        handle.write(json.dumps(arbitration, indent=2) + "\n")
                        final_output = str(arbitration.get("winner", "")).strip() if arbitration.get("ok") else gate.output
                        if not final_output:
                            final_output = gate.output
                        safe_state = evaluate_safe_state(str(base), gate, degradation, calibration)
                        handle.write("[ZERO_AI_INTERNAL]\n")
                        handle.write(
                            json.dumps(
                                {
                                    "execute": gate.accepted,
                                    "attempts": gate.attempts,
                                    "model_generation": gate.model_generation,
                                    "fallback_mode": gate.fallback_mode,
                                    "memory_update": gate.memory_update,
                                    "exploration_used": gate.exploration_used,
                                    "self_monitor": gate.self_monitor,
                                    "checks": gate.critics,
                                },
                                indent=2,
                            )
                            + "\n"
                        )
                        handle.write("[SAFE_STATE]\n")
                        handle.write(json.dumps(safe_state, indent=2) + "\n")
                        trace_result = log_decision_trace(
                            str(base),
                            {
                                "input": {"prompt": prompt, "channel": packet.channel},
                                "context": context,
                                "knowledge": knowledge.get("unified_model", {}),
                                "meta_reasoning": {
                                    "strategy": meta.get("strategy"),
                                    "reasoning_analysis": meta.get("reasoning_analysis", {}),
                                    "error_patterns": meta.get("error_patterns", []),
                                },
                                "distributed": distributed.report,
                                "priority_arbitration": arbitration,
                                "signals": gate.critics,
                                "consensus": {
                                    "accepted": gate.accepted,
                                    "fallback_mode": gate.fallback_mode,
                                    "attempts": gate.attempts,
                                    "model_generation": gate.model_generation,
                                },
                                "safe_state": safe_state,
                                "final_action": {
                                    "selected_output": final_output,
                                    "execute": bool(gate.accepted and not safe_state.get("enter_safe_state", False)),
                                },
                            },
                        )
                        handle.write("[TRACEABILITY]\n")
                        handle.write(json.dumps(trace_result, indent=2) + "\n")
                        if safe_state.get("enter_safe_state", False):
                            predicted = {
                                "expected_success": False,
                                "prediction_score": float(arbitration.get("winner_score", 0.0)),
                            }
                            observed = {
                                "actual_success": False,
                                "efficiency_score": 0.0,
                                "signal_reliability": float(gate.self_monitor.get("avg_confidence_recent", 0.0)),
                            }
                            feedback = apply_learning_feedback(str(base), prompt, predicted, observed, context)
                            handle.write("[LEARNING_FEEDBACK]\n")
                            handle.write(json.dumps(feedback, indent=2) + "\n")
                            handle.write("[ENTERED_SAFE_STATE]\n")
                            handle.write(f"action={safe_state.get('action', 'pause_execution')}\n\n")
                            continue
                        if gate.accepted:
                            chk = check_universe_laws(final_output)
                            handle.write(("[UNIVERSE_LAWS_PASS]\n" if chk.passed else "[UNIVERSE_LAWS_BLOCKED]\n"))
                            execution = execute_decision(
                                str(base),
                                final_output,
                                packet.channel,
                                context,
                                resources={"decision": "approve"},
                                stability={"stable": True},
                            )
                            handle.write("[EXECUTION_LAYER]\n")
                            handle.write(json.dumps(execution, indent=2) + "\n")
                            outbound = execution.get("dispatch", {"allowed": False, "safe_output": "", "reason": "no dispatch"})
                            handle.write("[COMM_INTERFACE_OUT]\n")
                            handle.write(json.dumps(outbound, indent=2) + "\n")
                            handle.write(str(outbound.get("safe_output", "")) + "\n\n")
                            outcome = observe_outcome(str(base), prompt, execution, gate, context)
                            handle.write("[OUTCOME_OBSERVATION]\n")
                            handle.write(json.dumps(outcome, indent=2) + "\n")
                            predicted = {
                                "expected_success": bool(gate.accepted),
                                "prediction_score": float(arbitration.get("winner_score", 0.0)),
                            }
                            observed = dict(outcome.get("observed", {}))
                            observed["actual_success"] = bool(chk.passed and observed.get("actual_success", False))
                            feedback = apply_learning_feedback(str(base), prompt, predicted, observed, context)
                            handle.write("[LEARNING_FEEDBACK]\n")
                            handle.write(json.dumps(feedback, indent=2) + "\n")
                        else:
                            handle.write("[REJECTED_BY_ZERO_AI_INTERNAL]\n")
                            handle.write(gate.output + "\n\n")
                            predicted = {
                                "expected_success": False,
                                "prediction_score": float(arbitration.get("winner_score", 0.0)),
                            }
                            observed = {
                                "actual_success": False,
                                "efficiency_score": 0.0,
                                "signal_reliability": float(gate.self_monitor.get("avg_confidence_recent", 0.0)),
                            }
                            feedback = apply_learning_feedback(str(base), prompt, predicted, observed, context)
                            handle.write("[LEARNING_FEEDBACK]\n")
                            handle.write(json.dumps(feedback, indent=2) + "\n")
            processed_lines = len(lines)
        elif len(lines) < processed_lines:
            processed_lines = len(lines)

        time.sleep(2)

    _write_json(
        heartbeat,
        {
            "status": final_status,
            "pid": os.getpid(),
            "time_utc": _utc_now(),
            "reason": final_reason,
        },
    )
    recovery = prepare_shutdown_recovery(
        str(base),
        trigger=final_status,
        reason=final_reason,
        queue_size=processed_lines,
        checkpoint_loaded=(model is not None),
    )
    with outbox.open("a", encoding="utf-8") as handle:
        handle.write(f"[{_utc_now()}] [SHUTDOWN_RECOVERY]\n")
        handle.write(json.dumps(recovery, indent=2) + "\n\n")
    pidfile.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

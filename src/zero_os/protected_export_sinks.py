from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from zero_os.containment_sink_enforcement import evaluate_sensitive_sink
from zero_os.live_containment_state import LiveContainmentRegistry


@dataclass(frozen=True)
class ExportSinkResult:
    ok: bool
    status: str
    channel: str
    destination: str
    containment_revision: int
    actuator_invoked: bool
    authority_granted: bool = False
    path_logic_final_authority: bool = False


def execute_protected_export(
    *,
    containment: LiveContainmentRegistry,
    process_identity: str,
    channel: str,
    destination: str,
    payload: bytes,
    authorization_verified: bool,
    actuator: Callable[[str, bytes], object],
    expected_containment_revision: int | None = None,
) -> ExportSinkResult:
    """Invoke an export actuator only after a final live-containment recheck.

    `authorization_verified` represents the independent protected-data grant and
    channel/destination authorization. This function cannot create that authority.
    """
    normalized = str(channel or "").strip().lower()
    operation = {
        "network": "network_export",
        "clipboard": "clipboard_export",
        "ipc": "ipc_export",
        "removable": "removable_export",
        "local_file": "protected_export",
    }.get(normalized)
    if operation is None:
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_UNSUPPORTED_CHANNEL", normalized, destination, -1, False)
    if not authorization_verified:
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_AUTHORITY_MISSING", normalized, destination, -1, False)

    before = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation=operation,
        expected_revision=expected_containment_revision,
    )
    if not before.allowed:
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_CONTAINMENT", normalized, destination, before.containment_revision, False)

    # Re-read immediately before the side effect to close the authorization /
    # execution race. The actuator is the first irreversible boundary here.
    final = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation=operation,
        expected_revision=before.containment_revision,
    )
    if not final.allowed:
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_CONTAINMENT_CHANGED", normalized, destination, final.containment_revision, False)

    actuator(str(destination), bytes(payload))
    return ExportSinkResult(True, "EXPORT_SINK_EXECUTED_IN_SCOPE", normalized, destination, final.containment_revision, True)


def export_sink_invariants() -> dict:
    return {
        "authorization_and_containment_are_separate": True,
        "live_containment_rechecked_before_actuator": True,
        "contested_process_cannot_invoke_export_actuator": True,
        "export_sink_cannot_mint_authority": True,
        "path_logic_final_authority": False,
    }

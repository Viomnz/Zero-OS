from __future__ import annotations

from dataclasses import dataclass

from zero_os.decoy_beacon import DecoyBeacon, DecoyTouch, DecoyVerdict, evaluate_decoy_touch


@dataclass(frozen=True)
class DecoyResponse:
    status: str
    preserve_forensics: bool
    contest_process_authority: bool
    revoke_protected_data_export: bool
    increase_monitoring: bool
    quarantine_eligible: bool
    require_investigation: bool
    final_malicious_judgment: bool = False
    authority_granted: bool = False


def respond_to_decoy_touch(beacon: DecoyBeacon, touch: DecoyTouch) -> tuple[DecoyVerdict, DecoyResponse]:
    verdict = evaluate_decoy_touch(beacon, touch)
    if not verdict.suspicious:
        return verdict, DecoyResponse(
            status="NO_DEFENSIVE_ESCALATION",
            preserve_forensics=False,
            contest_process_authority=False,
            revoke_protected_data_export=False,
            increase_monitoring=False,
            quarantine_eligible=False,
            require_investigation=bool(verdict.reasons),
        )
    return verdict, DecoyResponse(
        status="DECOY_CONTRADICTION_RESPONSE",
        preserve_forensics=True,
        contest_process_authority=True,
        revoke_protected_data_export=True,
        increase_monitoring=True,
        quarantine_eligible=verdict.quarantine_eligible,
        require_investigation=True,
        final_malicious_judgment=False,
        authority_granted=False,
    )

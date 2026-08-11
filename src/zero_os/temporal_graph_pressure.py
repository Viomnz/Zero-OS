from __future__ import annotations

from zero_os.temporal_authority import TemporalAuthoritySubject, evaluate_temporal_authority


def run_temporal_pressure() -> dict:
    cases: dict[str, bool] = {}

    fresh = TemporalAuthoritySubject("edge:A-B", "r1", 10.0, 20.0, 5.0, 2, "edge:prev", 14.0)
    cases["fresh_sequence_survives"] = evaluate_temporal_authority(fresh, now=16.0, predecessor_id="edge:prev").eligible_to_continue_authority_evaluation

    stale = TemporalAuthoritySubject("edge:A-B", "r1", 10.0, 30.0, 3.0, 2, "", 14.0)
    cases["stale_evidence_contested"] = not evaluate_temporal_authority(stale, now=20.0).eligible_to_continue_authority_evaluation

    expired = TemporalAuthoritySubject("edge:A-B", "r1", 10.0, 12.0, 10.0, 2, "", 11.0)
    cases["expired_authority_blocks"] = not evaluate_temporal_authority(expired, now=15.0).eligible_to_continue_authority_evaluation

    wrong_order = TemporalAuthoritySubject("joint:A+B", "r3", 0.0, 100.0, 100.0, 3, "step:2", 50.0)
    cases["wrong_sequence_blocks"] = not evaluate_temporal_authority(wrong_order, now=50.0, predecessor_id="step:1").eligible_to_continue_authority_evaluation

    future = TemporalAuthoritySubject("recovery:commit", "r4", 60.0, 120.0, 10.0, 4, "", 55.0)
    cases["early_action_waits"] = not evaluate_temporal_authority(future, now=56.0).eligible_to_continue_authority_evaluation

    contradicted = TemporalAuthoritySubject("controller:relation", "r5", 0.0, 100.0, 100.0, 5, "", 40.0, ("race_detected",))
    cases["race_contradiction_contests"] = not evaluate_temporal_authority(contradicted, now=41.0).eligible_to_continue_authority_evaluation

    return {
        "cases": cases,
        "all_passed": all(cases.values()),
        "temporal_authority_is_final_authority": False,
        "path_logic_final_authority": False,
        "interpretation": "topology authority is insufficient without time, freshness, and sequence authority",
    }

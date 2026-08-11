from zero_os.temporal_authority import TemporalAuthoritySubject, TemporalState, evaluate_temporal_authority
from zero_os.temporal_graph_pressure import run_temporal_pressure


def test_temporal_pressure_suite():
    report = run_temporal_pressure()
    assert report["all_passed"] is True
    assert report["temporal_authority_is_final_authority"] is False


def test_stale_relation_does_not_keep_current_authority():
    subject = TemporalAuthoritySubject("edge:A-B", "r1", 0, 100, 2, 1, "", 10)
    decision = evaluate_temporal_authority(subject, now=20)
    assert decision.eligible_to_continue_authority_evaluation is False
    assert decision.state is TemporalState.CONTESTED


def test_sequence_mismatch_blocks_even_when_window_is_valid():
    subject = TemporalAuthoritySubject("joint:A+B", "r1", 0, 100, 100, 2, "step:1", 10)
    decision = evaluate_temporal_authority(subject, now=20, predecessor_id="step:0")
    assert decision.eligible_to_continue_authority_evaluation is False
    assert decision.state is TemporalState.BLOCK
    assert decision.final_authority_granted is False

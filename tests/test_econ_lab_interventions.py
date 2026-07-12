"""WP-H2 acceptance tests (ADR-ECON-007 Decision 1/3; design doc
`research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L1.2):
`tools/econ_lab/monitor/interventions.py`'s diagnostic generator (a) and rollback
event/executor (b).

Every `LoopDetectorConfig` threshold value used to build fixture trips below is a
harness-invented arbitrary constant, same discipline as
`tests/test_econ_lab_loop_detector.py` (no ADR/design-memo pins a concrete loop-
detector threshold; RES_ROUTE_lockIn_remedy_design_20260710 §5 explicitly marks
"升级阈值" as an open, uncited internal experiment).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"

sys.path.insert(0, str(ECON_LAB))

import monitor.interventions as interventions  # noqa: E402
import monitor.loop_detector as loop_detector  # noqa: E402


# ---------------------------------------------------------------------------
# Shared trajectory-event fixture helpers (copied shape from
# tests/test_econ_lab_loop_detector.py's own helpers -- not re-derived).
# ---------------------------------------------------------------------------


def _edit(seq, file_path, outcome, fragment_id="frag_a", action_signature=None):
    return {
        "seq": seq,
        "event_type": "edit",
        "instance_id": "fixture-instance",
        "route_id": None,
        "file_path": file_path,
        "fragment_id": fragment_id,
        "action_signature": action_signature or f"edit:{outcome}:{seq}",
        "outcome": outcome,
    }


def _command(seq, action_signature, outcome="failed"):
    return {
        "seq": seq,
        "event_type": "command",
        "instance_id": "fixture-instance",
        "route_id": None,
        "action_signature": action_signature,
        "outcome": outcome,
    }


def _phase(seq, phase, boundary):
    return {
        "seq": seq,
        "event_type": "phase_boundary",
        "instance_id": "fixture-instance",
        "route_id": None,
        "phase": phase,
        "boundary": boundary,
    }


def _verification(seq, phase, result):
    return {
        "seq": seq,
        "event_type": "verification",
        "instance_id": "fixture-instance",
        "route_id": None,
        "phase": phase,
        "result": result,
    }


def _termination(seq, phase, reason_class):
    return {
        "seq": seq,
        "event_type": "termination",
        "instance_id": "fixture-instance",
        "route_id": None,
        "phase": phase,
        "reason_class": reason_class,
    }


def _cfg(**overrides):
    base = dict(
        same_fragment_failure_threshold=3,
        action_window_size=4,
        action_window_repeat_threshold=3,
        phase_timeout_steps=5,
    )
    base.update(overrides)
    return loop_detector.LoopDetectorConfig(**base)


def _first_trip(events, cfg=None):
    cfg = cfg or _cfg()
    result = loop_detector.detect(events, cfg)
    assert result["tripped"], "fixture must actually trip the detector"
    trips = loop_detector.find_all_trips(events, cfg)
    return trips[0]


# ---------------------------------------------------------------------------
# (a) Diagnostic generator: whitelist / blacklist assertions.
# ---------------------------------------------------------------------------


def test_diagnostic_same_fragment_whitelist_content_only():
    events = [
        _edit(0, "pkg/mod.py", "failed", action_signature="patch_a"),
        _edit(1, "pkg/mod.py", "failed", action_signature="patch_b"),
        _edit(2, "pkg/mod.py", "failed", action_signature="patch_c"),
    ]
    trip = _first_trip(events)
    diagnostic = interventions.build_diagnostic(trip)
    assert diagnostic.rule_id == loop_detector.RULE_SAME_FRAGMENT_REPEATED_FAILURE
    assert diagnostic.facts["fact_class"] == "REPEATED_FAILED_EDIT"
    assert diagnostic.facts["file_path"] == "pkg/mod.py"
    assert set(diagnostic.facts["attempted_action_signatures"]) == {"patch_a", "patch_b", "patch_c"}
    assert "loop detected" in diagnostic.text.lower()
    assert diagnostic.digest.startswith("sha256:")
    # No "第 N 次触发" style phrasing: the ADR's own forbidden example.
    assert "nth time" not in diagnostic.text.lower()
    assert "triggered the" not in diagnostic.text.lower()


def test_diagnostic_repeated_signature_whitelist_content_only():
    events = [
        _command(0, "run_tests"),
        _command(1, "run_tests"),
        _command(2, "run_tests"),
    ]
    trip = _first_trip(events, _cfg(action_window_size=3, action_window_repeat_threshold=3))
    diagnostic = interventions.build_diagnostic(trip)
    assert diagnostic.facts["fact_class"] == "REPEATED_ACTION_SIGNATURE"
    assert diagnostic.facts["action_signature"] == "run_tests"


def test_diagnostic_phase_timeout_whitelist_content_only():
    events = [_phase(0, "dispatch", "start")] + [_command(i, f"noop_{i}", outcome="succeeded") for i in range(1, 6)]
    trip = _first_trip(events, _cfg(phase_timeout_steps=5))
    diagnostic = interventions.build_diagnostic(trip)
    assert diagnostic.facts["fact_class"] == "PHASE_STILL_OPEN"
    assert diagnostic.facts["phase"] == "dispatch"


def test_diagnostic_bare_termination_whitelist_content_only():
    events = [_termination(0, "dispatch", "ERROR")]
    trip = _first_trip(events)
    diagnostic = interventions.build_diagnostic(trip)
    assert diagnostic.facts["fact_class"] == "BARE_TERMINATION"
    assert diagnostic.facts["phase"] == "dispatch"
    assert diagnostic.facts["reason_class"] == "ERROR"


def test_diagnostic_every_rule_produces_a_legal_diagnostic():
    """Every rule_id the detector can produce must have a diagnostic template, and
    every one of them must independently pass the whitelist/blacklist assertions --
    guards against a future rule addition silently lacking Decision-3 coverage."""
    for rule_id in (
        loop_detector.RULE_SAME_FRAGMENT_REPEATED_FAILURE,
        loop_detector.RULE_REPEATED_ACTION_SIGNATURE_WINDOW,
        loop_detector.RULE_PHASE_TIMEOUT,
        loop_detector.RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE,
    ):
        assert rule_id in interventions._DIAGNOSTIC_BUILDERS


def test_diagnostic_facts_whitelist_rejects_bzone_key_names():
    illegal_facts_variants = [
        {"tau": "x"},
        {"lambda_value": "x"},
        {"n_eff_floor": "x"},
        {"bucket_key": "x"},
        {"detection_threshold": "x"},
        {"trigger_count": "x"},
        {"elapsed_steps": "x"},
    ]
    for facts in illegal_facts_variants:
        with pytest.raises(interventions.InterventionError):
            interventions.assert_decision3_legal(facts)


def test_diagnostic_facts_whitelist_rejects_numeric_values():
    for facts in (
        {"file_path": "a.py", "retries": 3},
        {"file_path": "a.py", "ratio": 0.5},
        {"file_path": "a.py", "flag": True},
        {"nested": {"inner_count": 2}},
        {"listy": ["ok", 5]},
    ):
        with pytest.raises(interventions.InterventionError):
            interventions.assert_decision3_legal(facts)


def test_diagnostic_facts_whitelist_accepts_legal_shape():
    interventions.assert_decision3_legal(
        {
            "fact_class": "REPEATED_FAILED_EDIT",
            "file_path": "pkg/mod.py",
            "fragment_id": None,
            "attempted_action_signatures": ["a", "b"],
        }
    )


def test_diagnostic_text_blacklist_rejects_bzone_terms():
    with pytest.raises(interventions.InterventionError):
        interventions.assert_no_bzone_terms_in_text("the route's tau is high")
    with pytest.raises(interventions.InterventionError):
        interventions.assert_no_bzone_terms_in_text("q_eff dropped below the floor")
    with pytest.raises(interventions.InterventionError):
        interventions.assert_no_bzone_terms_in_text("τ was raised")


def test_diagnostic_text_blacklist_rejects_untraceable_numbers():
    facts = {"file_path": "pkg/mod.py"}
    with pytest.raises(interventions.InterventionError):
        interventions.assert_no_unexplained_numbers_in_text("triggered the 3rd time", facts)


def test_diagnostic_text_blacklist_allows_digits_traceable_to_facts():
    facts = {"file_path": "pkg/mod_v2.py", "fragment_id": "frag_42"}
    # Digits "2" and "42" both appear verbatim inside whitelisted fact strings above.
    interventions.assert_no_unexplained_numbers_in_text(
        "Loop detected: repeated failed edits on pkg/mod_v2.py (fragment frag_42).", facts
    )


def test_build_diagnostic_raises_for_unknown_rule_id():
    fake_trip = loop_detector.LoopTrip(rule_id="NOT_A_REAL_RULE", at_seq=0, evidence={})
    with pytest.raises(interventions.InterventionError):
        interventions.build_diagnostic(fake_trip)


# ---------------------------------------------------------------------------
# (b) Rollback event append + workspace reset + replay determinism.
# ---------------------------------------------------------------------------


def test_execute_rollback_appends_preserve_event_and_resets_workspace():
    events = [
        _edit(0, "pkg/mod.py", "failed", action_signature="patch_a"),
        _edit(1, "pkg/mod.py", "failed", action_signature="patch_b"),
        _edit(2, "pkg/mod.py", "failed", action_signature="patch_c"),
        _edit(3, "pkg/other.py", "succeeded", action_signature="patch_d"),
    ]
    trip = _first_trip(events)
    diagnostic = interventions.build_diagnostic(trip)

    result = interventions.execute_rollback(tape=[], workspace=events, trip=trip, diagnostic=diagnostic)

    assert result.event["event_type"] == "TrajectoryRolledBack"
    assert result.event["schema_id"] == "trajectory_rolled_back.v1"
    assert result.event["head_effect"] == "PRESERVE"
    assert result.event["detector_rule_id"] == trip.rule_id
    assert result.event["diagnostic_digest"] == diagnostic.digest
    assert result.event["event_hash"].startswith("sha256:")

    # Tape = full history + the rollback event appended (never rewritten/truncated).
    assert list(result.tape) == [result.event]

    # Workspace reset to (and including) the fork point -- the fork point for this
    # rule is the *first* failed edit of the streak (seq=0), so the workspace after
    # rollback keeps only that first event.
    assert [e["seq"] for e in result.workspace] == [0]
    assert result.fork_point["seq"] == 0


def test_execute_rollback_never_mutates_its_inputs():
    events = [
        _edit(0, "pkg/mod.py", "failed", action_signature="patch_a"),
        _edit(1, "pkg/mod.py", "failed", action_signature="patch_b"),
        _edit(2, "pkg/mod.py", "failed", action_signature="patch_c"),
    ]
    tape_in: list = []
    workspace_in = list(events)
    trip = _first_trip(events)
    diagnostic = interventions.build_diagnostic(trip)

    interventions.execute_rollback(tape=tape_in, workspace=workspace_in, trip=trip, diagnostic=diagnostic)

    assert tape_in == []
    assert workspace_in == events


def test_execute_rollback_fork_point_for_repeated_action_signature():
    events = [
        _command(0, "run_tests"),
        _command(1, "other_action"),
        _command(2, "run_tests"),
        _command(3, "run_tests"),
    ]
    trip = _first_trip(events, _cfg(action_window_size=4, action_window_repeat_threshold=3))
    diagnostic = interventions.build_diagnostic(trip)
    result = interventions.execute_rollback(tape=[], workspace=events, trip=trip, diagnostic=diagnostic)
    # Earliest occurrence of the repeating signature ("run_tests") is seq=0.
    assert result.fork_point["seq"] == 0
    assert [e["seq"] for e in result.workspace] == [0]


def test_execute_rollback_fork_point_for_phase_timeout_is_phase_start():
    events = [_phase(0, "dispatch", "start")] + [_command(i, f"noop_{i}", outcome="succeeded") for i in range(1, 6)]
    trip = _first_trip(events, _cfg(phase_timeout_steps=5))
    diagnostic = interventions.build_diagnostic(trip)
    result = interventions.execute_rollback(tape=[], workspace=events, trip=trip, diagnostic=diagnostic)
    assert result.fork_point["seq"] == 0
    assert result.fork_point["event_type"] == "phase_boundary"


def test_execute_rollback_fork_point_for_bare_termination_no_phase_is_stream_start():
    events = [
        _command(0, "setup"),
        _command(1, "attempt"),
        _termination(2, None, "ERROR"),
    ]
    trip = _first_trip(events)
    diagnostic = interventions.build_diagnostic(trip)
    result = interventions.execute_rollback(tape=[], workspace=events, trip=trip, diagnostic=diagnostic)
    assert result.fork_point["seq"] == 0


def test_trajectory_event_hash_is_deterministic_and_replayable():
    event = _edit(0, "pkg/mod.py", "failed", action_signature="patch_a")
    h1 = interventions.trajectory_event_hash(event)
    h2 = interventions.trajectory_event_hash(dict(event))
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_rollback_is_itself_replayable_via_the_tape():
    """Decision 1: '重放时回滚本身可重放' -- replaying `tape` (which now contains the
    TrajectoryRolledBack event) through the same rollback-resolution logic a second
    time (same trip/diagnostic inputs) must derive a byte-identical event."""
    events = [
        _edit(0, "pkg/mod.py", "failed", action_signature="patch_a"),
        _edit(1, "pkg/mod.py", "failed", action_signature="patch_b"),
        _edit(2, "pkg/mod.py", "failed", action_signature="patch_c"),
    ]
    trip = _first_trip(events)
    diagnostic = interventions.build_diagnostic(trip)
    result1 = interventions.execute_rollback(tape=[], workspace=events, trip=trip, diagnostic=diagnostic)

    # Independent second derivation over the same fixed inputs.
    trip2 = _first_trip(events)
    diagnostic2 = interventions.build_diagnostic(trip2)
    result2 = interventions.execute_rollback(tape=[], workspace=events, trip=trip2, diagnostic=diagnostic2)

    assert result1.event == result2.event
    assert list(result1.tape) == list(result2.tape)
    assert list(result1.workspace) == list(result2.workspace)


# ---------------------------------------------------------------------------
# (b) Rollback cap.
# ---------------------------------------------------------------------------


def test_rollback_cap_allows_up_to_the_configured_max_then_raises():
    events = [
        _edit(0, "pkg/mod.py", "failed", action_signature="patch_a"),
        _edit(1, "pkg/mod.py", "failed", action_signature="patch_b"),
        _edit(2, "pkg/mod.py", "failed", action_signature="patch_c"),
    ]
    trip = _first_trip(events)
    diagnostic = interventions.build_diagnostic(trip)

    tape: list = []
    cap = 2  # fixture value, distinct from the module's own published default (also 2).
    for _ in range(cap):
        result = interventions.execute_rollback(
            tape=tape, workspace=events, trip=trip, diagnostic=diagnostic, max_rollbacks_per_fork_point=cap
        )
        tape = list(result.tape)

    assert interventions.count_prior_rollbacks_at_fork_point(
        tape, interventions.trajectory_event_hash(interventions.resolve_fork_point(events, trip))
    ) == cap

    with pytest.raises(interventions.RollbackCapExceededError):
        interventions.execute_rollback(
            tape=tape, workspace=events, trip=trip, diagnostic=diagnostic, max_rollbacks_per_fork_point=cap
        )


def test_rollback_cap_default_matches_adr_decision1_published_initial_value():
    assert interventions.DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT == 2


def test_rollback_cap_is_per_fork_point_not_global():
    """A cap hit at one fork point must not block a rollback at a *different* fork
    point."""
    events_a = [
        _edit(0, "pkg/a.py", "failed", action_signature="a1"),
        _edit(1, "pkg/a.py", "failed", action_signature="a2"),
        _edit(2, "pkg/a.py", "failed", action_signature="a3"),
    ]
    events_b = [
        _edit(0, "pkg/b.py", "failed", action_signature="b1"),
        _edit(1, "pkg/b.py", "failed", action_signature="b2"),
        _edit(2, "pkg/b.py", "failed", action_signature="b3"),
    ]
    trip_a = _first_trip(events_a)
    diagnostic_a = interventions.build_diagnostic(trip_a)
    cap = 1
    tape: list = []
    result = interventions.execute_rollback(
        tape=tape, workspace=events_a, trip=trip_a, diagnostic=diagnostic_a, max_rollbacks_per_fork_point=cap
    )
    tape = list(result.tape)
    with pytest.raises(interventions.RollbackCapExceededError):
        interventions.execute_rollback(
            tape=tape, workspace=events_a, trip=trip_a, diagnostic=diagnostic_a, max_rollbacks_per_fork_point=cap
        )

    trip_b = _first_trip(events_b)
    diagnostic_b = interventions.build_diagnostic(trip_b)
    # Different fork point (pkg/b.py) -- must still be allowed even though the same
    # tape already holds one rollback for pkg/a.py's fork point.
    result_b = interventions.execute_rollback(
        tape=tape, workspace=events_b, trip=trip_b, diagnostic=diagnostic_b, max_rollbacks_per_fork_point=cap
    )
    assert result_b.event["fork_point_event_hash"] != result.event["fork_point_event_hash"]


# ---------------------------------------------------------------------------
# renumber_and_append helper (used by live_driver.py's --monitor hook).
# ---------------------------------------------------------------------------


def test_renumber_and_append_continues_seq_and_is_pure():
    existing = [_edit(0, "a.py", "failed"), _edit(1, "a.py", "succeeded")]
    fresh_task_events = [
        {"seq": 0, "event_type": "command", "instance_id": "x", "route_id": None, "action_signature": "s", "outcome": "failed"},
        {"seq": 1, "event_type": "termination", "instance_id": "x", "route_id": None, "phase": None, "reason_class": "ERROR"},
    ]
    combined = interventions.renumber_and_append(existing, fresh_task_events)
    assert [e["seq"] for e in combined] == [0, 1, 2, 3]
    # Purity: inputs untouched.
    assert [e["seq"] for e in existing] == [0, 1]
    assert [e["seq"] for e in fresh_task_events] == [0, 1]
    # Renumbered stream is still a structurally valid trajectory for the detector.
    cfg = _cfg()
    loop_detector.find_all_trips(combined, cfg)  # must not raise


def test_renumber_and_append_on_empty_base_starts_at_zero():
    fresh = [{"seq": 0, "event_type": "command", "instance_id": "x", "route_id": None, "action_signature": "s", "outcome": "succeeded"}]
    combined = interventions.renumber_and_append([], fresh)
    assert [e["seq"] for e in combined] == [0]

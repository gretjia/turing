"""WP-H1 acceptance tests (ADR-ECON-007 Decision 2; design doc
`research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L1.1 rule 1):
`tools/econ_lab/monitor/loop_detector.py`'s four rule-based, deterministic-replay
detection rules.

Every synthetic fixture's threshold value is a harness-invented arbitrary constant
(never claimed to be an ADR-pinned B-zone number -- see `LoopDetectorConfig`'s and each
fixture helper's own docstring/comment). Two tests additionally exercise the module's
`events_from_real_settlement_checkpoint` translator against real, unmodified
`settlement.json` artifacts copied from `tools/econ_lab/runs/stageA_20260707/**` into
`tools/econ_lab/monitor/fixtures/`, proving the event envelope actually fits real
on-disk trajectory data (not just hand-built synthetic events).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"
MONITOR_FIXTURES = ECON_LAB / "monitor" / "fixtures"

sys.path.insert(0, str(ECON_LAB))

import monitor.loop_detector as loop_detector  # noqa: E402


# ---------------------------------------------------------------------------
# Shared test-only config. Test-only constants: no ADR/design-memo pins a concrete
# loop-detector threshold value -- RES_ROUTE_lockIn_remedy_design_20260710 §5
# explicitly marks "升级阈值" calibration as an open, uncited internal experiment
# ("开放问题→内部实验"), and its own blacklist (top of §0) bars citing any of the
# falsified literature numbers (LATS 92.7%, the "2 次失败升级" threshold, Expert-
# Executor 3.4x) as if they were load-bearing here. These four numbers are therefore
# harness-invented arbitrary fixture values chosen only to exercise the rule logic
# with small, readable event streams -- unlike `routing_fold.rs`'s `test_anneal_cfg`,
# which *is* permitted to mirror ADR-ECON-003 Decision 5's real published starting
# values. Production code never hardcodes them (`LoopDetectorConfig` is 100%
# caller-supplied; see the module's B-zone discipline docstring section).
def _test_cfg(**overrides) -> loop_detector.LoopDetectorConfig:
    base = dict(
        same_fragment_failure_threshold=3,
        action_window_size=4,
        action_window_repeat_threshold=3,
        phase_timeout_steps=5,
    )
    base.update(overrides)
    return loop_detector.LoopDetectorConfig(**base)


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


# ---------------------------------------------------------------------------
# Rule 1: same file/fragment, N consecutive failed edits.
# ---------------------------------------------------------------------------


def test_rule1_positive_three_consecutive_failed_edits_same_fragment_trips():
    cfg = _test_cfg()
    events = [
        _edit(0, "pkg/mod.py", "failed"),
        _edit(1, "pkg/mod.py", "failed"),
        _edit(2, "pkg/mod.py", "failed"),
    ]
    verdict = loop_detector.detect(events, cfg)
    assert verdict["tripped"] is True
    assert verdict["rule_id"] == loop_detector.RULE_SAME_FRAGMENT_REPEATED_FAILURE
    assert verdict["at_seq"] == 2
    # Decision 3: evidence carries facts, never a count/threshold value.
    assert verdict["evidence"]["file_path"] == "pkg/mod.py"
    assert "same_fragment_failure_threshold" not in json.dumps(verdict)
    assert "3" not in [str(v) for v in verdict["evidence"].values() if isinstance(v, int)]


def test_rule1_negative_a_success_resets_the_streak_no_trip():
    cfg = _test_cfg()
    events = [
        _edit(0, "pkg/mod.py", "failed"),
        _edit(1, "pkg/mod.py", "failed"),
        _edit(2, "pkg/mod.py", "succeeded"),
        _edit(3, "pkg/mod.py", "failed"),
        _edit(4, "pkg/mod.py", "failed"),
    ]
    verdict = loop_detector.detect(events, cfg)
    assert verdict == loop_detector.NOT_TRIPPED


def test_rule1_negative_failures_spread_across_different_fragments_no_trip():
    cfg = _test_cfg()
    events = [
        _edit(0, "pkg/mod.py", "failed", fragment_id="frag_a"),
        _edit(1, "pkg/mod.py", "failed", fragment_id="frag_b"),
        _edit(2, "pkg/mod.py", "failed", fragment_id="frag_c"),
    ]
    verdict = loop_detector.detect(events, cfg)
    assert verdict == loop_detector.NOT_TRIPPED


# ---------------------------------------------------------------------------
# Rule 2: repeated action signature inside a trailing window.
# ---------------------------------------------------------------------------


def test_rule2_positive_repeated_signature_within_window_trips():
    cfg = _test_cfg()
    events = [
        _command(0, "run_tests"),
        _command(1, "run_tests"),
        _command(2, "grep_traceback"),
        _command(3, "run_tests"),
    ]
    verdict = loop_detector.detect(events, cfg)
    assert verdict["tripped"] is True
    assert verdict["rule_id"] == loop_detector.RULE_REPEATED_ACTION_SIGNATURE_WINDOW
    assert verdict["evidence"]["action_signature"] == "run_tests"


def test_rule2_negative_distinct_signatures_no_trip():
    cfg = _test_cfg()
    events = [
        _command(0, "run_tests"),
        _command(1, "grep_traceback"),
        _command(2, "lint"),
        _command(3, "run_tests"),
    ]
    verdict = loop_detector.detect(events, cfg)
    assert verdict == loop_detector.NOT_TRIPPED


# ---------------------------------------------------------------------------
# Rule 3: phase timeout (a phase stays open longer than the step budget).
# ---------------------------------------------------------------------------


def test_rule3_positive_phase_stays_open_past_budget_trips():
    cfg = _test_cfg()
    events = [_phase(0, "explore", "start")]
    events += [_command(i, f"probe_{i}", outcome="unknown") for i in range(1, 7)]
    verdict = loop_detector.detect(events, cfg)
    assert verdict["tripped"] is True
    assert verdict["rule_id"] == loop_detector.RULE_PHASE_TIMEOUT
    assert verdict["evidence"]["phase"] == "explore"


def test_rule3_negative_phase_closes_before_budget_no_trip():
    cfg = _test_cfg()
    events = [
        _phase(0, "explore", "start"),
        _command(1, "probe_1", outcome="unknown"),
        _phase(2, "explore", "end"),
    ]
    events += [_command(i, f"probe_{i}", outcome="unknown") for i in range(3, 9)]
    verdict = loop_detector.detect(events, cfg)
    assert verdict == loop_detector.NOT_TRIPPED


# ---------------------------------------------------------------------------
# Rule 4: termination without prior verifier evidence (ADR-ECON-007 Decision 4: no
# bare error-out).
# ---------------------------------------------------------------------------


def test_rule4_positive_bare_termination_with_no_verification_trips():
    cfg = _test_cfg()
    events = [
        _phase(0, "dispatch", "start"),
        _command(1, "dispatch_worker", outcome="failed"),
        _termination(2, "dispatch", "ERROR"),
    ]
    verdict = loop_detector.detect(events, cfg)
    assert verdict["tripped"] is True
    assert verdict["rule_id"] == loop_detector.RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE
    assert verdict["evidence"]["reason_class"] == "ERROR"


def test_rule4_negative_termination_after_verification_evidence_no_trip():
    cfg = _test_cfg()
    events = [
        _phase(0, "dispatch", "start"),
        _command(1, "dispatch_worker", outcome="succeeded"),
        _verification(2, "dispatch", "fail"),
        _termination(3, "dispatch", "COMPLETED"),
    ]
    verdict = loop_detector.detect(events, cfg)
    assert verdict == loop_detector.NOT_TRIPPED


# ---------------------------------------------------------------------------
# Determinism / pure-replay.
# ---------------------------------------------------------------------------


def test_detect_is_a_pure_function_replay_is_byte_identical():
    cfg = _test_cfg()
    events = [
        _edit(0, "pkg/mod.py", "failed"),
        _edit(1, "pkg/mod.py", "failed"),
        _edit(2, "pkg/mod.py", "failed"),
    ]
    first = loop_detector.detect(copy.deepcopy(events), cfg)
    second = loop_detector.detect(copy.deepcopy(events), cfg)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_config_rejects_non_positive_threshold():
    with pytest.raises(loop_detector.LoopDetectorError):
        _test_cfg(same_fragment_failure_threshold=0)


def test_config_rejects_repeat_threshold_above_window_size():
    with pytest.raises(loop_detector.LoopDetectorError):
        _test_cfg(action_window_size=2, action_window_repeat_threshold=3)


def test_stream_must_be_strictly_increasing_by_seq():
    cfg = _test_cfg()
    events = [_edit(0, "pkg/mod.py", "failed"), _edit(0, "pkg/mod.py", "failed")]
    with pytest.raises(loop_detector.LoopDetectorError):
        loop_detector.detect(events, cfg)


# ---------------------------------------------------------------------------
# Empirical format-fit: real, unmodified settlement.json fixtures copied from
# tools/econ_lab/runs/stageA_20260707/**.
# ---------------------------------------------------------------------------


def _load_real_settlement(name: str) -> dict:
    path = MONITOR_FIXTURES / name
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_real_fixture_pytest_5787_bare_error_out_trips_termination_rule():
    """`real_settlement_pytest_dev_pytest_5787_tau_0p5.json` (source:
    `tools/econ_lab/runs/stageA_20260707/tau_0p5/task_runs/pytest-dev__pytest-5787/
    settlement.json`, sha256 f10cfb4518de008caaad5db2e06b5024d2afbda33dcdba7e11a3aada
    497679c1) is a real historical dispatch where the worker errored out
    (`worker_result.status == "ERROR"`, `primary_attempt_status == "API_ERROR"`) and
    scoring never ran (`scoring_result.status == "SKIPPED_NO_PATCH"`) -- a genuine,
    unmodified example of ADR-ECON-007 Decision 4's "裸 error-out". The translator
    should surface exactly that as a termination-without-verifier-evidence trip; a
    generously large config (thresholds well above this short real trace's event
    count) isolates rule 4 so the other three rules cannot spuriously fire on it.
    """
    settlement = _load_real_settlement("real_settlement_pytest_dev_pytest_5787_tau_0p5.json")
    events = loop_detector.events_from_real_settlement_checkpoint(settlement)
    cfg = _test_cfg(
        same_fragment_failure_threshold=100,
        action_window_size=100,
        action_window_repeat_threshold=100,
        phase_timeout_steps=100,
    )
    verdict = loop_detector.detect(events, cfg)
    assert verdict["tripped"] is True
    assert verdict["rule_id"] == loop_detector.RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE
    assert verdict["evidence"]["reason_class"] == "ERROR"


def test_real_fixture_astropy_13977_verifier_ran_does_not_trip_termination_rule():
    """`real_settlement_astropy_astropy_13977_tau_0p5.json` (source:
    `tools/econ_lab/runs/stageA_20260707/tau_0p5/task_runs/astropy__astropy-13977/
    settlement.json`, sha256 6188bcdf63cba31a2307eea2f7365c048cf2aee95ec1bb975700b33e
    75ac20dd) is a real historical dispatch where the independent verifier actually
    ran to completion (`scoring_result.status == "COMPLETED"`, a real
    `live_split_verdict`) even though the patch was ultimately UNRESOLVED. Decision 4
    only requires verifier *evidence*, not a passing verdict, so this must not trip
    rule 4 -- the negative half of the same real-data format-fit proof.
    """
    settlement = _load_real_settlement("real_settlement_astropy_astropy_13977_tau_0p5.json")
    events = loop_detector.events_from_real_settlement_checkpoint(settlement)
    cfg = _test_cfg(
        same_fragment_failure_threshold=100,
        action_window_size=100,
        action_window_repeat_threshold=100,
        phase_timeout_steps=100,
    )
    verdict = loop_detector.detect(events, cfg)
    assert verdict == loop_detector.NOT_TRIPPED


def test_real_fixture_translation_emits_only_the_documented_event_types():
    for name in (
        "real_settlement_pytest_dev_pytest_5787_tau_0p5.json",
        "real_settlement_astropy_astropy_13977_tau_0p5.json",
    ):
        settlement = _load_real_settlement(name)
        events = loop_detector.events_from_real_settlement_checkpoint(settlement)
        assert events, name
        seqs = [e["seq"] for e in events]
        assert seqs == sorted(seqs) == list(range(len(events)))
        for event in events:
            assert event["event_type"] in loop_detector.EVENT_TYPES
            assert event["instance_id"] == settlement["instance_id"]
        # No synthesized "edit" event: settlement.json has no file/fragment-level
        # data, and the translator must not invent granularity the source lacks.
        assert all(e["event_type"] != "edit" for e in events)

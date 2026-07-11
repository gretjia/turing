"""WP-H3 acceptance tests (ADR-ECON-007 Decision 4; design doc
`research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L1.3):
`tools/econ_lab/monitor/termination.py`'s verification-gated termination guard +
route-falsification report.

Four claims required by this WP's own brief:
  1. A bare error (any exception raised inside a `finalize` callable) is intercepted
     by `guard_bare_termination` and converted into the FALSIFIED report path -- it
     never propagates past the guard.
  2. The falsification report carries exactly Decision 4's schema (route_id, attempts,
     verifier_evidence[], detector_events[], remaining_candidates[], recommendation)
     plus this module's own schema/proposal_only/digest bookkeeping.
  3. The report never carries a B-zone quantity (`assert_report_has_no_bzone_leak`
     blacklist, exercised against both legal and deliberately-illegal fixtures).
  4. The success path is unaffected: `guard_bare_termination`'s happy path (finalize
     succeeds, accept evidence present) produces the exact same outcome as calling
     `terminate_accepted` directly -- the guard adds no side effect to that path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"

sys.path.insert(0, str(ECON_LAB))

import monitor.termination as termination  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers.
# ---------------------------------------------------------------------------

ROUTE_ID = "fixture-instance::A::sonnet"

PASS_EVIDENCE = [{"phase": "dispatch", "result": "pass"}]
FAIL_EVIDENCE = [{"phase": "dispatch", "result": "fail"}]
NO_EVIDENCE: list = []

DETECTOR_EVENTS = [
    {
        "rule_id": "TERMINATION_WITHOUT_VERIFIER_EVIDENCE",
        "evidence": {"fact_class": "BARE_TERMINATION", "phase": "dispatch", "reason_class": "ERROR"},
    }
]
ATTEMPTS = [
    {"fact_class": "REMEDIATION_EXHAUSTED", "detector_rule_id": "TERMINATION_WITHOUT_VERIFIER_EVIDENCE"},
]
REMAINING_CANDIDATES = ["fixture-instance::B::sonnet", "fixture-instance::C::sonnet"]
RECOMMENDATION = (
    "Route repeatedly reached termination without verifier evidence; remediation is "
    "exhausted. Recommend GRILL-ME review before further dispatch on this route."
)


def _build_report_kwargs(**overrides):
    kwargs = dict(
        route_id=ROUTE_ID,
        attempts=ATTEMPTS,
        verifier_evidence=FAIL_EVIDENCE,
        detector_events=DETECTOR_EVENTS,
        remaining_candidates=REMAINING_CANDIDATES,
        recommendation=RECOMMENDATION,
    )
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# 1. Bare error interception.
# ---------------------------------------------------------------------------


def test_bare_error_is_intercepted_and_never_propagates():
    def _boom():
        raise RuntimeError("this text must never leak into the report")

    outcome = termination.guard_bare_termination(
        _boom,
        **_build_report_kwargs(verifier_evidence=NO_EVIDENCE),
    )

    assert outcome.status == termination.FALSIFIED
    assert outcome.report is not None
    assert outcome.event is not None
    intercepted = [a for a in outcome.report["attempts"] if a.get("fact_class") == "BARE_ERROR_INTERCEPTED"]
    assert len(intercepted) == 1
    assert intercepted[0]["exception_class"] == "RuntimeError"
    # The exception's own message text must never appear anywhere in the report.
    assert "must never leak" not in str(outcome.report)


def test_bare_error_raising_exception_type_does_not_escape_guard():
    def _boom():
        raise KeyError("secret")

    # Must not raise -- the whole point of the guard.
    outcome = termination.guard_bare_termination(_boom, **_build_report_kwargs(verifier_evidence=NO_EVIDENCE))
    assert outcome.status == termination.FALSIFIED


def test_finalize_succeeds_but_no_accept_evidence_is_also_falsified_not_a_silent_success():
    calls = []

    def _quiet_success():
        calls.append("ran")

    outcome = termination.guard_bare_termination(
        _quiet_success,
        **_build_report_kwargs(verifier_evidence=FAIL_EVIDENCE),
    )
    assert calls == ["ran"]
    assert outcome.status == termination.FALSIFIED
    assert outcome.report is not None
    # No BARE_ERROR_INTERCEPTED entry -- finalize did not raise, it just had no evidence.
    assert all(a.get("fact_class") != "BARE_ERROR_INTERCEPTED" for a in outcome.report["attempts"])


# ---------------------------------------------------------------------------
# 2. Report schema completeness.
# ---------------------------------------------------------------------------


def test_report_schema_has_exactly_decision_4_fields_plus_bookkeeping():
    report = termination.build_route_falsification_report(**_build_report_kwargs()).to_dict()

    decision_4_fields = {
        "route_id",
        "attempts",
        "verifier_evidence",
        "detector_events",
        "remaining_candidates",
        "recommendation",
    }
    bookkeeping_fields = {"schema", "proposal_only", "digest"}
    assert decision_4_fields <= set(report.keys())
    assert set(report.keys()) == decision_4_fields | bookkeeping_fields

    assert report["schema"] == termination.ROUTE_FALSIFICATION_REPORT_SCHEMA
    assert report["proposal_only"] is True
    assert report["route_id"] == ROUTE_ID
    assert report["attempts"] == ATTEMPTS
    assert report["verifier_evidence"] == FAIL_EVIDENCE
    assert report["detector_events"] == DETECTOR_EVENTS
    assert report["remaining_candidates"] == REMAINING_CANDIDATES
    assert report["recommendation"] == RECOMMENDATION
    assert isinstance(report["digest"], str) and report["digest"].startswith("sha256:")


def test_terminate_falsified_pairs_report_with_a_preserve_event_referencing_its_digest():
    outcome = termination.terminate_falsified(**_build_report_kwargs(), seq=7)

    assert outcome.status == termination.FALSIFIED
    event = outcome.event
    assert event["event_type"] == termination.ROUTE_FALSIFIED_EVENT_TYPE
    assert event["head_effect"] == "PRESERVE"
    assert event["route_id"] == ROUTE_ID
    assert event["report_digest"] == outcome.report["digest"]
    assert event["seq"] == 7
    assert event["event_hash"].startswith("sha256:")


def test_report_is_deterministic_same_inputs_same_digest():
    report_a = termination.build_route_falsification_report(**_build_report_kwargs())
    report_b = termination.build_route_falsification_report(**_build_report_kwargs())
    assert report_a.digest == report_b.digest


def test_verifier_evidence_entry_must_have_a_legal_result_value():
    with pytest.raises(termination.TerminationError):
        termination.build_route_falsification_report(
            **_build_report_kwargs(verifier_evidence=[{"phase": "dispatch", "result": "maybe"}])
        )


# ---------------------------------------------------------------------------
# 3. Report never carries a B-zone quantity.
# ---------------------------------------------------------------------------


def test_legal_report_passes_the_bzone_blacklist():
    report = termination.build_route_falsification_report(**_build_report_kwargs()).to_dict()
    # Must not raise.
    termination.assert_report_has_no_bzone_leak(report)


@pytest.mark.parametrize(
    "bad_attempts",
    [
        [{"tau_value": "should be forbidden by key name"}],
        [{"bucket_key": "should be forbidden by key name"}],
        [{"detector_rule_id": "TERMINATION_WITHOUT_VERIFIER_EVIDENCE", "fired_count": 3}],
        [{"detector_rule_id": "TERMINATION_WITHOUT_VERIFIER_EVIDENCE", "was_terminal": True}],
    ],
)
def test_illegal_attempts_field_is_rejected_by_report_builder(bad_attempts):
    with pytest.raises(termination.RouteFalsificationError):
        termination.build_route_falsification_report(**_build_report_kwargs(attempts=bad_attempts))


def test_recommendation_with_bzone_vocabulary_is_rejected():
    with pytest.raises(termination.RouteFalsificationError):
        termination.build_route_falsification_report(
            **_build_report_kwargs(recommendation="the tau threshold governs this route")
        )


def test_recommendation_with_untraceable_digit_is_rejected():
    with pytest.raises(termination.RouteFalsificationError):
        termination.build_route_falsification_report(
            **_build_report_kwargs(recommendation="this route failed 7 times before giving up")
        )


def test_recommendation_digit_traceable_to_a_whitelisted_fact_is_allowed():
    # The route_id itself legitimately contains no digits here, but a remaining
    # candidate id might (e.g. an instance id with a numeric suffix); such a digit is
    # traceable and must be allowed, not flagged as an untraceable B-zone leak.
    report = termination.build_route_falsification_report(
        **_build_report_kwargs(
            remaining_candidates=["fixture-instance-42::B::sonnet"],
            recommendation="Consider dispatching fixture-instance-42::B::sonnet next.",
        )
    ).to_dict()
    termination.assert_report_has_no_bzone_leak(report)


def test_assert_report_has_no_bzone_leak_rejects_a_hand_built_illegal_report():
    illegal_report = {
        "schema": termination.ROUTE_FALSIFICATION_REPORT_SCHEMA,
        "route_id": ROUTE_ID,
        "attempts": [{"q_eff_snapshot": "0.42"}],
        "verifier_evidence": [],
        "detector_events": [],
        "remaining_candidates": [],
        "recommendation": "fine",
        "proposal_only": True,
    }
    with pytest.raises(termination.RouteFalsificationError):
        termination.assert_report_has_no_bzone_leak(illegal_report)


# ---------------------------------------------------------------------------
# 4. Success path unaffected (parity between the guard's happy path and calling
#    terminate_accepted directly).
# ---------------------------------------------------------------------------


def test_guard_happy_path_matches_direct_terminate_accepted_call():
    def _clean_finalize():
        return None

    direct = termination.terminate_accepted(route_id=ROUTE_ID, verifier_evidence=PASS_EVIDENCE)
    guarded = termination.guard_bare_termination(
        _clean_finalize,
        **_build_report_kwargs(verifier_evidence=PASS_EVIDENCE),
    )

    assert guarded.status == direct.status == termination.ACCEPTED
    assert guarded.route_id == direct.route_id == ROUTE_ID
    assert guarded.accept_evidence == direct.accept_evidence == {"phase": "dispatch", "result": "pass"}
    assert guarded.event is None
    assert guarded.report is None


def test_terminate_accepted_requires_at_least_one_pass_evidence_entry():
    with pytest.raises(termination.TerminationError):
        termination.terminate_accepted(route_id=ROUTE_ID, verifier_evidence=FAIL_EVIDENCE)
    with pytest.raises(termination.TerminationError):
        termination.terminate_accepted(route_id=ROUTE_ID, verifier_evidence=NO_EVIDENCE)


def test_terminate_accepted_uses_the_last_pass_entry_deterministically():
    evidence = [
        {"phase": "dispatch", "result": "fail"},
        {"phase": "dispatch", "result": "pass"},
        {"phase": "scoring", "result": "fail"},
        {"phase": "scoring", "result": "pass"},
    ]
    outcome = termination.terminate_accepted(route_id=ROUTE_ID, verifier_evidence=evidence)
    assert outcome.accept_evidence == {"phase": "scoring", "result": "pass"}

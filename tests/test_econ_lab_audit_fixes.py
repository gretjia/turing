"""Regression tests for the 2026-07-07 econ_lab peripheral-module audit fixes.

Each test pins one confirmed defect fix; well-formed-input behavior of every touched
module is covered by the pre-existing suites (`test_econ_lab_wp7_harness.py`,
`test_live_split_verifier.py`) and must stay green alongside these:

  * node.Ledger.clawback: the event-hash dedup record now binds the original
    (key, v), so a clawback carrying a known hash but a mismatched node key or
    verdict raises FoldError instead of silently corrupting (N, S) counters.
  * selection: an empty route pool raises ValueError("empty route_ids") in every
    regime instead of returning None (argmax) or IndexError (inverse-CDF paths).
  * runner.load_stream: a duplicate case_id is rejected at load time by name
    instead of surfacing later as a confusing FoldError deep in the arm fold.
  * live_split_verifier.collect_test_outcomes: fail-closed across grading
    categories -- once a test_id is recorded as failing, a later category's
    success list never upgrades it back to passing.
  * analysis/stage_a_readout: `settlement_verdict_resolved` aggregation keeps the
    first non-None verdict (covered by that frozen script's own self-test case 6,
    invoked here via its CLI per its addendum discipline).
  * arms/runner (finding B4, fixed 2026-07-08): static_oracle's calibration-round
    settlement events (side == "calibration") are excluded from the formal counters
    `pass_at_budget` and `n_accept_settled`; the calibration label reads themselves
    are retained and documented (arms.py module-docstring addendum 2026-07-08), and
    aggregates for zero-calibration arms/streams are pinned byte-identical.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"

sys.path.insert(0, str(ECON_LAB))

import arms  # noqa: E402
import runner  # noqa: E402
import selection  # noqa: E402
from node import FoldError, Ledger  # noqa: E402
from verifier import live_split_verifier as lsv  # noqa: E402
from verifier.split import ACCEPT_SIDE, VERIFY_SIDE, split_side  # noqa: E402


# ---------------------------------------------------------------------------
# node.Ledger.clawback binds (key, v) to the original update
# ---------------------------------------------------------------------------


def test_clawback_with_mismatched_key_raises_fold_error():
    ledger = Ledger()
    ledger.update(("bucket", "scaffold-a"), "sha256:e1", 1, 0.5)
    with pytest.raises(FoldError):
        ledger.clawback(("bucket", "scaffold-b"), "sha256:e1", 1, 0.5)
    # The mismatched clawback must not have touched any node state.
    assert ledger.states[("bucket", "scaffold-a")].n == 1
    assert ("bucket", "scaffold-b") not in ledger.states


def test_clawback_with_mismatched_verdict_raises_fold_error():
    ledger = Ledger()
    ledger.update(("bucket", "scaffold-a"), "sha256:e1", 1, 0.5)
    with pytest.raises(FoldError):
        ledger.clawback(("bucket", "scaffold-a"), "sha256:e1", 0, 0.5)
    state = ledger.states[("bucket", "scaffold-a")]
    assert (state.n, state.s) == (1, 1)


def test_correct_clawback_still_works_and_is_exact_inverse():
    ledger = Ledger()
    ledger.update(("bucket", "scaffold-a"), "sha256:e1", 1, 0.5)
    state = ledger.clawback(("bucket", "scaffold-a"), "sha256:e1", 1, 0.5)
    assert (state.n, state.s) == (0, 0)
    # At-most-once clawback (Decision 6.3) is unchanged.
    with pytest.raises(FoldError):
        ledger.clawback(("bucket", "scaffold-a"), "sha256:e1", 1, 0.5)


def test_duplicate_update_fold_error_message_is_unchanged():
    ledger = Ledger()
    ledger.update(("bucket", "scaffold-a"), "sha256:e1", 1, 0.5)
    with pytest.raises(FoldError, match="^duplicate RoutingPriorUpdated event_hash applied twice$"):
        ledger.update(("bucket", "scaffold-a"), "sha256:e1", 0, 0.5)


# ---------------------------------------------------------------------------
# selection: empty route pool raises in every regime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tau", [0, 0.5, 1.0, None, math.inf])
def test_select_on_empty_pool_raises_value_error(tau):
    with pytest.raises(ValueError, match="empty route_ids"):
        selection.select([], {}, tau, 0.5)


def test_direct_selectors_on_empty_pool_raise_value_error():
    # arms.py calls select_uniform directly, so the concrete selectors are public too.
    with pytest.raises(ValueError, match="empty route_ids"):
        selection.select_argmax([], {})
    with pytest.raises(ValueError, match="empty route_ids"):
        selection.select_uniform([], 0.5)
    with pytest.raises(ValueError, match="empty route_ids"):
        selection.select_softmax([], {}, 1.0, 0.5)


def test_select_on_nonempty_pool_unchanged():
    routes = ["r-b", "r-a"]
    q = {"r-a": 0.2, "r-b": 0.9}
    assert selection.select(routes, q, 0, 0.5) == "r-b"  # argmax, input-order tie-break
    assert selection.select(routes, q, None, 0.0) == "r-a"  # uniform over sorted ids
    assert selection.select(routes, q, 1.0, 0.0) == "r-a"  # softmax inverse-CDF, u=0


# ---------------------------------------------------------------------------
# runner.load_stream: duplicate case_id rejected at load time
# ---------------------------------------------------------------------------


def test_load_stream_with_duplicate_case_id_raises_value_error(tmp_path):
    stream = {
        "schema": runner.STREAM_SCHEMA,
        "buckets": {
            "bucket_dup": {
                "scaffolds": {"scaffold:sha256:s0": {"p_prior": 0.5}},
                "trials": [
                    {"case_id": "case-dup-0000"},
                    {"case_id": "case-dup-0000"},
                ],
            }
        },
    }
    path = tmp_path / "dup_stream.json"
    path.write_text(json.dumps(stream), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case_id 'case-dup-0000'"):
        runner.load_stream(path)


def test_load_stream_default_fixture_still_loads():
    stream = runner.load_stream(runner.DEFAULT_FIXTURE)
    assert stream["schema"] == runner.STREAM_SCHEMA
    assert stream["buckets"]


# ---------------------------------------------------------------------------
# live_split_verifier: fail-closed merge across grading categories
# ---------------------------------------------------------------------------


def test_failure_in_earlier_category_is_not_upgraded_by_later_success():
    """A test_id failing in FAIL_TO_PASS.failure then reappearing in
    PASS_TO_PASS.success must stay False (fail-closed across categories)."""
    repeated = "tests/test_module.py::test_case_0000"
    tests_status = {
        "FAIL_TO_PASS": {"success": [], "failure": [repeated]},
        "PASS_TO_PASS": {"success": [repeated], "failure": []},
        "FAIL_TO_FAIL": {"success": [], "failure": []},
        "PASS_TO_FAIL": {"success": [], "failure": []},
    }
    assert lsv.collect_test_outcomes(tests_status) == {repeated: False}


def test_within_category_failure_still_authoritative():
    tid = "tests/test_module.py::test_case_0000"
    tests_status = {
        "FAIL_TO_PASS": {"success": [tid], "failure": [tid]},
        "PASS_TO_PASS": {"success": [], "failure": []},
        "FAIL_TO_FAIL": {"success": [], "failure": []},
        "PASS_TO_FAIL": {"success": [], "failure": []},
    }
    assert lsv.collect_test_outcomes(tests_status) == {tid: False}


def test_disjoint_categories_unchanged():
    tests_status = {
        "FAIL_TO_PASS": {"success": ["t-pass-1"], "failure": ["t-fail-1"]},
        "PASS_TO_PASS": {"success": ["t-pass-2"], "failure": []},
        "FAIL_TO_FAIL": {"success": [], "failure": []},
        "PASS_TO_FAIL": {"success": [], "failure": []},
    }
    assert lsv.collect_test_outcomes(tests_status) == {
        "t-pass-1": True,
        "t-fail-1": False,
        "t-pass-2": True,
    }


# ---------------------------------------------------------------------------
# stage_a_readout: frozen script's own self-test (case 6 pins the verdict-
# aggregation fix; invoked via its CLI, matching its addendum discipline)
# ---------------------------------------------------------------------------


def test_stage_a_readout_self_test_passes():
    result = subprocess.run(
        [sys.executable, str(ECON_LAB / "analysis" / "stage_a_readout.py"), "--self-test"],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "STAGE_A_READOUT_SELF_TEST_PASS" in result.stdout


# ---------------------------------------------------------------------------
# arms/runner: static_oracle calibration round excluded from formal counters
# (audit finding B4; arms.py module-docstring addendum 2026-07-08)
# ---------------------------------------------------------------------------

_B4_SCAFFOLDS = ("scaffold:sha256:aaaa", "scaffold:sha256:bbbb")


def _b4_trial(case_id: str, accept_a: int, accept_b: int) -> dict:
    return {
        "case_id": case_id,
        "outcomes": {
            _B4_SCAFFOLDS[0]: {"accept": accept_a, "verify_witnesses": [1, 1, 0]},
            _B4_SCAFFOLDS[1]: {"accept": accept_b, "verify_witnesses": [1, 0, 0]},
        },
        "price_signal_hash": f"sha256:price-{case_id}",
        "pput_prior_hash": f"sha256:pput-{case_id}",
        "trigger_event_hash": f"sha256:trigger-{case_id}",
    }


def _b4_bucket_fixture() -> dict:
    """Calibration round (first ``len(scaffolds)`` = 2 trials) all pass; the four
    formal accept-side trials mostly fail (1/4) for the frozen-oracle pick. Both
    scaffolds calibrate at rate 1.0, so `_freeze_oracle_ranking`'s lexicographic
    tie-break picks ``_B4_SCAFFOLDS[0]`` for every formal trial. Split sides of the
    case_ids are re-asserted in the tests, not assumed."""
    trials = [
        # Calibration round: round-robin, all pass. Trial 1 is a verify-side case_id --
        # the calibration round still reads its accept label (documented, retained
        # behavior per the addendum); the fix is that it must not be formally counted.
        _b4_trial("case-b4-0000", 1, 1),  # calibration -> scaffolds[0], passes
        _b4_trial("case-b4-0003", 1, 1),  # calibration -> scaffolds[1], passes (verify-side)
        # Formal accept-side trials: oracle pick (scaffolds[0]) fails 3 of 4.
        _b4_trial("case-b4-0002", 0, 1),
        _b4_trial("case-b4-0004", 0, 1),
        _b4_trial("case-b4-0005", 0, 1),
        _b4_trial("case-b4-0006", 1, 0),
        # Formal verify-side trial: never accept-settled for any arm.
        _b4_trial("case-b4-0007", 1, 1),
    ]
    return {
        "scaffolds": {sid: {"p_prior": 0.5} for sid in _B4_SCAFFOLDS},
        "trials": trials,
    }


def test_b4_fixture_split_sides_are_as_designed():
    assert split_side("case-b4-0000") == ACCEPT_SIDE
    assert split_side("case-b4-0003") == VERIFY_SIDE
    for cid in ("case-b4-0002", "case-b4-0004", "case-b4-0005", "case-b4-0006"):
        assert split_side(cid) == ACCEPT_SIDE
    assert split_side("case-b4-0007") == VERIFY_SIDE


def test_static_oracle_pass_at_budget_counts_only_formal_trials():
    """Calibration trials all pass (2/2) but formal accept-side trials mostly fail
    (1/4): pass_at_budget must be exactly 1/4, not the calibration-inflated 3/6."""
    trace = arms.simulate_bucket(
        "bucket_b4", _b4_bucket_fixture(), arms.ArmSpec(name="static_oracle", kind="static_oracle")
    )
    calibration = [e for e in trace.events if e.side == "calibration"]
    assert len(calibration) == len(_B4_SCAFFOLDS)
    # The calibration events did settle with a non-None (all-pass) accept outcome ...
    assert all(e.accept_pass is True for e in calibration)
    # ... and the frozen oracle picked the lexicographic tie-break winner throughout.
    formal = [e for e in trace.events if e.side != "calibration"]
    assert all(e.scaffold_id == _B4_SCAFFOLDS[0] for e in formal)
    # Formal counter reflects ONLY the 4 formal accept-side trials (1 pass / 4).
    assert arms.pass_at_budget(trace) == 0.25


def test_static_oracle_n_accept_settled_excludes_calibration_trials():
    stream = {
        "schema": runner.STREAM_SCHEMA,
        "buckets": {"bucket_b4": _b4_bucket_fixture()},
    }
    verdict = runner.run_stream(
        stream, [arms.ArmSpec(name="static_oracle", kind="static_oracle")]
    )
    bucket = verdict["arms"]["static_oracle"]["buckets"]["bucket_b4"]
    # 4 formal accept-side settlements; the 2 calibration settlements are excluded.
    assert bucket["n_accept_settled"] == 4
    assert bucket["pass_at_budget"] == 0.25
    # n_events still counts every selection event, calibration included.
    assert bucket["n_events"] == 7


def test_zero_calibration_arm_aggregates_byte_identical_to_pre_fix_pin():
    """Non-static_oracle arms never emit calibration events, so their aggregates over
    the default fixture must be byte-identical to before the B4 fix. The sha256 below
    was pinned from the pre-fix working tree on 2026-07-08."""
    stream = runner.load_stream(runner.DEFAULT_FIXTURE)
    verdict = runner.run_stream(stream)
    non_oracle = {k: v for k, v in verdict["arms"].items() if k != "static_oracle"}
    blob = json.dumps(non_oracle, sort_keys=True).encode("utf-8")
    assert (
        hashlib.sha256(blob).hexdigest()
        == "6684e94c8910daa0a781867e2d5dcb0ad0ddbd7e050fad841833a78f4be6f075"
    )
    # And no zero-calibration trace carries a calibration marker at all.
    for arm in runner.default_arm_specs():
        if arm.kind == "static_oracle":
            continue
        for bucket_name, bucket_fixture in stream["buckets"].items():
            trace = arms.simulate_bucket(bucket_name, bucket_fixture, arm)
            assert all(e.side != "calibration" for e in trace.events), (arm.name, bucket_name)

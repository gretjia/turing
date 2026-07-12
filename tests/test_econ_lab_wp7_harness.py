"""WP7 acceptance tests (design doc R1.1 §7 WP7 row):

  * fixture-stream self-test (the harness runs end to end over a synthetic stream and
    produces a well-formed verdict for all five arms + the tau-sweep group);
  * single-arm deterministic replay (same input -> byte-identical output, twice);
  * the rank-inversion metric returns exactly 1 on a hand-constructed
    exactly-one-inversion fixture.

Plus supporting structural checks for the held-out differential verifier's v0 criteria
(ADR-ECON-003 Decision 2): zero shared case IDs between the accept/verify sides, and
independent implementation (the verifier module does not import the acceptor path).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"

sys.path.insert(0, str(ECON_LAB))

import arms  # noqa: E402
import inversion  # noqa: E402
import runner  # noqa: E402
from verifier.split import split_side  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ECON_LAB / "runner.py"), *args],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


# ---------------------------------------------------------------------------
# 1. fixture 流自测
# ---------------------------------------------------------------------------


def test_runner_self_test_cli_passes():
    result = _run("--self-test")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "ECON_LAB_HARNESS_SELF_TEST_PASS" in result.stdout


def test_fixture_stream_exercises_all_five_arms_and_tau_sweep():
    stream = runner.load_stream(runner.DEFAULT_FIXTURE)
    verdict = runner.run_stream(stream)

    expected_arm_names = {"main", "frozen_backup", "static_oracle", "placebo"} | {
        f"tau_sweep_{('inf' if t is None else t)}" for t in arms.TAU_SWEEP_GRID
    }
    assert set(verdict["arms"].keys()) == expected_arm_names

    for arm_name, arm_result in verdict["arms"].items():
        for bucket_name, bucket_result in arm_result["buckets"].items():
            assert bucket_result["n_accept_settled"] > 0, (arm_name, bucket_name)
            assert bucket_result["pass_at_budget"] is not None
            assert 0.0 <= bucket_result["pass_at_budget"] <= 1.0


def test_frozen_backup_arm_never_produces_an_inversion_by_construction():
    """PREREG §4 harness self-check: the frozen-backup arm's Q never updates, so
    inversion count must be identically 0; nonzero would mean a harness bug."""
    stream = runner.load_stream(runner.DEFAULT_FIXTURE)
    frozen = arms.ArmSpec(name="frozen_backup", kind="frozen_backup", tau=1.0)
    for bucket_name, bucket_fixture in stream["buckets"].items():
        trace = arms.simulate_bucket(bucket_name, bucket_fixture, frozen)
        assert inversion.count_confirmed_inversions(trace) == 0


# ---------------------------------------------------------------------------
# 2. 单臂确定性重放
# ---------------------------------------------------------------------------


def test_single_arm_deterministic_replay_is_byte_identical():
    stream = runner.load_stream(runner.DEFAULT_FIXTURE)
    main_arm = [arms.ArmSpec(name="main", kind="main", tau=1.0)]

    first = json.dumps(runner.run_stream(stream, main_arm), sort_keys=True)
    second = json.dumps(runner.run_stream(stream, main_arm), sort_keys=True)
    assert first == second


def test_cli_replay_is_byte_identical_across_two_invocations():
    first = _run("--self-test")
    second = _run("--self-test")
    assert first.returncode == 0 == second.returncode
    assert first.stdout == second.stdout


# ---------------------------------------------------------------------------
# 3. rank-inversion 度量 == 1 on hand-constructed fixture
# ---------------------------------------------------------------------------


def test_rank_inversion_metric_equals_one_on_hand_constructed_fixture():
    data = json.loads((ECON_LAB / "fixtures" / "one_inversion_bucket_trace.json").read_text())
    trace = arms.load_bucket_trace_fixture(data)
    assert inversion.count_confirmed_inversions(trace) == 1

    events = inversion.detect_confirmed_inversions(trace)
    assert len(events) == 1
    confirmed = events[0]
    assert confirmed.scaffold_id == "scaffold:sha256:aaaa0001"
    assert confirmed.displaced_scaffold_id == "scaffold:sha256:bbbb0002"
    assert confirmed.confirmed is True
    assert confirmed.p_value <= inversion.SIGNIFICANCE_ALPHA


# ---------------------------------------------------------------------------
# Held-out differential verifier v0 criteria (ADR-ECON-003 Decision 2)
# ---------------------------------------------------------------------------


def test_heldout_split_zero_shared_case_ids():
    case_ids = [f"case-{i:05d}" for i in range(500)]
    accept_ids = {c for c in case_ids if split_side(c) == "accept"}
    verify_ids = {c for c in case_ids if split_side(c) == "verify"}
    assert accept_ids.isdisjoint(verify_ids)
    assert accept_ids | verify_ids == set(case_ids)
    # sanity: split is not degenerate (both sides populated on a nontrivial sample)
    assert accept_ids and verify_ids


def test_split_is_deterministic():
    assert split_side("some-case-id") == split_side("some-case-id")


def test_independent_verifier_does_not_import_acceptor_modules():
    verifier_src = (ECON_LAB / "verifier" / "independent_verifier.py").read_text()
    split_src = (ECON_LAB / "verifier" / "split.py").read_text()
    for forbidden in ("import arms", "from arms", "import node", "from node"):
        assert forbidden not in verifier_src
        assert forbidden not in split_src


def test_independent_verifier_majority_vote():
    from verifier.independent_verifier import verify

    assert verify([1, 1, 0]) == 1
    assert verify([0, 0, 1]) == 0
    assert verify([1, 1]) == 1
    assert verify([0, 0]) == 0

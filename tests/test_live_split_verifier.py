"""WP9b acceptance tests for `tools/econ_lab/verifier/live_split_verifier.py` (ADR-ECON-003
Decision 2, point 4 -- 2026-07-07 增补, the SWE-bench v0 instantiation of the independent
verifier).

Covers, per this task's deliverable list:
  * both-side verdicts on a synthetic harness `tests_status` report (accept side all pass,
    verify side all pass -> both verdicts True; and a mixed report where each side disagrees)
  * the canary condition (accept passes, verify fails)
  * the NOT_ENOUGH_TESTS condition (verify side has zero assigned test_ids)
  * split-function determinism (same test_id -> same side, every call; and the module's
    `test_id_split_side` is the *same function object* as `verifier.split.split_side`, not a
    re-implementation -- Decision 2.4's "若 split.py 的现有签名不适配,薄封装,不重写哈希
    逻辑" instruction, satisfied here by needing no wrapper at all)

Fixture report shape is copied verbatim (field names/nesting) from a real
`swebench.harness.run_evaluation` per-instance report already on disk in this repo:
`evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02/arms/
A_deepseek_flash_pilot/scoring/logs/run_evaluation/.../matplotlib__matplotlib-23299/
report.json`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"
sys.path.insert(0, str(ECON_LAB))

from verifier import live_split_verifier as lsv  # noqa: E402
from verifier.split import ACCEPT_SIDE, VERIFY_SIDE, split_side  # noqa: E402

# Hand-picked test_ids whose held-out split side is fixed by construction of the real hash
# function (checked below, not just asserted): the first two are ACCEPT-side, the last two
# VERIFY-side.
ACCEPT_IDS = [
    "tests/test_module.py::test_case_0004",
    "tests/test_module.py::test_case_0005",
]
VERIFY_IDS = [
    "tests/test_module.py::test_case_0000",
    "tests/test_module.py::test_case_0001",
]


def test_fixture_test_ids_actually_split_the_way_this_file_assumes():
    """Guards every other test below against silent fixture drift: if `split_side`'s
    hash/domain-separator ever changed, this test (not a downstream assertion buried in a
    canary/NOT_ENOUGH_TESTS test) is what would fail first."""
    for test_id in ACCEPT_IDS:
        assert split_side(test_id) == ACCEPT_SIDE
    for test_id in VERIFY_IDS:
        assert split_side(test_id) == VERIFY_SIDE


def test_test_id_split_side_is_the_same_function_as_split_py_not_a_reimplementation():
    """Decision 2.4: 'split 粒度...从 case 换为 test_id...若 split.py 的现有签名不适配,薄
    封装,不重写哈希逻辑' -- `split_side(case_id: str) -> str` already accepts any string, so
    `live_split_verifier.test_id_split_side` is required to be the identical function object,
    not a copy/reimplementation of its hash logic."""
    assert lsv.test_id_split_side is split_side


def _tests_status(*, fail_to_pass: dict, pass_to_pass: dict) -> dict:
    empty = {"success": [], "failure": []}
    return {
        "FAIL_TO_PASS": fail_to_pass,
        "PASS_TO_PASS": pass_to_pass,
        "FAIL_TO_FAIL": empty,
        "PASS_TO_FAIL": empty,
    }


def test_both_sides_pass():
    tests_status = _tests_status(
        fail_to_pass={"success": [ACCEPT_IDS[0], VERIFY_IDS[0]], "failure": []},
        pass_to_pass={"success": [ACCEPT_IDS[1], VERIFY_IDS[1]], "failure": []},
    )
    result = lsv.judge(tests_status)
    assert result["schema"] == lsv.LIVE_SPLIT_VERIFIER_SCHEMA
    assert result["accept_verdict"] is True
    assert result["verify_verdict"] is True
    assert result["canary"] is False
    assert result["not_enough_tests"] is False
    assert result["accept_test_ids"] == sorted(ACCEPT_IDS)
    assert result["verify_test_ids"] == sorted(VERIFY_IDS)
    # Decision 2's zero-shared-ID property, re-checked at this granularity.
    assert set(result["accept_test_ids"]).isdisjoint(result["verify_test_ids"])


def test_both_sides_fail():
    tests_status = _tests_status(
        fail_to_pass={"success": [], "failure": [ACCEPT_IDS[0], VERIFY_IDS[0]]},
        pass_to_pass={"success": [], "failure": [ACCEPT_IDS[1], VERIFY_IDS[1]]},
    )
    result = lsv.judge(tests_status)
    assert result["accept_verdict"] is False
    assert result["verify_verdict"] is False
    assert result["canary"] is False  # canary requires accept True, not both-fail
    assert result["not_enough_tests"] is False


def test_canary_accept_passes_but_verify_fails():
    """The E-soundness signal (Decision 2.3/2.4): accept side all green, verify side has at
    least one failure -- 过 ∏p 但被验证器证伪."""
    tests_status = _tests_status(
        fail_to_pass={"success": [ACCEPT_IDS[0]], "failure": [VERIFY_IDS[0]]},
        pass_to_pass={"success": [ACCEPT_IDS[1]], "failure": []},
    )
    result = lsv.judge(tests_status)
    assert result["accept_verdict"] is True
    assert result["verify_verdict"] is False
    assert result["canary"] is True
    assert result["not_enough_tests"] is False


def test_not_enough_tests_when_verify_side_is_empty():
    """Decision 2.4: 'verify 侧为空(测试太少)⇒ NOT_ENOUGH_TESTS,不回灌,计数上报.'
    Constructed by using only ACCEPT-side test_ids across both grading categories."""
    tests_status = _tests_status(
        fail_to_pass={"success": [ACCEPT_IDS[0]], "failure": []},
        pass_to_pass={"success": [], "failure": []},
    )
    result = lsv.judge(tests_status)
    assert result["not_enough_tests"] is True
    assert result["verify_verdict"] is None
    assert result["verify_test_ids"] == []
    # accept side is non-empty here and passes.
    assert result["accept_verdict"] is True
    # canary cannot be asserted True when there is no verify-side data to falsify against.
    assert result["canary"] is False


def test_not_enough_tests_on_totally_empty_report():
    """Defensive edge case (not a new judgment rule, module doc): a missing/empty
    `tests_status` -- e.g. the harness itself errored before producing per-test results --
    must not crash and must not fabricate a verdict on either side."""
    assert lsv.judge(None)["not_enough_tests"] is True
    assert lsv.judge({})["not_enough_tests"] is True
    for report in (None, {}):
        result = lsv.judge(report)
        assert result["accept_verdict"] is None
        assert result["verify_verdict"] is None
        assert result["canary"] is False
        assert result["accept_test_ids"] == []
        assert result["verify_test_ids"] == []


def test_fail_to_fail_and_pass_to_fail_categories_are_not_consulted():
    """Decision 2.4 names only FAIL_TO_PASS/PASS_TO_PASS; the other two harness-report
    categories are diagnostic-only (same as the upstream harness's own `resolved`
    computation) and must not influence either verdict."""
    tests_status = {
        "FAIL_TO_PASS": {"success": [ACCEPT_IDS[0], VERIFY_IDS[0]], "failure": []},
        "PASS_TO_PASS": {"success": [], "failure": []},
        "FAIL_TO_FAIL": {"success": [], "failure": [ACCEPT_IDS[1], VERIFY_IDS[1]]},
        "PASS_TO_FAIL": {"success": [], "failure": [ACCEPT_IDS[1], VERIFY_IDS[1]]},
    }
    result = lsv.judge(tests_status)
    # Only the FAIL_TO_PASS test_ids are seen; the FAIL_TO_FAIL/PASS_TO_FAIL-only test_ids
    # never enter accept_test_ids/verify_test_ids at all.
    assert result["accept_test_ids"] == [ACCEPT_IDS[0]]
    assert result["verify_test_ids"] == [VERIFY_IDS[0]]
    assert result["accept_verdict"] is True
    assert result["verify_verdict"] is True


def test_judge_harness_error_is_fail_closed_both_sides_not_not_enough_tests():
    """Orchestrator addendum (2026-07-07, point 3): a `patch_apply_failed` (or any other
    `error_ids`) outcome has no per-test data at all -- both verdicts are False (a definite
    outcome), `not_enough_tests` stays False (this is NOT "withheld for lack of data"), and
    no canary is raised (accept and verify agree)."""
    result = lsv.judge_harness_error("patch_apply_failed")
    assert result["schema"] == lsv.LIVE_SPLIT_VERIFIER_SCHEMA
    assert result["accept_verdict"] is False
    assert result["verify_verdict"] is False
    assert result["canary"] is False
    assert result["not_enough_tests"] is False
    assert result["accept_test_ids"] == []
    assert result["verify_test_ids"] == []
    assert result["harness_error_reason"] == "patch_apply_failed"


def test_judge_harness_error_reason_is_carried_verbatim_for_any_generic_error():
    result = lsv.judge_harness_error("harness_error")
    assert result["harness_error_reason"] == "harness_error"
    assert result["accept_verdict"] is False
    assert result["verify_verdict"] is False


def test_judge_normal_path_has_harness_error_reason_none_for_uniform_shape():
    tests_status = _tests_status(
        fail_to_pass={"success": [ACCEPT_IDS[0], VERIFY_IDS[0]], "failure": []},
        pass_to_pass={"success": [], "failure": []},
    )
    assert lsv.judge(tests_status)["harness_error_reason"] is None


def test_split_determinism_across_repeated_calls():
    for test_id in ACCEPT_IDS + VERIFY_IDS:
        first = lsv.test_id_split_side(test_id)
        second = lsv.test_id_split_side(test_id)
        assert first == second
    # And determinism at the whole-`judge()` level: same input -> byte-identical dict twice.
    tests_status = _tests_status(
        fail_to_pass={"success": [ACCEPT_IDS[0], VERIFY_IDS[0]], "failure": []},
        pass_to_pass={"success": [], "failure": []},
    )
    assert lsv.judge(tests_status) == lsv.judge(tests_status)

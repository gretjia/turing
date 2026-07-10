"""WP9b -- econ_lab live independent verifier (SWE-bench v0 instantiation).

Spec source (sole authority; a missing detail is reported BLOCKED, never guessed):
  ADR-ECON-003-emergence-routing-spec-pins.md, Decision 2, point 4 (2026-07-07 增补,
  "SWE-bench 任务的 v0 实例化"):

    split 粒度 = 任务的单条测试 ID(Decision 2 第 1 条的 case_id 在 SWE-bench 语境即
    test_id)。任务的 FAIL_TO_PASS 与 PASS_TO_PASS 测试 ID 各按
    SHA256("heldout-split.v1" ‖ test_id) 首字节奇偶分 accept 侧(偶)/verify 侧(奇),
    两侧零共享。官方 harness 单次执行产出逐测试结果:accept 裁决(市场结算侧)= accept
    侧测试全过;verify 裁决 v(经济奖励/backup 侧,RoutingPriorUpdated 携带)= verify 侧
    测试全过,由独立判读脚本从 harness 原始逐测试报告判读,与 accept 判读不共享判定
    代码。金丝雀 = accept 过 ∧ verify 败比例。verify 侧为空(测试太少)⇒
    NOT_ENOUGH_TESTS,不回灌,计数上报。

This module is that "独立判读脚本" (independent reading script). It is the *only* code
in this repository that reads a real SWE-bench official-harness per-instance report's
`tests_status` block to produce a live accept/verify verdict -- `tools/econ_lab/live_driver.py`
never inlines this judgment itself (Decision 2.4's "由独立判读脚本...判读" requirement), and
this module never imports `tools/econ_lab/arms.py` / `tools/econ_lab/node.py` (the
fixture-only accept-predicate modules) or `tools/econ_lab/verifier/independent_verifier.py`
(the WP7 fixture-only differential verifier this module supersedes for real SWE-bench tasks
-- see that module's own docstring; it stays in place for the WP7 harness's synthetic
`verify_witnesses` self-tests, which this file does not touch).

Report-shape source: this module's `tests_status` schema is copied verbatim from a real
`swebench.harness.run_evaluation` per-instance report already on disk in this repo, e.g.
`evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02/arms/
A_deepseek_flash_pilot/scoring/logs/run_evaluation/.../matplotlib__matplotlib-23299/
report.json`:

    {"<instance_id>": {
        "patch_is_None": bool, "patch_exists": bool,
        "patch_successfully_applied": bool, "resolved": bool,
        "tests_status": {
            "FAIL_TO_PASS": {"success": [test_id, ...], "failure": [test_id, ...]},
            "PASS_TO_PASS": {"success": [test_id, ...], "failure": [test_id, ...]},
            "FAIL_TO_FAIL": {"success": [...], "failure": [...]},
            "PASS_TO_FAIL": {"success": [...], "failure": [...]}}}}

`judge()` below takes the inner `tests_status` dict (i.e. `report[instance_id]["tests_status"]`,
which is also exactly the shape of `live_driver.py`'s own
`score_with_official_harness(...)["tests_status"]` -- that per-instance `report.json` is a
*separate* file from the aggregated `{model_name}.{run_id}.json` report `score_with_official_
harness` also reads; see that function's own module-level doc comment for the real
swebench 4.1.0 path layout, confirmed against `~/.turingos/swebench-venv/lib/python3.11/
site-packages/swebench/harness/{run_evaluation,reporting,constants}.py`).

Only `FAIL_TO_PASS`/`PASS_TO_PASS` are consulted, per Decision 2.4's own naming (it names
only those two categories) -- `FAIL_TO_FAIL`/`PASS_TO_FAIL` are the harness's own diagnostic-
only categories, not part of the pass/fail determination either upstream (SWE-bench's own
`resolved` field is `all(FAIL_TO_PASS.success) and all(PASS_TO_PASS.success)`) or here.

`judge_harness_error()` below handles the sibling case where no per-instance report.json was
ever produced at all (the harness's own `error_ids` bucket, e.g. `EvaluationError: Patch
Apply Failed`) -- orchestrator addendum (ADR-ECON-003, 2026-07-07, point 3).

`judge_infra_null()` below (independent audit `INDEPENDENT_AUDIT_ECON_LAB_20260707.md` B2,
ADR-ECON-003 Decision 7.1, 2026-07-08) handles the sibling-of-the-sibling case: the harness
never actually *evaluated* this run at all (INCOMPLETE, or an `error_ids` outcome with no
per-instance report/log and no pinned patch-apply-failure marker -- i.e. malformed or never
written). Unlike `judge_harness_error` (a real, determinate double-fail), this is "we have
nothing to say" -- the "never fabricate a verdict" invariant wins over fail-closed here: no
settlement, no backup update.

Split-function reuse (Decision 2.4's own instruction: "切分函数应复用/对齐
tools/econ_lab/verifier/split.py 已钉的 v0 实现语义...若 split.py 的现有签名不适配,薄
封装,不重写哈希逻辑"): `split.split_side(case_id: str) -> str` already takes an arbitrary
string and applies `SHA256("heldout-split.v1" + case_id)` first-byte parity -- it needs no
wrapper at all for `test_id: str` (the signature already fits: a test_id *is* just a string,
same shape as a case_id). This module re-exports it under a `test_id`-flavored name for
readability at this file's call sites; it does not re-implement or wrap the hash.
"""
from __future__ import annotations

from typing import Any, Optional

from .split import ACCEPT_SIDE, SPLIT_DOMAIN_SEPARATOR, VERIFY_SIDE, split_side

LIVE_SPLIT_VERIFIER_SCHEMA = "econ_lab.live_split_verifier.verdict.v1"

# Decision 2.4 names exactly these two tests_status categories as grading-relevant (the same
# two categories the upstream harness's own `resolved` boolean is computed from).
GRADING_CATEGORIES = ("FAIL_TO_PASS", "PASS_TO_PASS")

# Re-export, not a re-implementation (module doc above): identical function object, no new
# hash logic. Kept as a distinct name only so call sites below read "test_id split", not
# "case_id split".
test_id_split_side = split_side

__all__ = [
    "LIVE_SPLIT_VERIFIER_SCHEMA",
    "GRADING_CATEGORIES",
    "SPLIT_DOMAIN_SEPARATOR",
    "ACCEPT_SIDE",
    "VERIFY_SIDE",
    "test_id_split_side",
    "collect_test_outcomes",
    "judge",
    "judge_harness_error",
    "judge_infra_null",
]


def collect_test_outcomes(tests_status: Optional[dict[str, Any]]) -> dict[str, bool]:
    """Flatten the harness's per-category success/failure lists into a single
    ``test_id -> passed`` map, restricted to the two grading-relevant categories.

    Defensive, not a new judgment rule: a missing/malformed ``tests_status`` (e.g. the
    harness itself errored before producing per-test results) yields an empty map, which
    `judge()` below turns into ``not_enough_tests=True`` on both sides rather than crashing
    or fabricating a verdict -- consistent with `live_driver.py`'s existing "never fabricate
    a verdict" invariant for the surrounding driver.
    """
    outcomes: dict[str, bool] = {}
    if not tests_status:
        return outcomes
    for category in GRADING_CATEGORIES:
        block = tests_status.get(category) or {}
        for test_id in block.get("success", None) or []:
            # Fail-closed across categories too: a test_id should never repeat across
            # categories in a well-formed harness report, but if it was already recorded
            # as failing by an earlier category, a later category's success list must not
            # upgrade it back to passing.
            outcomes[test_id] = outcomes.get(test_id, True)
        for test_id in block.get("failure", None) or []:
            # A test_id should never appear in both success and failure for the same
            # category in a well-formed harness report; if it does, "failure" is treated as
            # authoritative (fail-closed, never silently upgrades a failing test to passing).
            outcomes[test_id] = False
    return outcomes


def judge(tests_status: Optional[dict[str, Any]]) -> dict[str, Any]:
    """ADR-ECON-003 Decision 2.4's independent read of one task's harness report.

    Returns a dict with exactly the fields Decision 2.4 calls for:
      - accept_verdict: bool | None  -- accept-side tests all passed; None only in the
        (spec-silent) edge case where the accept side itself has zero assigned test_ids
        (e.g. a task with a single FAIL_TO_PASS test_id that happens to land on the verify
        side) -- not invented semantics, just "cannot judge an empty set", the same
        conservative null the verify side gets via `not_enough_tests`.
      - verify_verdict: bool | None  -- verify-side tests all passed; None when
        not_enough_tests is True.
      - canary: bool  -- True iff accept_verdict is True and verify_verdict is False
        (Decision 2.3's "过 ∏p 但被验证器证伪" E-soundness signal, at Decision 2.4's
        per-task-per-route granularity).
      - not_enough_tests: bool  -- True iff the verify side has zero assigned test_ids
        (Decision 2.4: "verify 侧为空(测试太少)⇒ NOT_ENOUGH_TESTS,不回灌,计数上报").
      - accept_test_ids / verify_test_ids: sorted list[str] -- the two disjoint test_id
        sets (for evidence/audit; Decision 2's "两侧 test_id 清单" zero-overlap property is
        directly checkable from these two lists).
    """
    outcomes = collect_test_outcomes(tests_status)

    accept_ids = sorted(test_id for test_id in outcomes if test_id_split_side(test_id) == ACCEPT_SIDE)
    verify_ids = sorted(test_id for test_id in outcomes if test_id_split_side(test_id) == VERIFY_SIDE)

    accept_verdict: Optional[bool] = all(outcomes[t] for t in accept_ids) if accept_ids else None
    not_enough_tests = len(verify_ids) == 0
    verify_verdict: Optional[bool] = None if not_enough_tests else all(outcomes[t] for t in verify_ids)

    canary = bool(accept_verdict is True and verify_verdict is False)

    # ADR-ECON-006: verify-side pass ratio ∈ [0,1]. Empty verify side → None (withheld).
    if not_enough_tests:
        verify_pass_fraction: Optional[float] = None
        verify_pass_count = 0
        verify_total_count = 0
    else:
        verify_pass_count = sum(1 for t in verify_ids if outcomes[t])
        verify_total_count = len(verify_ids)
        verify_pass_fraction = verify_pass_count / verify_total_count

    return {
        "schema": LIVE_SPLIT_VERIFIER_SCHEMA,
        "accept_verdict": accept_verdict,
        "verify_verdict": verify_verdict,
        "canary": canary,
        "not_enough_tests": not_enough_tests,
        "accept_test_ids": accept_ids,
        "verify_test_ids": verify_ids,
        # ADR-ECON-006 fractional reward inputs (descriptive; binary paths ignore them).
        "verify_pass_fraction": verify_pass_fraction,
        "verify_pass_count": verify_pass_count,
        "verify_total_count": verify_total_count,
        # Only ever set by `judge_harness_error` below; present here too (always None) so
        # both this module's return shapes are uniform for callers.
        "harness_error_reason": None,
    }


def judge_harness_error(reason: str) -> dict[str, Any]:
    """Orchestrator addendum (ADR-ECON-003, 2026-07-07, point 3): when the harness's own
    aggregated report buckets a task into `error_ids`, no per-instance report.json was ever
    produced (e.g. `EvaluationError: Patch Apply Failed` -- the harness never got as far as
    running any test), so there is no `tests_status` for `judge()` above to read at all.

    Pinned resolution (not this module's invention -- the addendum states it explicitly):
    both sides are judged FAIL (`accept_verdict=False`, `verify_verdict=False`) -- a
    definite, fail-closed outcome, distinct from `not_enough_tests` (which means "we have
    some data but the verify side happens to be empty"; here there is no per-test data at
    all). No canary is possible (accept and verify agree, so there is no "过 ∏p 但被验证器
    证伪" signal). `not_enough_tests` is `False` here specifically because this *is* a
    definite verdict, not a withheld one -- the caller's backup-update wiring still applies a
    normal `RoutingPriorUpdated` with `v=0`, exactly as the addendum specifies ("正常回灌
    v=0"), unlike the `NOT_ENOUGH_TESTS` path, which withholds the backup update entirely.
    """
    return {
        "schema": LIVE_SPLIT_VERIFIER_SCHEMA,
        "accept_verdict": False,
        "verify_verdict": False,
        "canary": False,
        "not_enough_tests": False,
        "accept_test_ids": [],
        "verify_test_ids": [],
        # Double-fail: no tests ran successfully → fraction 0 (ADR-ECON-006 Decision 1).
        "verify_pass_fraction": 0.0,
        "verify_pass_count": 0,
        "verify_total_count": 0,
        "harness_error_reason": reason,
    }


def judge_infra_null(reason: str) -> dict[str, Any]:
    """B2 remedy (independent audit `INDEPENDENT_AUDIT_ECON_LAB_20260707.md` B2; ADR-ECON-003
    Decision 7.1, orchestrator ruling 2026-07-08): the harness never actually *evaluated* this
    run at all -- `outcome == "INCOMPLETE"`, or an `error_ids` outcome with no per-instance
    report/log at all and no pinned patch-apply-failure marker (report malformed or never
    written). Distinct from `judge_harness_error` (a real, determinate double-fail: the harness
    *did* run and *did* determine a failure, e.g. `patch_apply_failed`/`empty_patch`) -- here
    the harness has nothing to say at all, so this must never be funneled into a fabricated
    definite verdict (the pinned `error_ids` fail-closed path was exactly B2's bug).

    `accept_verdict`/`verify_verdict` stay `None` (never settled); `not_enough_tests` stays
    `False` (that field is reserved for `judge()`'s own "some data exists, verify side is
    just empty" case -- a different condition from "no data exists at all"); `canary` stays
    `False` (no accept/verify disagreement is possible without a determination on either
    side). The caller (`live_driver.py`'s `_apply_live_split_verifier`) must not build a
    `RoutingPriorUpdated` event for this result and must not count it toward any settled
    denominator -- `infra_null=True`/`infra_null_reason` is this function's own signal for
    that, read only by this module's callers, never fed into `EconomyEvent`/tape construction.
    """
    return {
        "schema": LIVE_SPLIT_VERIFIER_SCHEMA,
        "accept_verdict": None,
        "verify_verdict": None,
        "canary": False,
        "not_enough_tests": False,
        "accept_test_ids": [],
        "verify_test_ids": [],
        "verify_pass_fraction": None,
        "verify_pass_count": 0,
        "verify_total_count": 0,
        "harness_error_reason": None,
        "infra_null": True,
        "infra_null_reason": reason,
    }

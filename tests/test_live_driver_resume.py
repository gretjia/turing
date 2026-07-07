"""WP9c -- deterministic offline tests for `live_driver.py`'s `--resume` feature.

Spec source (sole authority; no formula is invented here -- see also each function's own
docstring in `tools/econ_lab/live_driver.py`): this task's own orchestrator brief (2026-07-07,
"语义规则(orchestrator 钉死)" points 1-3) --

  1. `--resume`: for each task, in the driver's existing processing order --
     (a) `task_runs/<instance>/settlement.json` present -> replay verbatim, no recompute;
     (b) else `candidate.patch`/`worker_receipt.json` present -> never re-dispatch the worker;
         reuse the scoring report if present, else re-run scoring only (local docker, zero
         API spend);
     (c) else -> the exact fresh-run flow.
  2. An incremental checkpoint (`settlement.json`) is written after every task's settlement,
     fresh run and resume alike, and its write must not perturb `verdict.json`'s bytes.
  3. Determinism: killing a mock run after k tasks (k = 0 / a middle task / the last task)
     and then `--resume`-ing must reproduce the same uninterrupted run's verdict, byte for
     byte.

This file never invokes a real worker or a real SWE-bench Docker harness -- both are
monkeypatched with the deterministic, artifact-writing stubs in `_wp9c_live_driver_fixtures`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DRIVER_PATH = REPO / "tools" / "econ_lab" / "live_driver.py"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wp9c_live_driver_fixtures import (  # noqa: E402
    strip_volatile,
    stub_dispatch_worker_for_lineage,
    stub_score_with_official_harness,
    synthetic_packets,
    wire_stubs,
)

TASK_COUNT = 3


def _load_driver():
    spec = importlib.util.spec_from_file_location("wp9c_resume_driver_under_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    module = _load_driver()
    wire_stubs(module, monkeypatch, task_count=TASK_COUNT)
    return module


def _args(run_root: Path, *, resume: bool, max_tasks: int = TASK_COUNT) -> argparse.Namespace:
    return argparse.Namespace(
        smoke=False,
        max_tasks=max_tasks,
        out=run_root / "verdict.json",
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=run_root / "task_runs",
        report_dir=run_root / "scoring",
        resume=resume,
    )


def _normalize(verdict: dict, *, run_root: Path) -> dict:
    text = json.dumps(strip_volatile(verdict), sort_keys=True).replace(str(run_root.resolve()), "<RUN_ROOT>")
    return json.loads(text)


# ---------------------------------------------------------------------------
# Point 3: kill-at-k determinism, k in {0, 1 (middle), 2 (last)} of 3 tasks.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("k", [0, 1, 2], ids=["k=0(first)", "k=1(middle)", "k=2(last)"])
def test_resume_after_kill_at_k_matches_uninterrupted_run(tmp_path, driver, monkeypatch, k):
    # Baseline: one uninterrupted run over all TASK_COUNT tasks.
    baseline_root = tmp_path / "baseline"
    baseline_verdict = _normalize(driver.run_driver(_args(baseline_root, resume=False)), run_root=baseline_root)

    # "Killed after k tasks": a first process instance that only ever sees `max_tasks=k`
    # tasks (so it never even starts task k, simulating a kill at or before that point),
    # writing whatever on-disk state a real interrupted run would have left behind.
    killed_root = tmp_path / "killed"
    if k > 0:
        driver.run_driver(_args(killed_root, resume=False, max_tasks=k))
    else:
        # k=0: nothing has run at all yet -- not even the directory tree exists.
        (killed_root / "task_runs").mkdir(parents=True)
        (killed_root / "scoring").mkdir(parents=True)

    # Guard hard constraint A ("绝不重调 worker") for the k tasks that *did* complete: assert
    # dispatch is never called again for those instance_ids during the resumed run below.
    already_settled_instance_ids = {p["instance_id"] for p in synthetic_packets(TASK_COUNT)[:k]}

    def _guarded_dispatch(*, arm, lineage, packet, task_dir_root, run_id_prefix, deepseek_native_provider_config):
        assert packet["instance_id"] not in already_settled_instance_ids, (
            f"resume must never re-dispatch the worker for already-settled {packet['instance_id']!r}"
        )
        return stub_dispatch_worker_for_lineage(
            arm=arm,
            lineage=lineage,
            packet=packet,
            task_dir_root=task_dir_root,
            run_id_prefix=run_id_prefix,
            deepseek_native_provider_config=deepseek_native_provider_config,
        )

    monkeypatch.setattr(driver, "dispatch_worker_for_lineage", _guarded_dispatch)

    resumed_verdict = _normalize(driver.run_driver(_args(killed_root, resume=True)), run_root=killed_root)

    assert resumed_verdict == baseline_verdict, (
        f"resume after killing at k={k} tasks must reproduce the uninterrupted run byte-for-byte"
    )

    # Every task's on-disk settlement checkpoint must exist once the resumed run completes.
    for packet in synthetic_packets(TASK_COUNT):
        checkpoint_path = killed_root / "task_runs" / packet["instance_id"] / "settlement.json"
        assert checkpoint_path.exists(), f"missing settlement.json checkpoint for {packet['instance_id']!r}"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert checkpoint["schema"] == "econ_lab.live_driver.settlement_checkpoint.v1"


def test_resume_writes_no_checkpoint_bytes_into_verdict(tmp_path, driver):
    """Point 2's own "must not perturb verdict.json" clause, checked directly: a fresh run's
    verdict must be identical whether or not a `settlement.json` checkpoint happens to already
    be sitting on disk for a task the fresh run is about to (re)compute -- i.e. this driver's
    checkpoint *write* has no read-side effect on a non-`--resume` invocation."""
    root_a = tmp_path / "no_checkpoint"
    verdict_a = _normalize(driver.run_driver(_args(root_a, resume=False)), run_root=root_a)

    root_b = tmp_path / "with_stale_checkpoint"
    (root_b / "task_runs" / "fixture__repo-0001").mkdir(parents=True)
    # A deliberately wrong/stale checkpoint -- a *fresh* (non-resume) run must never read it.
    (root_b / "task_runs" / "fixture__repo-0001" / "settlement.json").write_text(
        json.dumps({"schema": "bogus", "poison": True}), encoding="utf-8"
    )
    verdict_b = _normalize(driver.run_driver(_args(root_b, resume=False)), run_root=root_b)

    assert verdict_a == verdict_b


# ---------------------------------------------------------------------------
# Point 1(b): finer-grained artifact-level reuse (no settlement.json at all for a task, but
# some subset of the underlying worker/scoring artifacts already exist on disk).
# ---------------------------------------------------------------------------


def test_resume_reuses_existing_scoring_report_without_rerunning_worker_or_harness(tmp_path, driver, monkeypatch):
    """candidate.patch + worker_receipt.json + a completed scoring report all exist, but no
    settlement.json checkpoint (e.g. the process was killed between "scoring completed" and
    "checkpoint written") -- resume must read back both artifacts, invoking neither the worker
    nor the harness again, and must reproduce the exact settlement a fresh run would."""
    baseline_root = tmp_path / "baseline"
    baseline_verdict = _normalize(driver.run_driver(_args(baseline_root, resume=False, max_tasks=1)), run_root=baseline_root)

    reuse_root = tmp_path / "reuse"
    shutil.copytree(baseline_root / "task_runs", reuse_root / "task_runs")
    shutil.copytree(baseline_root / "scoring", reuse_root / "scoring")
    # Remove exactly the settlement.json checkpoint -- everything else (patch, receipt,
    # aggregated report, per-instance report.json) stays, simulating a kill right before the
    # checkpoint write.
    (reuse_root / "task_runs" / "fixture__repo-0001" / "settlement.json").unlink()

    def _boom_dispatch(**kwargs):
        raise AssertionError("must not re-dispatch the worker when artifacts already exist")

    def _boom_score(**kwargs):
        raise AssertionError("must not re-run the harness when a scoring report already exists")

    monkeypatch.setattr(driver, "dispatch_worker_for_lineage", _boom_dispatch)
    monkeypatch.setattr(driver, "score_with_official_harness", _boom_score)

    resumed_verdict = _normalize(driver.run_driver(_args(reuse_root, resume=True, max_tasks=1)), run_root=reuse_root)
    assert resumed_verdict == baseline_verdict


def test_resume_reruns_scoring_only_when_patch_exists_but_scoring_missing(tmp_path, driver, monkeypatch):
    """candidate.patch + worker_receipt.json exist, but no scoring artifacts and no
    settlement.json (killed right after the worker dispatch completed) -- resume must reuse
    the existing patch (never re-dispatch the worker) and re-run *only* the scoring step,
    reproducing the same settlement a fresh run would."""
    baseline_root = tmp_path / "baseline"
    baseline_verdict = _normalize(driver.run_driver(_args(baseline_root, resume=False, max_tasks=1)), run_root=baseline_root)

    reuse_root = tmp_path / "reuse"
    shutil.copytree(baseline_root / "task_runs", reuse_root / "task_runs")
    # Deliberately do *not* copy the scoring/ tree at all -- simulates a kill before scoring
    # ever started.
    (reuse_root / "task_runs" / "fixture__repo-0001" / "settlement.json").unlink()

    def _boom_dispatch(**kwargs):
        raise AssertionError("must not re-dispatch the worker when candidate.patch already exists")

    monkeypatch.setattr(driver, "dispatch_worker_for_lineage", _boom_dispatch)

    score_calls = []
    original_score = stub_score_with_official_harness

    def _counting_score(**kwargs):
        score_calls.append(kwargs["instance_id"])
        return original_score(**kwargs)

    monkeypatch.setattr(driver, "score_with_official_harness", _counting_score)

    resumed_verdict = _normalize(driver.run_driver(_args(reuse_root, resume=True, max_tasks=1)), run_root=reuse_root)
    assert resumed_verdict == baseline_verdict
    assert score_calls == ["fixture__repo-0001"], "scoring must be re-run exactly once when no report exists yet"


def test_resume_with_nothing_on_disk_falls_back_to_full_flow(tmp_path, driver):
    """No settlement.json, no candidate.patch, no worker_receipt.json, nothing at all --
    resume must fall back to the exact fresh-run flow (hard constraint A: "全缺 -> 正常全流程"),
    for every task, and still match an uninterrupted fresh run byte for byte."""
    baseline_root = tmp_path / "baseline"
    baseline_verdict = _normalize(driver.run_driver(_args(baseline_root, resume=False)), run_root=baseline_root)

    empty_root = tmp_path / "empty_resume"
    resumed_verdict = _normalize(driver.run_driver(_args(empty_root, resume=True)), run_root=empty_root)
    assert resumed_verdict == baseline_verdict

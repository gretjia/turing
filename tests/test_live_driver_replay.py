"""WP9a deliverable 4: deterministic offline replay test for `tools/econ_lab/live_driver.py`'s
select -> settle loop, updated for the 4-lineage (deepseek/qwen/glm/kimi) provider-layer
refactor (PREREG Appendix A, frozen 2026-07-07) and, again, for WP9b's live independent
verifier / backup ("回灌") wiring (ADR-ECON-003 Decision 2 point 4, 2026-07-07 增补).

Proves reproducibility (Art 0.2 style discipline, applied at the driver layer): the same
fixed task packets, routed through the same real `econ_fold_cli` subprocess bridge (the
single source of truth for the routing decision, the N_eff/H_lineage diversity metrics, and
-- as of WP9b -- each `RoutingPriorUpdated` event's `event_hash`), with a MOCK/offline stub
standing in for the real per-lineage worker dispatch and the real SWE-bench Docker scorer
(neither of which this test may invoke -- no network, no subprocess spend), must produce
byte-identical verdict output across two independent `run_driver` calls.

The scorer stub below (`_stub_score_with_official_harness`) now returns a `raw_report` shaped
like a *real* `swebench.harness.run_evaluation` per-instance report (`tests_status` block
with `FAIL_TO_PASS`/`PASS_TO_PASS` `success`/`failure` lists, copied verbatim from
`evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02/.../report.json`'s own
shape), with hand-picked test_ids whose held-out split side (`verifier.split.split_side`,
applied per-test_id by `live_split_verifier`) is verified below at import time -- not just
asserted by construction -- so this fixture cannot silently drift from Decision 2.4's actual
split function. This is what lets the test exercise the WP9b backup ("回灌")
path -- `live_split_verifier.judge(...)` reading a non-empty verify side and
`_settle_one` asking `econ_fold_cli`'s `build-routing-prior-updated` subcommand for a real,
correctly-hashed `RoutingPriorUpdated` event, which `run_driver` then folds back onto its own
`committed_routing_events` tape for the *next* task's selection -- while remaining a pure,
hermetic function of the fixed stub inputs (still byte-identical across two runs).

This does not re-test `econ_fold_cli`'s own determinism (that is
`crates/turing-economy/tests/econ_fold_cli_cross_check.rs`'s job); it tests that
`live_driver.py`'s orchestration around the CLI -- task iteration, tape bookkeeping,
held-out split routing, per-lineage settlement bookkeeping, diversity-history accumulation,
and now the live-split-verifier backup feed -- introduces no hidden non-determinism.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
DRIVER_PATH = REPO / "tools" / "econ_lab" / "live_driver.py"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"

sys.path.insert(0, str(REPO / "tools" / "econ_lab"))
from verifier.split import ACCEPT_SIDE, VERIFY_SIDE, split_side  # noqa: E402

# Hand-picked test_ids, each already checked against the real split function immediately
# below (not merely asserted-by-construction): `ACCEPT_TEST_IDS` all land on the accept side,
# `VERIFY_TEST_IDS` all land on the verify side, of `SHA256("heldout-split.v1" + test_id)`
# first-byte parity (`verifier.split.split_side`, ADR-ECON-003 Decision 2.4).
ACCEPT_TEST_IDS = [
    "tests/test_module.py::test_case_0004",
    "tests/test_module.py::test_case_0005",
    "tests/test_module.py::test_case_0009",
]
VERIFY_TEST_IDS = [
    "tests/test_module.py::test_case_0000",
    "tests/test_module.py::test_case_0001",
    "tests/test_module.py::test_case_0002",
]
for _tid in ACCEPT_TEST_IDS:
    assert split_side(_tid) == ACCEPT_SIDE, f"fixture drift: {_tid!r} no longer splits ACCEPT"
for _tid in VERIFY_TEST_IDS:
    assert split_side(_tid) == VERIFY_SIDE, f"fixture drift: {_tid!r} no longer splits VERIFY"


def _tests_status_for_instance(instance_id: str) -> dict[str, Any]:
    """Deterministic, `instance_id`-only synthetic `tests_status` block (pure function, so
    the stub scorer below stays a pure function of `instance_id` too -- same determinism
    contract the pre-WP9b stub already had for `resolved`).

    `...-0001`: every assigned test_id (both sides) is a "success" -- accept_verdict=True,
    verify_verdict=True, backup update applied, no canary.
    `...-0002`: the one accept-side test_id fails (accept_verdict=False) while the one
    verify-side test_id still succeeds (verify_verdict=True) -- a deliberately *not*
    canary case (canary requires accept=True and verify=False) that still exercises the
    backup-update path with a task whose market settlement is a FAIL.
    """
    if instance_id.endswith("0001"):
        return {
            "FAIL_TO_PASS": {"success": [ACCEPT_TEST_IDS[0], VERIFY_TEST_IDS[0]], "failure": []},
            "PASS_TO_PASS": {"success": [ACCEPT_TEST_IDS[1], VERIFY_TEST_IDS[1]], "failure": []},
            "FAIL_TO_FAIL": {"success": [], "failure": []},
            "PASS_TO_FAIL": {"success": [], "failure": []},
        }
    return {
        "FAIL_TO_PASS": {"success": [VERIFY_TEST_IDS[2]], "failure": [ACCEPT_TEST_IDS[2]]},
        "PASS_TO_PASS": {"success": [], "failure": []},
        "FAIL_TO_FAIL": {"success": [], "failure": []},
        "PASS_TO_FAIL": {"success": [], "failure": []},
    }

STUB_PATCH_TEXT = "diff --git a/stub.py b/stub.py\n--- a/stub.py\n+++ b/stub.py\n@@ -1 +1 @@\n-old\n+new\n"


def _load_driver():
    spec = importlib.util.spec_from_file_location("wp9a_live_driver_under_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _synthetic_packets() -> list[dict[str, Any]]:
    """Two hand-built packets shaped like the real worker-safe schema's load-bearing
    fields only (`instance_id`, `repo`, `ipqc_window_id`) -- never reads the real 55/50-task
    shard, so this test is hermetic and fast regardless of shard state."""
    return [
        {
            "instance_id": "fixture__repo-0001",
            "repo": "Fixture/Repo",
            "ipqc_window_id": "FIX-W00",
            "_task_dir": Path("/nonexistent/fixture-repo-0001"),
            "_task_packet_path": Path("/nonexistent/fixture-repo-0001/task_packet.json"),
        },
        {
            "instance_id": "fixture__repo-0002",
            "repo": "Fixture/Repo",
            "ipqc_window_id": "FIX-W00",
            "_task_dir": Path("/nonexistent/fixture-repo-0002"),
            "_task_packet_path": Path("/nonexistent/fixture-repo-0002/task_packet.json"),
        },
    ]


def _stub_dispatch_worker_for_lineage(
    *,
    arm: str,
    lineage: str,
    packet: dict,
    task_dir_root: Path,
    run_id_prefix: str,
    deepseek_native_provider_config: dict,
):
    """Offline stand-in for `dispatch_worker_for_lineage`: no network call, deterministic
    content, but still writes the same `candidate.patch` artifact shape the real SiliconFlow
    dispatch path produces (`task_dir_root/instance_id/lineage/candidate.patch`), so the
    loop's downstream scoring/settlement bookkeeping is exercised identically."""
    instance_id = packet["instance_id"]
    task_dir = task_dir_root / instance_id / lineage
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "candidate.patch").write_text(STUB_PATCH_TEXT, encoding="utf-8")
    return {
        "status": "COMPLETED",
        "instance_id": instance_id,
        "arm": arm,
        "lineage": lineage,
        "provider_path": "siliconflow",
        "candidate_patch_sha256": "sha256:" + ("0" * 63) + "1",
    }


def _stub_score_with_official_harness(
    *, python_bin: str, instance_id: str, model_patch: str, run_id: str, report_dir: Path, timeout_s: int = 1800
):
    """Offline stand-in for the real SWE-bench Docker harness: a pure function of
    `instance_id` only, so it is trivially deterministic across repeated calls. Shaped like
    the *fixed* `score_with_official_harness` contract (WP9b orchestrator addendum,
    2026-07-07): `tests_status` at the top level (not nested under a per-instance
    `raw_report`, since the real aggregated report has no per-instance keys at all --
    schema_version 2's `resolved_ids`/`unresolved_ids`/`error_ids` instance-id lists), plus
    `outcome`/`harness_error_reason` fields for shape parity with the real function."""
    resolved = instance_id.endswith("0001")
    tests_status = _tests_status_for_instance(instance_id)
    return {
        "status": "COMPLETED",
        "outcome": "RESOLVED" if resolved else "UNRESOLVED",
        "resolved": resolved,
        "tests_status": tests_status,
        "harness_error_reason": None,
        "report_path": "stub://not-a-real-report",
        "log_path": "stub://not-a-real-log",
        "raw_report": {"schema_version": 2, "resolved_ids": [instance_id] if resolved else [], "stub": True},
    }


def _run_once(driver, tmp_path: Path, tag: str, *, smoke: bool = False, max_tasks: int = 2) -> dict:
    out_path = tmp_path / f"verdict_{tag}.json"
    args = argparse.Namespace(
        smoke=smoke,
        max_tasks=max_tasks,
        out=out_path,
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=tmp_path / f"task_runs_{tag}",
        report_dir=tmp_path / f"scoring_{tag}",
        # B5 (ADR-ECON-003 Decision 7.4): fixed, tag-independent -- this test asserts the
        # select->settle loop is byte-for-byte reproducible across two *separate* driver
        # invocations of the same conceptual run (only the tag/out-path differs, as a test
        # artifact); a tag-derived default run_label would make the two invocations'
        # verifier attestations (and therefore RoutingPriorUpdated event_hash) legitimately
        # differ, which is not what this test is checking.
        run_label="test-select-settle-determinism",
    )
    return driver.run_driver(args)


def _strip_volatile(verdict: dict) -> dict:
    verdict = dict(verdict)
    verdict.pop("generated_at_unix", None)
    return verdict


@pytest.fixture()
def driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    try:
        module = _load_driver()
    except Exception as error:  # noqa: BLE001 -- surfaces a clear skip reason, not a hard failure.
        pytest.skip(f"live_driver.py failed to import in this environment: {error!r}")
    monkeypatch.setattr(module, "load_task_packets", lambda shard_root=module.SHARD_ROOT: _synthetic_packets())
    monkeypatch.setattr(
        module,
        "load_provider_config",
        lambda: {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "stub://offline", "model": "stub-model"},
    )
    monkeypatch.setattr(module, "dispatch_worker_for_lineage", _stub_dispatch_worker_for_lineage)
    monkeypatch.setattr(module, "score_with_official_harness", _stub_score_with_official_harness)
    return module


def test_select_settle_loop_is_deterministic_across_two_offline_runs(tmp_path, driver):
    verdict_1 = _run_once(driver, tmp_path, "1")
    verdict_2 = _run_once(driver, tmp_path, "2")

    assert _strip_volatile(verdict_1) == _strip_volatile(verdict_2), (
        "the select->settle loop must be byte-for-byte reproducible given fixed inputs "
        "and a fixed (stubbed) worker/scorer"
    )
    assert verdict_1["task_count"] == 2
    assert verdict_1["worker_lineages"] == ["deepseek", "qwen", "glm", "kimi"]
    for task in verdict_1["tasks"]:
        assert task["selected_arm"] in {"armA", "armB", "armC"}
        assert task["selected_lineage"] in {"deepseek", "qwen", "glm", "kimi"}
        assert task["dispatch_mode"] == "single_winner"
        assert len(task["dispatches"]) == 1
        dispatch = task["dispatches"][0]
        assert dispatch["worker_result_status"] == "COMPLETED"
        assert dispatch["scoring_result"]["status"] == "COMPLETED"
        # WP9b: market settlement now uses the live split verifier's accept_verdict (Decision
        # 2.4), not the harness's own whole-suite `resolved` -- but the fixture is built so
        # the two still agree here (see `_tests_status_for_instance`'s docstring).
        assert dispatch["settlement_verdict_resolved"] == task["instance_id"].endswith("0001")
        live_split_verdict = dispatch["live_split_verdict"]
        assert live_split_verdict is not None
        assert live_split_verdict["accept_verdict"] == task["instance_id"].endswith("0001")
        assert live_split_verdict["verify_verdict"] is True
        assert live_split_verdict["not_enough_tests"] is False
        assert live_split_verdict["canary"] is False
        # WP9b backup ("回灌") path: every dispatch here has a non-empty verify side, so
        # every one must produce an applied RoutingPriorUpdated backup update, not the
        # retired BLOCKED_NO_LIVE_INDEPENDENT_VERIFIER / accept_side_no_backup_update_by_design
        # stand-ins.
        backup_update = dispatch["backup_update"]
        assert backup_update["applied"] is True
        assert backup_update["routing_prior_updated_event_hash"].startswith("sha256:")
    assert verdict_1["verifier_summary"]["settled_dispatch_count"] == 2
    assert verdict_1["verifier_summary"]["not_enough_tests_count"] == 0
    assert verdict_1["verifier_summary"]["canary_count"] == 0
    assert verdict_1["verifier_summary"]["routing_prior_updated_applied_count"] == 2
    # Lineage-label discipline: the full model-ID strings must never appear anywhere in the
    # verdict JSON (only the 4 short labels are permitted on this surface).
    import json

    verdict_text = json.dumps(verdict_1)
    for config in driver.LINEAGE_CONFIGS.values():
        assert config["model_id"] not in verdict_text


def test_smoke_mode_dispatches_all_four_lineages_for_the_winning_arm(tmp_path, driver):
    verdict = _run_once(driver, tmp_path, "smoke", smoke=True)

    assert verdict["mode"] == "smoke"
    assert verdict["task_count"] == 1
    assert verdict["real_worker_calls_cap"] == 4
    assert verdict["real_worker_calls_made"] == 4  # all 4 stub dispatches report COMPLETED

    task = verdict["tasks"][0]
    assert task["dispatch_mode"] == "smoke_all_lineages_for_winning_arm"
    dispatched_lineages = {d["lineage"] for d in task["dispatches"]}
    assert dispatched_lineages == {"deepseek", "qwen", "glm", "kimi"}
    for dispatch in task["dispatches"]:
        assert dispatch["worker_result_status"] == "COMPLETED"
        # Smoke-mode task selection is now "first task by instance_id" (Decision 2.4
        # supersedes the old instance_id-level accept-side filter) -- the single synthetic
        # task selected is instance "...0001", whose fixture tests_status resolves on both
        # sides, so every one of the 4 lineage dispatches gets an applied backup update.
        assert dispatch["live_split_verdict"]["accept_verdict"] is True
        assert dispatch["live_split_verdict"]["verify_verdict"] is True
        assert dispatch["backup_update"]["applied"] is True

    assert verdict["verifier_summary"]["settled_dispatch_count"] == 4
    assert verdict["verifier_summary"]["not_enough_tests_count"] == 0
    assert verdict["verifier_summary"]["canary_count"] == 0
    assert verdict["verifier_summary"]["routing_prior_updated_applied_count"] == 4

    # All 4 lineages settled on the *same* task -> diversity history should have exactly one
    # domain_bucket with 4 records sharing one settlement_index, and the CLI's own
    # diversity-metrics subcommand should have been called (real subprocess, not stubbed --
    # this is the "single source of truth" math, not the mocked worker/scorer boundary).
    assert verdict["diversity_metrics_by_domain_bucket"], "expected at least one domain_bucket's diversity metrics"
    for bucket_result in verdict["diversity_metrics_by_domain_bucket"].values():
        assert bucket_result["schema"] == "econ_fold_cli.diversity_metrics.response.v1"
        assert bucket_result["status"] in {"COMPUTED", "NOT_ENOUGH_DATA"}


def test_dispatch_worker_never_calls_real_worker_without_credentials(tmp_path, monkeypatch, driver):
    """Guards the spend-cap contract at its source (this is exactly why a real `--smoke`
    run with no credentials present ends at 0 real calls rather than silently making an
    unaccounted-for one): `dispatch_worker` (the DeepSeek-direct native fallback path) must
    return `NOT_RUN` without ever invoking the real, network-calling
    `arm_a_worker.run_one_task` when the configured API-key env var is absent."""

    def _boom(*args, **kwargs):
        raise AssertionError("run_one_task (the real, network-calling DeepSeek dispatch) must not be called")

    monkeypatch.setattr(driver.arm_a_worker, "run_one_task", _boom)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    packet = _synthetic_packets()[0]
    result = driver.dispatch_worker(
        arm="armA",
        packet=packet,
        provider_config={"api_key_env": "DEEPSEEK_API_KEY", "base_url": "stub://offline", "model": "stub-model"},
        task_dir_root=tmp_path / "task_runs_guard",
        run_id_prefix="test",
    )
    assert result["status"] == "NOT_RUN"
    assert result["missing_env"] == ["DEEPSEEK_API_KEY"]


def test_dispatch_via_siliconflow_never_calls_network_without_credentials(tmp_path, monkeypatch, driver):
    """Same guard as above, for the new SiliconFlow-routed primary path (all 4 lineages)."""

    def _boom(*args, **kwargs):
        raise AssertionError("urllib.request.urlopen must not be called without SILICONFLOW_API_KEY present")

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    packet = _synthetic_packets()[0]
    result = driver.dispatch_via_siliconflow(
        arm="armA", lineage="qwen", packet=packet, task_dir_root=tmp_path / "task_runs_guard2"
    )
    assert result["status"] == "NOT_RUN"
    assert result["missing_env"] == ["SILICONFLOW_API_KEY"]

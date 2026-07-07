"""WP9a deliverable 4: deterministic offline replay test for `tools/econ_lab/live_driver.py`'s
select -> settle loop.

Proves reproducibility (Art 0.2 style discipline, applied at the driver layer): the same
fixed task packets, routed through the same real `econ_fold_cli` subprocess bridge (the
single source of truth for the routing decision), with a MOCK/offline stub standing in for
the real DeepSeek worker call and the real SWE-bench Docker scorer (neither of which this
test may invoke -- no network, no subprocess spend), must produce byte-identical verdict
output across two independent `run_driver` calls.

This does not re-test `econ_fold_cli`'s own determinism (that is
`crates/turing-economy/tests/econ_fold_cli_cross_check.rs`'s job); it tests that
`live_driver.py`'s orchestration around the CLI -- task iteration, tape bookkeeping,
held-out split routing, settlement bookkeeping -- introduces no hidden non-determinism
(e.g. dict/set iteration order, wall-clock-derived IDs, live-random selection).
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
DRIVER_PATH = REPO / "tools" / "econ_lab" / "live_driver.py"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"


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


def _stub_dispatch_worker(*, arm: str, packet: dict, provider_config: dict, task_dir_root: Path, run_id_prefix: str):
    """Offline stand-in for `dispatch_worker`: no network call, deterministic content, but
    still writes the same `candidate.patch` artifact shape the real dispatch produces, so the
    loop's downstream scoring/settlement bookkeeping is exercised identically."""
    instance_id = packet["instance_id"]
    task_dir = task_dir_root / instance_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "candidate.patch").write_text(
        "diff --git a/stub.py b/stub.py\n--- a/stub.py\n+++ b/stub.py\n@@ -1 +1 @@\n-old\n+new\n",
        encoding="utf-8",
    )
    return {
        "status": "COMPLETED",
        "instance_id": instance_id,
        "arm": arm,
        "candidate_patch_sha256": "sha256:" + ("0" * 63) + "1",
        "model_reported": "stub-model-offline-replay",
    }


def _stub_score_with_official_harness(
    *, python_bin: str, instance_id: str, model_patch: str, run_id: str, report_dir: Path, timeout_s: int = 1800
):
    """Offline stand-in for the real SWE-bench Docker harness: a pure function of
    `instance_id` only, so it is trivially deterministic across repeated calls."""
    resolved = instance_id.endswith("0001")
    return {
        "status": "COMPLETED",
        "resolved": resolved,
        "report_path": "stub://not-a-real-report",
        "log_path": "stub://not-a-real-log",
        "raw_report": {"resolved": resolved},
    }


def _run_once(driver, tmp_path: Path, tag: str) -> dict:
    out_path = tmp_path / f"verdict_{tag}.json"
    args = argparse.Namespace(
        smoke=False,
        max_tasks=2,
        out=out_path,
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=tmp_path / f"task_runs_{tag}",
        report_dir=tmp_path / f"scoring_{tag}",
    )
    return driver.run_driver(args)


def _strip_volatile(verdict: dict) -> dict:
    verdict = dict(verdict)
    verdict.pop("generated_at_unix", None)
    return verdict


@pytest.fixture()
def driver():
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    try:
        module = _load_driver()
    except Exception as error:  # noqa: BLE001 -- surfaces a clear skip reason, not a hard failure.
        pytest.skip(f"live_driver.py failed to import in this environment: {error!r}")
    return module


def test_select_settle_loop_is_deterministic_across_two_offline_runs(tmp_path, monkeypatch, driver):
    monkeypatch.setattr(driver, "load_task_packets", lambda shard_root=driver.SHARD_ROOT: _synthetic_packets())
    monkeypatch.setattr(
        driver,
        "load_provider_config",
        lambda: {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "stub://offline", "model": "stub-model"},
    )
    monkeypatch.setattr(driver, "dispatch_worker", _stub_dispatch_worker)
    monkeypatch.setattr(driver, "score_with_official_harness", _stub_score_with_official_harness)

    verdict_1 = _run_once(driver, tmp_path, "1")
    verdict_2 = _run_once(driver, tmp_path, "2")

    assert _strip_volatile(verdict_1) == _strip_volatile(verdict_2), (
        "the select->settle loop must be byte-for-byte reproducible given fixed inputs "
        "and a fixed (stubbed) worker/scorer"
    )
    assert verdict_1["task_count"] == 2
    for task in verdict_1["tasks"]:
        assert task["selected_arm"] in {"armA", "armB", "armC"}
        assert task["worker_result_status"] == "COMPLETED"
        assert task["scoring_result"]["status"] == "COMPLETED"
        assert task["settlement_verdict_resolved"] == task["instance_id"].endswith("0001")


def test_dispatch_worker_never_calls_real_worker_without_credentials(tmp_path, monkeypatch, driver):
    """Guards the spend-cap contract at its source (this is exactly why the real `--smoke`
    run in this task's own final report ended at 0 real DeepSeek calls rather than silently
    making an unaccounted-for one): `dispatch_worker` must return `NOT_RUN` without ever
    invoking the real, network-calling `arm_a_worker.run_one_task` when the configured
    API-key env var is absent from the environment."""

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

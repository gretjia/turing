"""Crash-hardening regression tests for `tools/econ_lab/live_driver.py` (2026-07-07 fixes).

Every fix under test here is error/crash-path only -- the happy path's verdict bytes are
separately guarded by `tests/test_live_driver_head_parity.py` (fresh-run byte parity against
the pre-WP9c anchor commit) and `tests/test_live_driver_resume.py` (resume determinism).
Covered contracts, each matching the fixed function's own docstring:

  1. A truncated `settlement.json` checkpoint (killed run's partial write) degrades to "no
     checkpoint": `--resume` proceeds via artifact-level reconstruction, never crashes.
     (`_load_settlement_checkpoint`; `_write_settlement_checkpoint` is now atomic too.)
  2. A truncated `worker_receipt.json` makes `_reconstruct_worker_result_from_artifacts`
     return `None` ("no artifact" -> re-dispatch path), on both the siliconflow and the
     deepseek-direct-fallback artifact layouts.
  3. Resume tamper guard: a reused aggregated scoring report must correspond to the current
     `candidate.patch` (cross-checked against `predictions.jsonl`'s recorded `model_patch`
     sha256); a tampered patch or unreadable predictions file forces a re-score.
  4. A truncated aggregated report makes `_read_scoring_report` return `None` (treated as
     absent -> re-score), never crash.
  5. `call_cli` re-raises `subprocess.TimeoutExpired` as the same RuntimeError shape the
     nonzero-exit branch uses (subcommand + timeout named).
  6. `load_provider_config` returns `None` when `~/.turingos/provider-profiles.json` is
     absent, and `dispatch_worker_for_lineage` reports the deepseek-direct fallback as
     NOT_RUN with a "provider config missing" detail instead of crashing.

This file never invokes a real worker or a real SWE-bench Docker harness -- both are
monkeypatched with the deterministic, artifact-writing stubs in `_wp9c_live_driver_fixtures`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DRIVER_PATH = REPO / "tools" / "econ_lab" / "live_driver.py"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wp9c_live_driver_fixtures import (  # noqa: E402
    STUB_PATCH_TEXT,
    strip_volatile,
    stub_score_with_official_harness,
    wire_stubs,
)

INSTANCE_ID = "fixture__repo-0001"
TAMPERED_PATCH_TEXT = STUB_PATCH_TEXT.replace("+new\n", "+tampered\n")
assert TAMPERED_PATCH_TEXT != STUB_PATCH_TEXT


def _load_driver():
    spec = importlib.util.spec_from_file_location("crash_hardening_driver_under_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def driver(monkeypatch):
    """Fully-wired driver (offline stubs, 1 synthetic task) for run_driver-level tests."""
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    module = _load_driver()
    wire_stubs(module, monkeypatch, task_count=1)
    return module


@pytest.fixture()
def driver_unit():
    """Bare module load (no stubs, no CLI requirement) for unit-level tests of single
    functions that never touch `econ_fold_cli` or `run_driver`."""
    return _load_driver()


def _args(run_root: Path, *, resume: bool, max_tasks: int = 1) -> argparse.Namespace:
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
        # B5 (ADR-ECON-003 Decision 7.4): fixed, run_root-independent -- see the identical
        # note in test_live_driver_resume.py's own `_args`; these crash-hardening tests
        # compare a "baseline" run against a separately-rooted "killed"/corrupted-then-
        # resumed run of the same conceptual scenario.
        run_label="test-wp9c-crash-hardening",
    )


def _normalize(verdict: dict, *, run_root: Path) -> dict:
    text = json.dumps(strip_volatile(verdict), sort_keys=True).replace(str(run_root.resolve()), "<RUN_ROOT>")
    return json.loads(text)


def _truncate_file(path: Path) -> None:
    """Simulate a killed process's partial write: keep only the first half of the bytes
    (all these artifacts are multi-line JSON, so half of one is never valid JSON)."""
    text = path.read_text(encoding="utf-8")
    truncated = text[: len(text) // 2]
    assert truncated
    with pytest.raises(json.JSONDecodeError):
        json.loads(truncated)
    path.write_text(truncated, encoding="utf-8")


def _boom_dispatch(**kwargs):
    raise AssertionError("must not re-dispatch the worker when intact artifacts already exist")


# ---------------------------------------------------------------------------
# 1. Truncated settlement.json -> resume proceeds via artifact reconstruction.
# ---------------------------------------------------------------------------


def test_truncated_settlement_checkpoint_degrades_to_artifact_reconstruction(tmp_path, driver, monkeypatch):
    baseline_root = tmp_path / "baseline"
    baseline_verdict = _normalize(driver.run_driver(_args(baseline_root, resume=False)), run_root=baseline_root)

    killed_root = tmp_path / "killed"
    driver.run_driver(_args(killed_root, resume=False))
    checkpoint_path = killed_root / "task_runs" / INSTANCE_ID / "settlement.json"
    _truncate_file(checkpoint_path)

    # Worker/scoring artifacts are all intact, so the resume must reconstruct from them
    # (never re-dispatch) despite the unreadable checkpoint -- and never crash on it.
    monkeypatch.setattr(driver, "dispatch_worker_for_lineage", _boom_dispatch)
    resumed_verdict = _normalize(driver.run_driver(_args(killed_root, resume=True)), run_root=killed_root)
    assert resumed_verdict == baseline_verdict

    # The resumed run must have rewritten a valid checkpoint over the truncated one.
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["schema"] == "econ_lab.live_driver.settlement_checkpoint.v1"


def test_load_settlement_checkpoint_returns_none_on_truncated_file(tmp_path, driver_unit):
    task_dir = tmp_path / "task_runs" / INSTANCE_ID
    task_dir.mkdir(parents=True)
    (task_dir / "settlement.json").write_text('{"schema": "econ_lab.live_driver.settle', encoding="utf-8")
    assert driver_unit._load_settlement_checkpoint(tmp_path / "task_runs", INSTANCE_ID) is None


# ---------------------------------------------------------------------------
# 2. Truncated worker_receipt.json -> reconstruction returns None (re-dispatch path).
# ---------------------------------------------------------------------------


def test_truncated_worker_receipt_makes_reconstruction_return_none(tmp_path, driver_unit):
    task_dir_root = tmp_path / "task_runs"
    siliconflow_dir = task_dir_root / INSTANCE_ID / "qwen"
    siliconflow_dir.mkdir(parents=True)
    (siliconflow_dir / "candidate.patch").write_text(STUB_PATCH_TEXT, encoding="utf-8")
    (siliconflow_dir / "worker_receipt.json").write_text('{"schema_id": "turingos.wp9a', encoding="utf-8")

    assert (
        driver_unit._reconstruct_worker_result_from_artifacts(
            task_dir_root=task_dir_root, instance_id=INSTANCE_ID, arm="armA", lineage="qwen"
        )
        is None
    )


def test_truncated_fallback_worker_receipt_makes_reconstruction_return_none(tmp_path, driver_unit):
    task_dir_root = tmp_path / "task_runs"
    fallback_dir = task_dir_root / "deepseek_direct_fallback" / INSTANCE_ID
    fallback_dir.mkdir(parents=True)
    (fallback_dir / "candidate.patch").write_text(STUB_PATCH_TEXT, encoding="utf-8")
    (fallback_dir / "worker_receipt.json").write_text('{"status": "COMPL', encoding="utf-8")

    assert (
        driver_unit._reconstruct_worker_result_from_artifacts(
            task_dir_root=task_dir_root, instance_id=INSTANCE_ID, arm="armA", lineage="deepseek"
        )
        is None
    )


# ---------------------------------------------------------------------------
# 3. Resume tamper guard: tampered candidate.patch vs existing report -> re-score.
# ---------------------------------------------------------------------------


def test_tampered_candidate_patch_forces_rescoring_on_resume(tmp_path, driver, monkeypatch):
    run_root = tmp_path / "run"
    driver.run_driver(_args(run_root, resume=False))
    (run_root / "task_runs" / INSTANCE_ID / "settlement.json").unlink()
    # Tamper the patch out from under the existing (otherwise fully intact) scoring report.
    patch_paths = list((run_root / "task_runs" / INSTANCE_ID).glob("*/candidate.patch"))
    assert len(patch_paths) == 1
    patch_paths[0].write_text(TAMPERED_PATCH_TEXT, encoding="utf-8")

    monkeypatch.setattr(driver, "dispatch_worker_for_lineage", _boom_dispatch)
    score_calls: list[str] = []

    def _counting_score(**kwargs):
        score_calls.append(kwargs["instance_id"])
        return stub_score_with_official_harness(**kwargs)

    monkeypatch.setattr(driver, "score_with_official_harness", _counting_score)

    verdict = driver.run_driver(_args(run_root, resume=True))
    assert score_calls == [INSTANCE_ID], "a report/patch mismatch must trigger exactly one re-score"
    dispatch = verdict["tasks"][0]["dispatches"][0]
    assert dispatch["scoring_result"]["status"] == "COMPLETED"


def test_reused_report_matches_current_patch_unit(tmp_path, driver_unit):
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    predictions_path = report_dir / "predictions.jsonl"

    # No predictions.jsonl at all -> unreadable -> False (fall back to re-scoring).
    assert not driver_unit._reused_report_matches_current_patch(
        report_dir=report_dir, instance_id=INSTANCE_ID, model_patch=STUB_PATCH_TEXT
    )

    row = {"instance_id": INSTANCE_ID, "model_name_or_path": "wp9a-live-driver", "model_patch": STUB_PATCH_TEXT}
    predictions_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert driver_unit._reused_report_matches_current_patch(
        report_dir=report_dir, instance_id=INSTANCE_ID, model_patch=STUB_PATCH_TEXT
    )
    assert not driver_unit._reused_report_matches_current_patch(
        report_dir=report_dir, instance_id=INSTANCE_ID, model_patch=TAMPERED_PATCH_TEXT
    )
    # Row for a different instance only -> no record for this one -> False.
    assert not driver_unit._reused_report_matches_current_patch(
        report_dir=report_dir, instance_id="fixture__repo-0002", model_patch=STUB_PATCH_TEXT
    )

    predictions_path.write_text('{"instance_id": "fixture__repo-0001", "model_pat', encoding="utf-8")
    assert not driver_unit._reused_report_matches_current_patch(
        report_dir=report_dir, instance_id=INSTANCE_ID, model_patch=STUB_PATCH_TEXT
    )


# ---------------------------------------------------------------------------
# 4. Truncated aggregated report -> _read_scoring_report returns None -> re-score.
# ---------------------------------------------------------------------------


def test_truncated_aggregated_report_treated_as_absent_and_rescored(tmp_path, driver, monkeypatch):
    baseline_root = tmp_path / "baseline"
    baseline_verdict = _normalize(driver.run_driver(_args(baseline_root, resume=False)), run_root=baseline_root)

    run_root = tmp_path / "run"
    driver.run_driver(_args(run_root, resume=False))
    (run_root / "task_runs" / INSTANCE_ID / "settlement.json").unlink()
    report_paths = list((run_root / "scoring" / INSTANCE_ID).glob("*/wp9a-live-driver.*.json"))
    assert len(report_paths) == 1
    _truncate_file(report_paths[0])

    # Unit-level contract first: the truncated report reads back as "absent".
    report_dir = report_paths[0].parent
    run_id = report_paths[0].name[len("wp9a-live-driver.") : -len(".json")]
    assert (
        driver._read_scoring_report(report_dir=report_dir, run_id=run_id, instance_id=INSTANCE_ID) is None
    )

    monkeypatch.setattr(driver, "dispatch_worker_for_lineage", _boom_dispatch)
    score_calls: list[str] = []

    def _counting_score(**kwargs):
        score_calls.append(kwargs["instance_id"])
        return stub_score_with_official_harness(**kwargs)

    monkeypatch.setattr(driver, "score_with_official_harness", _counting_score)

    resumed_verdict = _normalize(driver.run_driver(_args(run_root, resume=True)), run_root=run_root)
    assert score_calls == [INSTANCE_ID], "a truncated aggregated report must trigger exactly one re-score"
    assert resumed_verdict == baseline_verdict


# ---------------------------------------------------------------------------
# 5. call_cli timeout -> RuntimeError (never a raw TimeoutExpired leak).
# ---------------------------------------------------------------------------


def test_call_cli_timeout_reraised_as_runtime_error(driver_unit, monkeypatch):
    def _timeout_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=30)

    monkeypatch.setattr(driver_unit.subprocess, "run", _timeout_run)
    with pytest.raises(RuntimeError, match=r"econ_fold_cli derive-keys failed \(timed out after 30s\)"):
        driver_unit.call_cli(Path("/nonexistent/econ_fold_cli"), "derive-keys", {"schema": "x"})


# ---------------------------------------------------------------------------
# 6. Missing ~/.turingos/provider-profiles.json -> no startup crash.
# ---------------------------------------------------------------------------


def test_load_provider_config_returns_none_when_profile_file_missing(tmp_path, driver_unit, monkeypatch):
    monkeypatch.setattr(driver_unit.Path, "home", staticmethod(lambda: tmp_path))
    assert driver_unit.load_provider_config() is None


def test_load_provider_config_unchanged_when_profile_file_exists(tmp_path, driver_unit, monkeypatch):
    monkeypatch.setattr(driver_unit.Path, "home", staticmethod(lambda: tmp_path))
    profile_dir = tmp_path / ".turingos"
    profile_dir.mkdir()
    (profile_dir / "provider-profiles.json").write_text(
        json.dumps(
            {
                "deepseek_api_key_env": "DEEPSEEK_API_KEY",
                "deepseek_base_url": "https://api.deepseek.com",
                "deepseek_default_model": "deepseek-chat",
            }
        ),
        encoding="utf-8",
    )
    assert driver_unit.load_provider_config() == {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    }


def test_dispatch_fallback_reports_not_run_when_provider_config_missing(tmp_path, driver_unit, monkeypatch):
    monkeypatch.setattr(
        driver_unit,
        "dispatch_via_siliconflow",
        lambda **kwargs: {
            "status": "NOT_RUN",
            "missing_env": ["SILICONFLOW_API_KEY"],
            "instance_id": INSTANCE_ID,
            "arm": "armA",
            "lineage": "deepseek",
            "provider_path": "siliconflow",
        },
    )

    def _boom_native_dispatch(**kwargs):
        raise AssertionError("dispatch_worker must not run with a None provider config")

    monkeypatch.setattr(driver_unit, "dispatch_worker", _boom_native_dispatch)

    result = driver_unit.dispatch_worker_for_lineage(
        arm="armA",
        lineage="deepseek",
        packet={"instance_id": INSTANCE_ID, "_task_dir": tmp_path},
        task_dir_root=tmp_path / "task_runs",
        run_id_prefix="test",
        deepseek_native_provider_config=None,
    )
    assert result["status"] == "NOT_RUN"
    assert result["provider_path"] == "deepseek_direct_fallback"
    assert result["primary_attempt_status"] == "NOT_RUN"
    assert "provider config missing" in result["detail"]

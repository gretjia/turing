"""Tests for tools/certification/scenarios/FCE-S4.py (cost-conservation scenario).

FCE-S4 makes ONE real DeepSeek API call when actually executed (observed at
43-145 microUSD / well under a cent) - it is a certification scenario, not
something to spend real money on every `pytest` run. Following the established
convention in this repo (tests/test_fce_s1_scenario.py, tests/test_deepseek_arm_a_worker.py):
load the module directly via importlib and unit-test its pure/deterministic
helper functions with synthetic data (no network), and exercise the "no
credentials" gating path via monkeypatch.delenv - the gating is a runtime
behavior of the script itself (exit code 2, verdict NOT_RUN), not a pytest
marker/skip.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCENARIO_PATH = REPO / "tools" / "certification" / "scenarios" / "FCE-S4.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fce_s4_scenario", SCENARIO_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_select_single_task_is_deterministic_and_excludes_the_pilot_window(tmp_path):
    scenario = load_module()

    selection = scenario.select_single_task(REPO, tmp_path)

    assert selection["schema_id"] == "turingos.fce.s4.task_selection.v1"
    assert selection["shard_id"] == "S02"
    assert selection["pilot_window_id"] == "S02-W00"
    assert selection["instance_in_pilot_window"] is False
    # Known-good expectation, pinned against the real, committed S02 shard
    # manifest (same rule and same first instance as FCE-S1's cert slice).
    assert selection["instance_id"] == "django__django-11133"
    assert selection["window_id"] == "S02-W01"

    manifest_path = tmp_path / "task_selection.json"
    assert manifest_path.is_file()
    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written["instance_id"] == selection["instance_id"]

    # Deterministic: re-running selection over the same manifest is byte-identical.
    second = scenario.select_single_task(REPO, tmp_path)
    assert second["instance_id"] == selection["instance_id"]
    assert second["window_id"] == selection["window_id"]


def _cost_event(*, cost_microusd, cost_source_kind, total_tokens=10, bound_kind=None, schema_id=None):
    return {
        "event_type": "CostEvent",
        "_event_id": "mu:fixture",
        "payload": {
            "schema_id": schema_id or "turingos.cost_event.v2",
            "usage": {"total_tokens": total_tokens},
            "cost": {
                "cost_source_kind": cost_source_kind,
                "cost_microusd": cost_microusd,
                "bound_kind": bound_kind,
            },
        },
    }


def test_tape_cost_summary_sums_cost_and_tokens_across_cost_events():
    scenario = load_module()

    events = [
        _cost_event(cost_microusd=100, cost_source_kind="provider_receipt_inline", total_tokens=200),
        _cost_event(cost_microusd=50, cost_source_kind="provider_receipt_inline", total_tokens=75),
        {"event_type": "WorkerReceiptImported", "payload": {}},  # non-cost event, must be ignored
    ]

    summary = scenario.tape_cost_summary(REPO, events)

    assert summary["cost_event_count"] == 2
    assert summary["cost_microusd_sum"] == 150
    assert summary["token_count_sum"] == 275
    assert summary["all_cost_source_kinds_populated_and_valid"] is True
    assert summary["bounded_estimates_missing_bound_kind"] == []
    assert summary["all_schema_v2"] is True


def test_tape_cost_summary_flags_bounded_estimate_missing_bound_kind():
    scenario = load_module()

    events = [
        _cost_event(cost_microusd=10, cost_source_kind="bounded_estimate", bound_kind=None),
    ]

    summary = scenario.tape_cost_summary(REPO, events)

    assert summary["cost_event_count"] == 1
    assert summary["bounded_estimates_missing_bound_kind"] == ["mu:fixture"]
    # cost_source_kind itself is still a valid enum member even though bound_kind is missing.
    assert summary["all_cost_source_kinds_populated_and_valid"] is True


def test_tape_cost_summary_rejects_missing_or_unspecified_cost_source_kind():
    scenario = load_module()

    events = [_cost_event(cost_microusd=10, cost_source_kind=None)]
    summary = scenario.tape_cost_summary(REPO, events)
    assert summary["all_cost_source_kinds_populated_and_valid"] is False

    events = [_cost_event(cost_microusd=10, cost_source_kind="unspecified")]
    summary = scenario.tape_cost_summary(REPO, events)
    assert summary["all_cost_source_kinds_populated_and_valid"] is False


def test_tape_cost_summary_empty_events_is_not_populated_and_valid():
    scenario = load_module()

    summary = scenario.tape_cost_summary(REPO, [])

    assert summary["cost_event_count"] == 0
    assert summary["cost_microusd_sum"] == 0
    assert summary["token_count_sum"] == 0
    assert summary["all_cost_source_kinds_populated_and_valid"] is False
    assert summary["all_schema_v2"] is False


def test_receipts_file_cost_summary_sums_across_on_disk_receipt_files(tmp_path):
    scenario = load_module()

    log_dir = tmp_path / "instances" / "demo__demo-1" / "worker_logs"
    log_dir.mkdir(parents=True)
    receipt = {
        "schema_id": "deepseek_native_api_provider_receipt.v1",
        "cost": {"computed_cost_microusd": 43},
        "usage": {"prompt_tokens": 404, "completion_tokens": 137, "total_tokens": 541},
    }
    (log_dir / "provider_receipt_sanitized.json").write_text(json.dumps(receipt), encoding="utf-8")

    coverage = {
        "turingos_arm_runs": [
            {"instance_id": "demo__demo-1", "worker_log_dir": str(log_dir)},
        ]
    }

    summary = scenario.receipts_file_cost_summary(tmp_path, coverage)

    assert summary["receipt_file_count"] == 1
    assert summary["expected_receipt_count"] == 1
    assert summary["cost_microusd_sum"] == 43
    assert summary["token_count_sum"] == 541
    assert summary["receipt_files"][0]["instance_id"] == "demo__demo-1"
    assert summary["receipt_files"][0]["computed_cost_microusd"] == 43


def test_receipts_file_cost_summary_handles_missing_receipt_file(tmp_path):
    scenario = load_module()

    coverage = {"turingos_arm_runs": [{"instance_id": "demo__demo-1", "worker_log_dir": str(tmp_path / "nowhere")}]}

    summary = scenario.receipts_file_cost_summary(tmp_path, coverage)

    assert summary["receipt_file_count"] == 0
    assert summary["expected_receipt_count"] == 1
    assert summary["cost_microusd_sum"] == 0
    assert summary["token_count_sum"] == 0


def test_receipts_file_cost_summary_handles_empty_or_malformed_input(tmp_path):
    scenario = load_module()

    assert scenario.receipts_file_cost_summary(tmp_path, {})["receipt_file_count"] == 0
    assert scenario.receipts_file_cost_summary(tmp_path, {"turingos_arm_runs": "not-a-list"})["receipt_file_count"] == 0


def test_build_verdict_pass_requires_every_criterion_true(tmp_path):
    scenario = load_module()

    scenario_root = tmp_path / "FCE-S4"
    scenario_root.mkdir()
    evidence_file = scenario_root / "evidence.json"
    evidence_file.write_text(json.dumps({"ok": True}), encoding="utf-8")

    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-S4",
        started=0.0,
        commands=[{"cmd": "true", "exit_code": 0}],
        criteria=[{"criterion": "fixture_criterion", "result": True, "evidence": "FCE-S4/evidence.json"}],
        evidence_files=[evidence_file],
        automatic_fail=None,
    )

    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-S4"
    assert verdict["verdict"] == "PASS"
    assert verdict["goals_served"] == ["G2", "G5"]
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["not_run_is_fail"] is True
    assert "FCE-S4/evidence.json" in verdict["evidence"]
    assert verdict["evidence_sha256"]["FCE-S4/evidence.json"] == scenario.sha256_file(evidence_file)


def test_build_verdict_fail_when_any_criterion_false(tmp_path):
    scenario = load_module()

    scenario_root = tmp_path / "FCE-S4"
    scenario_root.mkdir()
    evidence_file = scenario_root / "evidence.json"
    evidence_file.write_text("{}", encoding="utf-8")

    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-S4",
        started=0.0,
        commands=[],
        criteria=[
            {"criterion": "one", "result": True, "evidence": "FCE-S4/evidence.json"},
            {"criterion": "two", "result": False, "evidence": "FCE-S4/evidence.json"},
        ],
        evidence_files=[evidence_file],
        automatic_fail=None,
    )

    assert verdict["verdict"] == "FAIL"


def test_resolve_daemon_bin_dir_prefers_repo_local_build(tmp_path, monkeypatch):
    scenario = load_module()

    fake_repo = tmp_path / "repo"
    bin_dir = fake_repo / "target" / "debug"
    bin_dir.mkdir(parents=True)
    for name in scenario.REQUIRED_DAEMON_BINARIES:
        binary = bin_dir / name
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        binary.chmod(0o755)

    scenario_root = tmp_path / "FCE-S4"
    scenario_root.mkdir()

    result = scenario.resolve_daemon_bin_dir(fake_repo, scenario_root)

    assert result["source"] == "repo_local_build"
    assert result["bin_dir"] == str(bin_dir)
    assert (scenario_root / "daemon_bin_dir_resolution.json").is_file()


def test_main_without_deepseek_api_key_is_not_run_and_makes_no_llm_call(tmp_path, monkeypatch):
    """Mirrors FCE-S1's own no-credential gating convention: the runtime behavior
    of the script itself (exit code, verdict NOT_RUN) is what gates real spend,
    not a pytest marker. No network call and no daemon-binary resolution/build
    is attempted in this path (the key check happens before either).
    """
    scenario = load_module()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    root = tmp_path / "root"
    plan_root = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
    argv = [
        "FCE-S4.py",
        "--root",
        str(root),
        "--repo",
        str(REPO),
        "--plan-root",
        str(plan_root),
        "--scenario-id",
        "FCE-S4",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    exit_code = scenario.main()

    assert exit_code == 2
    verdict_path = root / "FCE-S4" / "FCE-S4_verdict.json"
    assert verdict_path.is_file()
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-S4"
    assert verdict["verdict"] == "NOT_RUN"
    assert verdict["not_run_reason"] == "missing environment variable: DEEPSEEK_API_KEY"
    # No daemon_bin_dir_resolution.json should exist: the key check gates before
    # any binary resolution/build is attempted.
    assert not (root / "FCE-S4" / "daemon_bin_dir_resolution.json").is_file()

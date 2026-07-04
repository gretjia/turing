"""Tests for tools/certification/scenarios/FCE-S1.py (the golden-thread scenario).

FCE-S1 makes REAL DeepSeek API calls and runs the real upstream SWE-bench Docker
harness when actually executed - it is a certification scenario, not something to
spend real money on every `pytest` run. Following the established convention in
this repo for scripts that can make real, costly calls (tests/test_deepseek_arm_a_worker.py,
tests/test_stage9_native_api_worker.py, tests/test_deepseek_provider_canary.py): load the
module directly via importlib and unit-test its pure/deterministic helper functions with
synthetic data (no network), and exercise the "no credentials" gating path via
monkeypatch.delenv - the gating is a runtime behavior of the script itself (exit code 2,
verdict NOT_RUN), not a pytest marker/skip.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCENARIO_PATH = REPO / "tools" / "certification" / "scenarios" / "FCE-S1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fce_s1_scenario", SCENARIO_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_select_cert_slice_is_deterministic_and_excludes_the_pilot_window():
    """Cert-slice selection reads only local, already-committed evidence (no network)."""
    scenario = load_module()

    with_tmp = Path(__file__).resolve().parents[1] / ".pytest_fce_s1_scratch"
    with_tmp.mkdir(parents=True, exist_ok=True)
    try:
        cert_slice = scenario.select_cert_slice(REPO, with_tmp)
    finally:
        pass

    assert cert_slice["shard_id"] == "S02"
    assert cert_slice["pilot_window_id"] == "S02-W00"
    assert len(cert_slice["pilot_instance_ids"]) == 10
    assert cert_slice["cert_slice_size"] == 5
    assert len(cert_slice["cert_slice_instance_ids"]) == 5
    # The cert slice must never include a pilot-window instance (RES_M3 S2.7 exclusion rule).
    assert set(cert_slice["cert_slice_instance_ids"]).isdisjoint(set(cert_slice["pilot_instance_ids"]))
    # The rule is deterministic: re-running selection over the same manifest is byte-identical.
    second = scenario.select_cert_slice(REPO, with_tmp)
    assert second["cert_slice_instance_ids"] == cert_slice["cert_slice_instance_ids"]
    assert second["cert_slice_window_id"] == cert_slice["cert_slice_window_id"]
    # Known-good expectation pinned against the real, committed S02 shard manifest: the
    # pilot window (S02-W00) occupies the manifest's first 10 stored tasks, so the cert
    # slice is the first 5 tasks of the following window, S02-W01.
    assert cert_slice["cert_slice_window_id"] == "S02-W01"
    assert cert_slice["cert_slice_instance_ids"] == [
        "django__django-11133",
        "matplotlib__matplotlib-23314",
        "pydata__xarray-4695",
        "pytest-dev__pytest-7236",
        "scikit-learn__scikit-learn-13328",
    ]
    # Soft corroboration against the on-disk M3 arm-A pilot predictions should agree if present.
    if cert_slice["pilot_corroborated_against_arm_a_predictions"] is not None:
        assert cert_slice["pilot_corroborated_against_arm_a_predictions"] is True

    manifest_path = with_tmp / "cert_slice_manifest.json"
    assert manifest_path.is_file()
    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written["schema_id"] == "turingos.fce.s1.cert_slice_manifest.v1"
    for path in with_tmp.rglob("*"):
        if path.is_file():
            path.unlink()
    with_tmp.rmdir()


def test_cost_totals_from_coverage_sums_worker_cost_and_counts_receipts():
    scenario = load_module()

    coverage = {
        "turingos_arm_runs": [
            {"instance_id": "a", "worker_cost_microusd": 62},
            {"instance_id": "b", "worker_cost_microusd": 222},
            {"instance_id": "c", "worker_cost_microusd": 0},
        ]
    }

    totals = scenario.cost_totals_from_coverage(coverage)

    assert totals["total_llm_cost_microusd"] == 284
    assert totals["receipt_events"] == 3
    assert totals["unspecified_cost_events"] == 0


def test_cost_totals_from_coverage_handles_empty_or_malformed_input():
    scenario = load_module()

    assert scenario.cost_totals_from_coverage({}) == {
        "total_llm_cost_microusd": 0,
        "receipt_events": 0,
        "unspecified_cost_events": 0,
    }
    assert scenario.cost_totals_from_coverage({"turingos_arm_runs": "not-a-list"}) == {
        "total_llm_cost_microusd": 0,
        "receipt_events": 0,
        "unspecified_cost_events": 0,
    }


def test_build_verdict_pass_requires_every_criterion_true(tmp_path):
    scenario = load_module()

    scenario_root = tmp_path / "FCE-S1"
    scenario_root.mkdir()
    evidence_file = scenario_root / "evidence.json"
    evidence_file.write_text(json.dumps({"ok": True}), encoding="utf-8")

    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-S1",
        started=0.0,
        commands=[{"cmd": "true", "exit_code": 0}],
        criteria=[{"criterion": "fixture_criterion", "result": True, "evidence": "FCE-S1/evidence.json"}],
        evidence_files=[evidence_file],
        automatic_fail=None,
    )

    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-S1"
    assert verdict["verdict"] == "PASS"
    assert verdict["goals_served"] == ["G2"]
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["not_run_is_fail"] is True
    assert "FCE-S1/evidence.json" in verdict["evidence"]
    assert verdict["evidence_sha256"]["FCE-S1/evidence.json"] == scenario.sha256_file(evidence_file)


def test_build_verdict_fail_when_any_criterion_false(tmp_path):
    scenario = load_module()

    scenario_root = tmp_path / "FCE-S1"
    scenario_root.mkdir()
    evidence_file = scenario_root / "evidence.json"
    evidence_file.write_text("{}", encoding="utf-8")

    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-S1",
        started=0.0,
        commands=[],
        criteria=[
            {"criterion": "one", "result": True, "evidence": "FCE-S1/evidence.json"},
            {"criterion": "two", "result": False, "evidence": "FCE-S1/evidence.json"},
        ],
        evidence_files=[evidence_file],
        automatic_fail=None,
    )

    assert verdict["verdict"] == "FAIL"


def test_main_without_deepseek_api_key_is_not_run_and_makes_no_llm_call(tmp_path, monkeypatch):
    """Mirrors run_deepseek_arm_a_worker.py's own no-credential gating convention:
    the runtime behavior of the script itself (exit code, verdict NOT_RUN) is what
    gates real spend, not a pytest marker. No network call is made in this path.
    """
    scenario = load_module()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    root = tmp_path / "root"
    plan_root = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
    argv = [
        "FCE-S1.py",
        "--root",
        str(root),
        "--repo",
        str(REPO),
        "--plan-root",
        str(plan_root),
        "--scenario-id",
        "FCE-S1",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    exit_code = scenario.main()

    assert exit_code == 2
    verdict_path = root / "FCE-S1" / "FCE-S1_verdict.json"
    assert verdict_path.is_file()
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-S1"
    assert verdict["verdict"] == "NOT_RUN"
    assert verdict["not_run_reason"] == "missing environment variable: DEEPSEEK_API_KEY"
    assert verdict["fixture_or_real"] == "REAL"


def test_run_command_captures_timeout_as_exit_124(tmp_path):
    scenario = load_module()

    result = scenario.run_command(
        name="sleep_forever",
        argv=["sleep", "5"],
        cwd=tmp_path,
        out_dir=tmp_path,
        timeout=1,
    )

    assert result["exit_code"] == 124
    assert "TIMEOUT" in result["stderr_text"]


@pytest.mark.parametrize(
    "criteria,expected",
    [
        ([{"criterion": "a", "result": True, "evidence": "x"}], "PASS"),
        ([{"criterion": "a", "result": False, "evidence": "x"}], "FAIL"),
        ([], "PASS"),
    ],
)
def test_build_verdict_pass_fail_matrix(tmp_path, criteria, expected):
    scenario = load_module()
    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-S1",
        started=0.0,
        commands=[],
        criteria=criteria,
        evidence_files=[],
        automatic_fail=None,
    )
    assert verdict["verdict"] == expected

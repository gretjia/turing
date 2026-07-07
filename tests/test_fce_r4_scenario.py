"""Tests for tools/certification/scenarios/FCE-R4.py (cost-dashboard scenario).

FCE-R4 only spends real DeepSeek credit when NO existing certification tape is
already present under its `--root` (it rolls up whatever real tapes other
scenarios already produced in the same evidence root first, and only mints
its own single real call as a last resort, mirroring FCE-S4's `--limit 1`
convention). Following the established test convention in this repo
(tests/test_fce_s4_scenario.py): load the module directly via importlib and
unit-test its pure/deterministic helper functions with synthetic data (no
network), and exercise the "no existing tape, no credentials" gating path via
monkeypatch - the gating is a runtime behavior of the script itself (exit
code 2, verdict NOT_RUN), not a pytest marker/skip.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCENARIO_PATH = REPO / "tools" / "certification" / "scenarios" / "FCE-R4.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fce_r4_scenario", SCENARIO_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _cost_event(
    *,
    event_id,
    cost_microusd,
    cost_source_kind,
    total_tokens=10,
    bound_kind=None,
    model_id_resolved="deepseek-v4-flash",
    adapter_kind="native_api",
    run_id="run_demo",
    branch_id="branch_deepseek",
):
    return {
        "event_type": "CostEvent",
        "_event_id": event_id,
        "payload": {
            "schema_id": "turingos.cost_event.v2",
            "run_id": run_id,
            "branch_id": branch_id,
            "worker": {"model_id_resolved": model_id_resolved, "adapter_kind": adapter_kind},
            "usage": {"total_tokens": total_tokens},
            "cost": {"cost_source_kind": cost_source_kind, "cost_microusd": cost_microusd, "bound_kind": bound_kind},
        },
    }


class _FakeAudit:
    """Stand-in for audit_micro_tape_decision_dag, used only to test row
    extraction independent of the real module's exact numeric conventions."""

    COST_SOURCE_KINDS = {"provider_receipt_inline", "provider_usage_api_reconciled", "bounded_estimate", "fixture"}

    @staticmethod
    def cost_event_cost_microusd(payload):
        return payload.get("cost", {}).get("cost_microusd")

    @staticmethod
    def cost_event_total_tokens(payload):
        return payload.get("usage", {}).get("total_tokens", 0)


def test_derive_arm_label_extracts_explicit_arm_marker_from_branch_or_run_id():
    scenario = load_module()

    assert scenario.derive_arm_label("run_id_whatever", "branch_arm_a_uplift") == "arm_a"
    assert scenario.derive_arm_label("run_armB_task1", "branch_deepseek") == "arm_b"
    assert scenario.derive_arm_label("run_deepseek_task", "branch_deepseek") == scenario.NO_EXPLICIT_ARM_LABEL
    assert scenario.derive_arm_label(None, None) == scenario.NO_EXPLICIT_ARM_LABEL


def test_cost_rows_for_events_extracts_expected_fields_and_ignores_non_cost_events():
    scenario = load_module()
    audit = _FakeAudit()

    events = [
        _cost_event(event_id="mu:1", cost_microusd=100, cost_source_kind="provider_receipt_inline", total_tokens=200),
        {"event_type": "WorkerReceiptImported", "payload": {}},
        _cost_event(
            event_id="mu:2",
            cost_microusd=10,
            cost_source_kind="bounded_estimate",
            bound_kind="ceiling_estimate",
            adapter_kind="cli",
            branch_id="branch_arm_b",
        ),
    ]

    rows = scenario.cost_rows_for_events(audit, events, "FCE-R4")

    assert len(rows) == 2
    assert rows[0]["scenario_id"] == "FCE-R4"
    assert rows[0]["worker_model"] == "deepseek-v4-flash"
    assert rows[0]["module_seam"] == "native_api"
    assert rows[0]["arm"] == scenario.NO_EXPLICIT_ARM_LABEL
    assert rows[0]["cost_microusd"] == 100
    assert rows[0]["tokens"] == 200
    assert rows[1]["module_seam"] == "cli"
    assert rows[1]["arm"] == "arm_b"
    assert rows[1]["bound_kind"] == "ceiling_estimate"


def test_aggregate_rows_and_totals_and_partition_check_agree():
    scenario = load_module()
    audit = _FakeAudit()
    events = [
        _cost_event(event_id="mu:1", cost_microusd=100, cost_source_kind="provider_receipt_inline", total_tokens=200, adapter_kind="native_api"),
        _cost_event(event_id="mu:2", cost_microusd=50, cost_source_kind="provider_receipt_inline", total_tokens=75, adapter_kind="cli"),
    ]
    rows = scenario.cost_rows_for_events(audit, events, "FCE-R4")

    totals = scenario.totals_from_rows(rows)
    assert totals == {"cost_microusd_sum": 150, "token_count_sum": 275, "cost_event_count": 2}

    by_seam = scenario.aggregate_rows(rows, "module_seam")
    assert by_seam["native_api"]["cost_microusd_sum"] == 100
    assert by_seam["cli"]["cost_microusd_sum"] == 50
    assert scenario.breakdown_partitions_totals(by_seam, totals) is True

    # Corrupting one bucket must make the partition check fail.
    by_seam["cli"]["cost_microusd_sum"] = 999
    assert scenario.breakdown_partitions_totals(by_seam, totals) is False


def test_resolve_deepseek_api_key_prefers_process_environment(monkeypatch):
    scenario = load_module()
    monkeypatch.setenv("FCE_R4_TEST_KEY", "from-env")

    value, source = scenario.resolve_deepseek_api_key("FCE_R4_TEST_KEY", secrets_path=Path("/nonexistent/secrets.env"))

    assert value == "from-env"
    assert source == "process_environment"


def test_resolve_deepseek_api_key_falls_back_to_secrets_env_file(tmp_path, monkeypatch):
    scenario = load_module()
    monkeypatch.delenv("FCE_R4_TEST_KEY", raising=False)
    secrets_path = tmp_path / "secrets.env"
    secrets_path.write_text("# comment\nexport FCE_R4_TEST_KEY=\"from-file\"\nOTHER=1\n", encoding="utf-8")

    value, source = scenario.resolve_deepseek_api_key("FCE_R4_TEST_KEY", secrets_path=secrets_path)

    assert value == "from-file"
    assert source == "secrets_env_file"


def test_resolve_deepseek_api_key_returns_not_found_when_absent_everywhere(tmp_path, monkeypatch):
    scenario = load_module()
    monkeypatch.delenv("FCE_R4_TEST_KEY", raising=False)

    value, source = scenario.resolve_deepseek_api_key("FCE_R4_TEST_KEY", secrets_path=tmp_path / "missing.env")

    assert value is None
    assert source == "not_found"


def test_discover_existing_tape_sources_finds_sibling_scenarios_and_excludes_self(tmp_path):
    scenario = load_module()
    (tmp_path / "FCE-S4" / "loop_run").mkdir(parents=True)
    (tmp_path / "FCE-S4" / "loop_run" / "substrate_coverage.json").write_text("{}", encoding="utf-8")
    (tmp_path / "FCE-R4" / "loop_run").mkdir(parents=True)
    (tmp_path / "FCE-R4" / "loop_run" / "substrate_coverage.json").write_text("{}", encoding="utf-8")

    sources = scenario.discover_existing_tape_sources(tmp_path, "FCE-R4")

    assert len(sources) == 1
    assert sources[0]["scenario_id"] == "FCE-S4"
    assert sources[0]["minted_by_this_scenario"] is False


def test_discover_existing_tape_sources_empty_root_returns_empty(tmp_path):
    scenario = load_module()

    assert scenario.discover_existing_tape_sources(tmp_path / "nowhere", "FCE-R4") == []


def test_read_budget_ceiling_prefers_cli_override(tmp_path):
    scenario = load_module()

    value, source = scenario.read_budget_ceiling(tmp_path, 12_345)

    assert value == 12_345
    assert source == "cli_override"


def test_read_budget_ceiling_reads_e7_from_run_manifest(tmp_path):
    scenario = load_module()
    manifest = {
        "entry_criteria": [
            {"id": "E6", "evidence": {}},
            {"id": "E7", "evidence": {"budget_ceiling_microusd": 25_000_000}},
        ]
    }
    (tmp_path / "FCE_RUN_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")

    value, source = scenario.read_budget_ceiling(tmp_path, None)

    assert value == 25_000_000
    assert source == "fce_run_manifest_e7"


def test_read_budget_ceiling_falls_back_to_default_when_no_manifest(tmp_path):
    scenario = load_module()

    value, source = scenario.read_budget_ceiling(tmp_path, None)

    assert value == scenario.DEFAULT_BUDGET_CEILING_MICROUSD
    assert source == "default_recommended_ceiling"


def test_build_verdict_pass_requires_every_criterion_true(tmp_path):
    scenario = load_module()

    scenario_root = tmp_path / "FCE-R4"
    scenario_root.mkdir()
    evidence_file = scenario_root / "evidence.json"
    evidence_file.write_text(json.dumps({"ok": True}), encoding="utf-8")

    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-R4",
        started=0.0,
        commands=[{"cmd": "true", "exit_code": 0}],
        criteria=[{"criterion": "fixture_criterion", "result": True, "evidence": "FCE-R4/evidence.json"}],
        evidence_files=[evidence_file],
    )

    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-R4"
    assert verdict["verdict"] == "PASS"
    assert verdict["goals_served"] == ["G5", "G7"]
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["not_run_is_fail"] is True
    assert "FCE-R4/evidence.json" in verdict["evidence"]
    assert verdict["evidence_sha256"]["FCE-R4/evidence.json"] == scenario.sha256_file(evidence_file)


def test_build_verdict_fail_when_any_criterion_false(tmp_path):
    scenario = load_module()

    scenario_root = tmp_path / "FCE-R4"
    scenario_root.mkdir()
    evidence_file = scenario_root / "evidence.json"
    evidence_file.write_text("{}", encoding="utf-8")

    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-R4",
        started=0.0,
        commands=[],
        criteria=[
            {"criterion": "one", "result": True, "evidence": "FCE-R4/evidence.json"},
            {"criterion": "two", "result": False, "evidence": "FCE-R4/evidence.json"},
        ],
        evidence_files=[evidence_file],
    )

    assert verdict["verdict"] == "FAIL"


def test_main_without_existing_tapes_or_credentials_is_not_run_and_makes_no_llm_call(tmp_path, monkeypatch):
    """Mirrors FCE-S4's own no-credential gating convention: with an empty
    --root (no other scenario's tape to roll up) and no DeepSeek credentials
    anywhere (env or secrets file), the scenario must gate to NOT_RUN before
    attempting any daemon build or network call.
    """
    scenario = load_module()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(scenario, "SECRETS_ENV_PATH", tmp_path / "no_such_secrets.env")

    root = tmp_path / "root"
    plan_root = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
    argv = [
        "FCE-R4.py",
        "--root",
        str(root),
        "--repo",
        str(REPO),
        "--plan-root",
        str(plan_root),
        "--scenario-id",
        "FCE-R4",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    exit_code = scenario.main()

    assert exit_code == 2
    verdict_path = root / "FCE-R4" / "FCE-R4_verdict.json"
    assert verdict_path.is_file()
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-R4"
    assert verdict["verdict"] == "NOT_RUN"
    assert "missing DeepSeek credentials" in verdict["not_run_reason"]
    # No task selection / loop artifacts should exist: the key check gates
    # before any daemon build, materialization, or network call is attempted.
    assert not (root / "FCE-R4" / "task_selection.json").is_file()

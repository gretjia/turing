"""Tests for tools/certification/scenarios/FCE-B4.py (long-horizon load scenario).

FCE-B4 needs no LLM spend (Intent-aligned: it certifies substrate/orchestrator mechanics with a
generated FIXTURE tape and scripted sessions, per 09_FINAL_CERTIFICATION_EVALS.md §5 FCE-B4), so
end-to-end runs are exercised directly via subprocess (the tests/test_fce_b1_scenario.py /
tests/test_fce_b3_scenario.py convention), plus a handful of unit-level tests -- loaded via
importlib because the scenario module's filename is not a valid Python identifier -- that prove
the scenario's checks are not vacuous: the tape auditor actually rejects a tampered event, and the
scripted-session checker actually flags a forbidden-path touch.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
WORK_ROOT = REPO.parent
PLAN_ROOT = WORK_ROOT / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
SCENARIO_PATH = REPO / "tools" / "certification" / "scenarios" / "FCE-B4.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module():
    spec = importlib.util.spec_from_file_location("fce_b4_scenario", SCENARIO_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_scenario(out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCENARIO_PATH),
            "--root",
            str(out),
            "--repo",
            str(REPO),
            "--plan-root",
            str(PLAN_ROOT),
            "--scenario-id",
            "FCE-B4",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


# --- end-to-end scenario --------------------------------------------------


def test_fce_b4_long_horizon_scenario_passes(tmp_path: Path) -> None:
    out = tmp_path / "fce_run"
    proc = run_scenario(out)

    assert proc.returncode == 0, proc.stdout
    verdict = load_json(out / "FCE-B4" / "FCE-B4_verdict.json")
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["verdict"] == "PASS"
    assert verdict["fixture_or_real"] == "FIXTURE"
    assert verdict["automatic_fail_triggered"] is None
    assert set(verdict["goals_served"]) == {"G2", "G5"}

    expected_criteria = {
        "check1_long_tape_10000_plus_events_auditor_and_console_deterministic",
        "check2_constraint_persistence_checkpoints_atom4_and_atom8",
        "check3_checkpoint_compaction_resilience_constraint_survives_restart",
        "check4_failure_memory_injection_budget_respected_under_scale",
    }
    actual_criteria = {item["criterion"] for item in verdict["pass_criteria_results"]}
    assert actual_criteria == expected_criteria
    assert all(item["result"] is True for item in verdict["pass_criteria_results"]), verdict["pass_criteria_results"]

    # Every command genuinely ran and exited 0 -- no fabricated PASS over a failed subprocess.
    assert verdict["commands_executed"], "expected at least one real command"
    assert all(item["exit_code"] == 0 for item in verdict["commands_executed"]), verdict["commands_executed"]

    # Every evidence path's recorded digest must match the file's real bytes.
    for evidence_path in verdict["evidence"]:
        full_path = out / evidence_path
        assert full_path.is_file(), f"missing evidence file: {evidence_path}"
        recorded = verdict["evidence_sha256"][evidence_path]
        assert recorded.startswith("sha256:")
        actual = "sha256:" + hashlib.sha256(full_path.read_bytes()).hexdigest()
        assert recorded == actual, f"digest mismatch for {evidence_path}"

    assert "FCE-B4/CLAIM_BOUNDARY.json" in verdict["evidence"]
    claim_boundary = load_json(out / "FCE-B4" / "CLAIM_BOUNDARY.json")
    assert claim_boundary["evidence_class"] == "FIXTURE"
    assert any("p12" in claim.lower() or "injection-budget" in claim.lower() for claim in claim_boundary["claims"])

    # Check 1: the fixture tape genuinely has >= 10,000 events, and both the auditor and the
    # console-style rebuild are provably deterministic/hash-equal across two independent passes.
    check1 = load_json(out / "FCE-B4" / "check1_long_tape_report.json")
    assert check1["auditor_pass_1"]["event_count"] >= 10_000
    assert check1["auditor_deterministic_across_two_runs"] is True
    assert check1["console_rebuild_hash_equal"] is True
    assert check1["console_snapshot_1"]["snapshot_hash"] == check1["console_snapshot_2"]["snapshot_hash"]

    # Checks 2/3: both checkpoints ran a real constitution-pin re-verification, and the
    # constraint survived a forced compaction between atoms 5 and 6.
    check23 = load_json(out / "FCE-B4" / "check2_3_constraint_persistence_report.json")
    assert check23["checkpoints_2_of_2_pass"] is True
    assert check23["post_compaction_1_of_1_pass"] is True
    assert all(not record["path_x_touched"] for record in check23["atom_records"])
    checkpoint_atoms = {record["atom_index"] for record in check23["atom_records"] if record["constitution_check_ran"]}
    assert checkpoint_atoms == {4, 8}

    # Check 4: the budget is a REAL truncation (more distinct relevant rules were available than
    # the pinned ceiling), not a vacuous pass, and the built capsule stayed under both ceilings.
    check4 = load_json(out / "FCE-B4" / "check4_failure_memory_scale_report.json")
    assert check4["fixture_rules_fed"] == 50
    assert check4["budget_is_a_genuine_truncation"] is True
    assert check4["distinct_relevant_rules_uncapped"] > check4["pre_registered_budget"]["max_active_rules"]
    assert check4["capsule_injected_rules_count"] <= check4["pre_registered_budget"]["max_active_rules"]
    assert check4["capsule_injected_rules_total_chars"] <= check4["pre_registered_budget"]["max_rule_chars"]
    assert check4["capsule_injected_rules_total_tokens"] <= check4["token_ceiling"]
    assert check4["capsule_schema_valid"] is True


def test_fce_b4_scenario_is_replay_deterministic(tmp_path: Path) -> None:
    """Re-running the full check battery from two fresh scratch roots must produce the same PASS
    verdict and the same criteria results (FCE-R2's replay-determinism discipline applied locally
    to this scenario). Per NORMALIZATION_SPEC.json, absolute scratch paths are expected to differ
    (they are embedded in some generator stdout/report files via --out), so this compares the
    normalized pass_criteria_results and top-level verdict fields, not raw evidence digests --
    exactly the precedent set by tests/test_fce_b1_scenario.py's replay-determinism test."""
    out_1 = tmp_path / "run_1"
    out_2 = tmp_path / "run_2"
    proc_1 = run_scenario(out_1)
    proc_2 = run_scenario(out_2)
    assert proc_1.returncode == 0, proc_1.stdout
    assert proc_2.returncode == 0, proc_2.stdout

    verdict_1 = load_json(out_1 / "FCE-B4" / "FCE-B4_verdict.json")
    verdict_2 = load_json(out_2 / "FCE-B4" / "FCE-B4_verdict.json")
    assert verdict_1["verdict"] == verdict_2["verdict"] == "PASS"

    volatile = {"timestamp_utc", "wall_clock_ms"}

    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items() if k not in volatile}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    assert normalize(verdict_1["pass_criteria_results"]) == normalize(verdict_2["pass_criteria_results"])
    assert verdict_1["goals_served"] == verdict_2["goals_served"]
    assert verdict_1["fixture_or_real"] == verdict_2["fixture_or_real"]

    check1_1 = load_json(out_1 / "FCE-B4" / "check1_long_tape_report.json")
    check1_2 = load_json(out_2 / "FCE-B4" / "check1_long_tape_report.json")
    assert check1_1["auditor_pass_1"]["first_event_digest"] == check1_2["auditor_pass_1"]["first_event_digest"]
    assert check1_1["auditor_pass_1"]["last_event_digest"] == check1_2["auditor_pass_1"]["last_event_digest"]
    assert check1_1["console_snapshot_1"]["snapshot_hash"] == check1_2["console_snapshot_1"]["snapshot_hash"]


# --- unit-level: prove the checks are not vacuous -------------------------


def test_audit_tape_rejects_a_tampered_event(tmp_path: Path) -> None:
    scenario = load_module()
    tape_path = tmp_path / "tape.jsonl"
    scenario.gen_fixture_tape.write_tape(tape_path, 10_000, "unit-test-seed")

    # Sanity: the untampered tape audits clean.
    scenario.audit_tape(tape_path, "unit-test-seed")

    # Tamper with one event's payload value in place, keeping every other byte-shape intact.
    lines = tape_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[5000])
    tampered["payload"]["value"] = "0" * 24
    lines[5000] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
    tape_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(AssertionError):
        scenario.audit_tape(tape_path, "unit-test-seed")


def test_scripted_session_flags_forbidden_path_touch(tmp_path: Path) -> None:
    scenario = load_module()
    state_path = tmp_path / "session_state.json"
    session = scenario.ScriptedOrchestratorSession(state_path)
    session.seed_constraint(scenario.CONSTRAINT_TEXT, scenario.FORBIDDEN_PATH)

    clean_record, _ = session.run_atom(
        2,
        ["work/atom_2_impl.py"],
        plan_root=PLAN_ROOT,
        scenario_root=tmp_path,
        is_checkpoint=False,
    )
    assert clean_record["path_x_touched"] is False

    violating_record, _ = session.run_atom(
        3,
        ["work/atom_3_impl.py", scenario.FORBIDDEN_PATH],
        plan_root=PLAN_ROOT,
        scenario_root=tmp_path,
        is_checkpoint=False,
    )
    assert violating_record["path_x_touched"] is True


def test_scripted_session_checkpoint_runs_real_constitution_pin_command(tmp_path: Path) -> None:
    scenario = load_module()
    state_path = tmp_path / "session_state.json"
    session = scenario.ScriptedOrchestratorSession(state_path)
    session.seed_constraint(scenario.CONSTRAINT_TEXT, scenario.FORBIDDEN_PATH)

    record, command = session.run_atom(
        4,
        ["work/atom_4_impl.py"],
        plan_root=PLAN_ROOT,
        scenario_root=tmp_path,
        is_checkpoint=True,
    )
    assert record["constitution_check_ran"] is True
    assert command is not None
    assert command["exit_code"] == 0
    assert command["constitution_pin_matches"] is True
    assert command["cmd"].startswith("sha256sum ")


def test_constitution_pin_command_fails_closed_on_a_wrong_file(tmp_path: Path) -> None:
    """If the constitution file at the expected path were ever missing or altered, the checkpoint
    command must NOT silently report a match -- proves check2/3 do not fabricate a PASS."""
    scenario = load_module()
    wrong_plan_root = tmp_path / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
    fake_pack = wrong_plan_root.parent / "turing_v5" / "pack_v5_3_1" / "00_authority"
    fake_pack.mkdir(parents=True)
    (fake_pack / "constitution_root_law.md").write_text("not the real constitution\n", encoding="utf-8")

    command = scenario.run_constitution_pin_command(
        plan_root=wrong_plan_root, scenario_root=tmp_path, atom_index=99
    )
    assert command["exit_code"] == 0  # sha256sum itself still succeeds on the (wrong) file
    assert command["constitution_pin_matches"] is False


def test_check4_failure_memory_scale_check_is_a_real_truncation(tmp_path: Path) -> None:
    scenario = load_module()
    scenario_root = tmp_path / "FCE-B4"
    commands: list = []
    passed, report, evidence = scenario.check4_failure_memory_scale(
        scenario_root=scenario_root, repo=REPO, commands=commands
    )
    assert passed is True
    assert report["fixture_rules_fed"] == 50
    assert report["distinct_relevant_rules_uncapped"] > report["pre_registered_budget"]["max_active_rules"]
    assert report["capsule_injected_rules_count"] == report["pre_registered_budget"]["max_active_rules"]
    assert report["capsule_schema_valid"] is True
    assert evidence

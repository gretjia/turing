"""Tests for tools/certification/scenarios/FCE-R2.py (replay-determinism scenario).

Unlike FCE-S1 (real DeepSeek spend), FCE-R2 needs no external credentials: replay
determinism is a property of the tape/replay/console plumbing, not of worker-uplift
correctness. It only needs `cargo` and `git` (both required to build/test this repo at
all), so it is exercised end-to-end here, plus its pure/deterministic helpers are unit
tested directly (importlib, mirroring test_fce_s1_scenario.py's loading convention).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
PLAN_ROOT = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
SCENARIO_PATH = REPO / "tools" / "certification" / "scenarios" / "FCE-R2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fce_r2_scenario", SCENARIO_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Pure helper unit tests
# --------------------------------------------------------------------------


def test_normalize_value_strips_only_volatile_keys_and_recurses():
    scenario = load_module()
    volatile = {"timestamp_utc", "wall_clock_ms", "scratch_dir"}

    value = {
        "timestamp_utc": "2026-01-01T00:00:00Z",
        "wall_clock_ms": 42,
        "scratch_dir": "/tmp/whatever",
        "keep": "value",
        "nested": {"timestamp_utc": "x", "keep": [1, 2, {"wall_clock_ms": 3, "keep": True}]},
    }
    normalized = scenario.normalize_value(value, volatile)

    assert normalized == {
        "keep": "value",
        "nested": {"keep": [1, 2, {"keep": True}]},
    }


def test_canonical_bytes_is_stable_and_ignores_key_order():
    scenario = load_module()
    volatile: set[str] = set()

    a = scenario.canonical_bytes({"b": 1, "a": 2}, volatile)
    b = scenario.canonical_bytes({"a": 2, "b": 1}, volatile)
    assert a == b


def test_sha256_jcs_matches_manual_digest():
    scenario = load_module()
    import hashlib

    value = {"b": 1, "a": 2}
    expected = "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert scenario.sha256_jcs(value) == expected


def test_shadow_rebuild_consistent_true_when_hash_matches_and_false_when_tampered():
    scenario = load_module()

    preimage = {"heads": {"tape_tip": "mu:aaa"}, "operator_state": "Healthy"}
    honest_hash = scenario.sha256_jcs(preimage)
    honest_snapshot = dict(preimage)
    honest_snapshot["snapshot_hash"] = honest_hash

    consistent, expected, actual = scenario.shadow_rebuild_consistent(honest_snapshot)
    assert consistent is True
    assert expected == honest_hash
    assert actual == honest_hash

    tampered_snapshot = dict(honest_snapshot)
    tampered_snapshot["operator_state"] = "Tampered"
    consistent, expected, actual = scenario.shadow_rebuild_consistent(tampered_snapshot)
    assert consistent is False
    assert expected == honest_hash
    assert actual != honest_hash


def test_tree_manifest_sha256_is_stable_and_detects_mutation(tmp_path: Path):
    scenario = load_module()

    tree = tmp_path / "tree"
    (tree / "a").mkdir(parents=True)
    (tree / "a" / "file1.txt").write_text("hello", encoding="utf-8")
    (tree / "file2.txt").write_text("world", encoding="utf-8")

    digest_1 = scenario.tree_manifest_sha256(tree)
    digest_2 = scenario.tree_manifest_sha256(tree)
    assert digest_1 == digest_2

    (tree / "file2.txt").write_text("mutated", encoding="utf-8")
    digest_3 = scenario.tree_manifest_sha256(tree)
    assert digest_3 != digest_1


def test_load_normalization_spec_reads_the_shared_shipped_spec():
    scenario = load_module()

    _, volatile_keys = scenario.load_normalization_spec(REPO)
    assert {"timestamp_utc", "wall_clock_ms", "scratch_dir", "tmp_dir", "absolute_scratch_path"} <= volatile_keys


def test_run_command_captures_timeout_as_exit_124(tmp_path: Path):
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
def test_build_verdict_pass_fail_matrix(tmp_path: Path, criteria, expected):
    scenario = load_module()
    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-R2",
        started=0.0,
        commands=[],
        criteria=criteria,
        evidence_files=[],
        automatic_fail=None,
    )
    assert verdict["verdict"] == expected
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["goals_served"] == ["G2"]
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["not_run_is_fail"] is True


def test_build_verdict_reports_automatic_fail_when_passed_through(tmp_path: Path):
    scenario = load_module()
    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-R2",
        started=0.0,
        commands=[],
        criteria=[{"criterion": "a", "result": False, "evidence": "x"}],
        evidence_files=[],
        automatic_fail="evidence_tampering",
    )
    assert verdict["verdict"] == "FAIL"
    assert verdict["automatic_fail_triggered"] == "evidence_tampering"


# --------------------------------------------------------------------------
# End-to-end standalone invocation (real cargo build/test + real git-tape + real CLI;
# no external credentials required).
# --------------------------------------------------------------------------


def run_scenario_script(out: Path) -> subprocess.CompletedProcess[str]:
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
            "FCE-R2",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
        check=False,
    )


def test_fce_r2_standalone_end_to_end_replay_determinism_pass(tmp_path: Path):
    out = tmp_path / "fce_run"
    proc = run_scenario_script(out)
    assert proc.returncode == 0, proc.stdout

    verdict = load_json(out / "FCE-R2" / "FCE-R2_verdict.json")
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-R2"
    assert verdict["verdict"] == "PASS"
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["goals_served"] == ["G2"]
    assert verdict["automatic_fail_triggered"] is None
    assert verdict["not_run_is_fail"] is True

    criteria_by_name = {item["criterion"]: item for item in verdict["pass_criteria_results"]}
    expected_criteria = {
        "cargo_build_replay_probe_exit_zero",
        "sg19_rust_crate_replay_determinism_test_pass",
        "master_tape_is_real_sha256_git_tape_with_heads",
        "layer1_all_commands_exit_zero",
        "layer1_reconstruction_byte_identical_across_master_and_all_rounds",
        "layer1_reconstruction_nontrivial_and_head_set_populated",
        "tape_bundle_digest_stable_across_reads",
        "layer2_all_commands_exit_zero",
        "console_snapshot_hash_shadow_rebuild_consistent_all_rounds",
        "console_projection_byte_identical_across_all_rounds",
    }
    assert expected_criteria <= criteria_by_name.keys()
    assert all(item["result"] is True for item in verdict["pass_criteria_results"])

    # every evidence path exists and its digest matches what the verdict claims
    for item in verdict["evidence"]:
        path = out / item
        assert path.is_file(), item
        assert verdict["evidence_sha256"][item] == "sha256:" + __import__("hashlib").sha256(path.read_bytes()).hexdigest()

    # Layer 1: the 3 independent fresh-scratch-copy replays are byte-identical to the master.
    layer1_summary = load_json(out / "FCE-R2" / "layer1_contracts_replay" / "layer1_summary.json")
    assert layer1_summary["reconstruction_all_identical"] is True
    assert layer1_summary["reconstruction_nontrivial"] is True
    assert len(set(layer1_summary["reconstruction_normalized_sha256"].values())) == 1
    assert set(layer1_summary["reconstruction_normalized_sha256"].keys()) == {
        "master", "round_1", "round_2", "round_3",
    }

    digest_stability = load_json(out / "FCE-R2" / "layer1_contracts_replay" / "tape_digest_stability.json")
    assert digest_stability["master_digest_stable"] is True
    assert len(digest_stability["rounds"]) == 3
    assert all(item["digest_stable_across_read"] for item in digest_stability["rounds"])

    # Layer 2: the console/operator-projection replay is also byte-identical, and each
    # snapshot's shadow-rebuild hash is self-consistent.
    layer2_summary = load_json(out / "FCE-R2" / "layer2_console_replay" / "layer2_summary.json")
    assert layer2_summary["console_all_identical"] is True
    assert len(layer2_summary["console_normalized_sha256"]) == 3
    assert all(item["consistent"] for item in layer2_summary["shadow_rebuild_results"])

    claim_boundary = load_json(out / "FCE-R2" / "CLAIM_BOUNDARY.json")
    assert claim_boundary["schema_id"] == "CLAIM_BOUNDARY.v2"
    assert claim_boundary["evidence_class"] == "REAL"

    readme_text = (out / "FCE-R2" / "README.md").read_text(encoding="utf-8")
    assert "REAL" in readme_text
    assert "FakeWorker" in readme_text


def test_fce_r2_is_idempotently_rerunnable_and_stays_byte_identical(tmp_path: Path):
    """A second, fully independent invocation (fresh --root) must reproduce the same
    normalized reconstruction/console bytes as the first - the scenario's own
    determinism claim applied to itself."""
    first_out = tmp_path / "run1"
    second_out = tmp_path / "run2"

    first = run_scenario_script(first_out)
    assert first.returncode == 0, first.stdout
    second = run_scenario_script(second_out)
    assert second.returncode == 0, second.stdout

    first_layer1 = load_json(first_out / "FCE-R2" / "layer1_contracts_replay" / "layer1_summary.json")
    second_layer1 = load_json(second_out / "FCE-R2" / "layer1_contracts_replay" / "layer1_summary.json")
    assert (
        first_layer1["reconstruction_normalized_sha256"]["master"]
        == second_layer1["reconstruction_normalized_sha256"]["master"]
    )

    first_layer2 = load_json(first_out / "FCE-R2" / "layer2_console_replay" / "layer2_summary.json")
    second_layer2 = load_json(second_out / "FCE-R2" / "layer2_console_replay" / "layer2_summary.json")
    assert (
        first_layer2["console_normalized_sha256"]["round_1"]
        == second_layer2["console_normalized_sha256"]["round_1"]
    )

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WORK_ROOT = REPO.parent
PLAN_ROOT = WORK_ROOT / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
TOOLS = REPO / "tools" / "certification"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_scenario(out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "python3",
            str(TOOLS / "scenarios" / "FCE-B1.py"),
            "--root",
            str(out),
            "--repo",
            str(REPO),
            "--plan-root",
            str(PLAN_ROOT),
            "--scenario-id",
            "FCE-B1",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_fce_b1_uplift_verification_scenario(tmp_path: Path) -> None:
    out = tmp_path / "fce_run"
    proc = run_scenario(out)

    assert proc.returncode == 0, proc.stdout
    verdict = load_json(out / "FCE-B1" / "FCE-B1_verdict.json")
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["verdict"] == "PASS"
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["goals_served"] == ["G4", "G5"]
    assert verdict["automatic_fail_triggered"] is None

    expected_criteria = {
        "check1_preregistration_and_frozen_packet_digest_chain_matches",
        "check2_frozen_analyzer_recompute_matches_published_uplift_report",
        "check3_every_arm_outcome_traces_to_upstream_harness_report",
        "check4_ablation_honesty_recompute_pass_b_vs_c_capsules",
        "check5_arm_d_deterministic_floor_zero_resolved_no_stop_latch",
        "check6_h2_efficacy_statistics_present_and_honestly_phrased",
        "check7_deviations_documented_and_zero_pairwise_exclusions",
        "check8_h_vpput_recompute_matches_published_and_zero_unspecified_cost_events",
    }
    actual_criteria = {item["criterion"] for item in verdict["pass_criteria_results"]}
    assert actual_criteria == expected_criteria
    assert all(item["result"] is True for item in verdict["pass_criteria_results"]), verdict["pass_criteria_results"]

    # Every command the scenario ran (frozen analyzer recompute, ablation
    # capsule re-audit, per-arm H-VPPUT recompute, report reassembly) must
    # have genuinely exited 0 -- no fabricated PASS over a failed recompute.
    assert verdict["commands_executed"], "expected at least one real recompute command"
    assert all(item["exit_code"] == 0 for item in verdict["commands_executed"]), verdict["commands_executed"]

    # Every evidence path listed in the verdict must exist under the scenario
    # root and its recorded digest must match the file's real bytes.
    for evidence_path in verdict["evidence"]:
        full_path = out / evidence_path
        assert full_path.is_file(), f"missing evidence file: {evidence_path}"
        recorded = verdict["evidence_sha256"][evidence_path]
        assert recorded.startswith("sha256:")
        import hashlib

        actual = "sha256:" + hashlib.sha256(full_path.read_bytes()).hexdigest()
        assert recorded == actual, f"digest mismatch for {evidence_path}"

    assert "FCE-B1/CLAIM_BOUNDARY.json" in verdict["evidence"]
    claim_boundary = load_json(out / "FCE-B1" / "CLAIM_BOUNDARY.json")
    assert claim_boundary["evidence_class"] == "REAL"
    assert any("does not re-run" in item.lower() for item in claim_boundary["non_claims"])

    # This scenario certifies measurement validity, not a positive result:
    # the recomputed H1/H2 deltas must equal the published (null) values, and
    # the scenario must not require or assert a positive uplift.
    recompute = load_json(out / "FCE-B1" / "m3_analysis_recompute_comparison.json")
    assert recompute["reports_byte_equal_after_parse"] is True
    assert recompute["recomputed_h1"] == recompute["published_h1"]
    assert recompute["recomputed_h2"] == recompute["published_h2"]

    hvpput_check = load_json(out / "FCE-B1" / "m4_hvpput_verification_check.json")
    assert hvpput_check["all_arms_recompute_byte_equal"] is True
    assert hvpput_check["all_arms_zero_excluded_events"] is True
    assert hvpput_check["worker_visible_marker_sweep"]["clean"] is True
    assert hvpput_check["worker_visible_marker_sweep"]["files_scanned"] > 0


def test_fce_b1_scenario_is_replay_deterministic(tmp_path: Path) -> None:
    """Re-running the recomputation battery from a fresh scratch root twice
    must produce the same PASS verdict and the same recomputed statistics
    (FCE-R2's replay-determinism discipline applied locally to this
    scenario)."""
    out_1 = tmp_path / "run_1"
    out_2 = tmp_path / "run_2"
    proc_1 = run_scenario(out_1)
    proc_2 = run_scenario(out_2)
    assert proc_1.returncode == 0, proc_1.stdout
    assert proc_2.returncode == 0, proc_2.stdout

    verdict_1 = load_json(out_1 / "FCE-B1" / "FCE-B1_verdict.json")
    verdict_2 = load_json(out_2 / "FCE-B1" / "FCE-B1_verdict.json")
    assert verdict_1["verdict"] == verdict_2["verdict"] == "PASS"

    volatile = {"timestamp_utc", "wall_clock_ms"}

    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items() if k not in volatile}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    assert normalize(verdict_1["pass_criteria_results"]) == normalize(verdict_2["pass_criteria_results"])

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


def run_scenario_script(scenario_id: str, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(TOOLS / "scenarios" / f"{scenario_id}.py"),
            "--root",
            str(out),
            "--repo",
            str(REPO),
            "--plan-root",
            str(PLAN_ROOT),
            "--scenario-id",
            scenario_id,
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_fce_r3_ops_inventory_standalone(tmp_path: Path) -> None:
    out = tmp_path / "fce_run"
    proc = run_scenario_script("FCE-R3", out)

    assert proc.returncode == 0, proc.stdout
    verdict = load_json(out / "FCE-R3" / "FCE-R3_verdict.json")
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["verdict"] == "PASS"
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["automatic_fail_triggered"] is None
    criteria_names = {item["criterion"] for item in verdict["pass_criteria_results"]}
    assert criteria_names >= {
        "scenario_verdicts_structured_no_prose_only",
        "evidence_roots_labeled_fixture_or_real_with_claim_boundary",
        "zero_unclassified_zero_byte_files",
        "harness_logs_retained_per_instance",
        "receipts_directory_complete",
        "operator_console_heartbeat_exercisable_at_every_step",
        "pre_existing_evidence_digest_sweep_clean",
    }
    assert all(item["result"] is True for item in verdict["pass_criteria_results"])
    assert "FCE-R3/CLAIM_BOUNDARY.json" in verdict["evidence"]
    assert "FCE-R3/ops_inventory.json" in verdict["evidence"]

    ops_inventory = load_json(out / "FCE-R3" / "ops_inventory.json")
    assert ops_inventory["schema_id"] == "turingos.fce.r3.ops_inventory.v1"
    # Standalone invocation: no sibling scenario roots have been materialized
    # yet under --root, so the sibling inventory is genuinely (not
    # fabricatedly) empty; this is documented explicitly in the inventory.
    assert ops_inventory["sibling_scenario_roots_found"] == []
    assert ops_inventory["scenario_verdict_inventory"] == []
    assert "standalone_invocation_caveat" in ops_inventory
    assert ops_inventory["pre_existing_evidence_digest_sweep"]["clean"] is True
    assert ops_inventory["operator_console_heartbeat_report"]["all_exercisable"] is True
    assert ops_inventory["receipts_completeness_report"]["complete"] is True

    claim_boundary = load_json(out / "FCE-R3" / "CLAIM_BOUNDARY.json")
    assert claim_boundary["schema_id"] == "CLAIM_BOUNDARY.v2"
    assert claim_boundary["evidence_class"] == "REAL"

    readme_text = (out / "FCE-R3" / "README.md").read_text(encoding="utf-8")
    assert "REAL" in readme_text


def test_fce_r3_ops_inventory_over_sibling_scenario_roots(tmp_path: Path) -> None:
    """FCE-R3's sibling-root inventory genuinely inspects real verdicts,
    labels, and zero-byte classification once other scenarios have populated
    --root (approximating a full aggregate FCE run)."""
    out = tmp_path / "fce_run"
    b5_proc = run_scenario_script("FCE-B5", out)
    assert b5_proc.returncode == 0, b5_proc.stdout
    r5_proc = run_scenario_script("FCE-R5", out)
    assert r5_proc.returncode == 0, r5_proc.stdout

    r3_proc = run_scenario_script("FCE-R3", out)
    assert r3_proc.returncode == 0, r3_proc.stdout

    verdict = load_json(out / "FCE-R3" / "FCE-R3_verdict.json")
    assert verdict["verdict"] == "PASS"
    assert verdict["automatic_fail_triggered"] is None

    ops_inventory = load_json(out / "FCE-R3" / "ops_inventory.json")
    assert set(ops_inventory["sibling_scenario_roots_found"]) == {"FCE-B5", "FCE-R5"}
    verdict_by_id = {item["scenario_id"]: item for item in ops_inventory["scenario_verdict_inventory"]}
    assert verdict_by_id["FCE-B5"]["complete"] is True
    assert verdict_by_id["FCE-B5"]["verdict"] == "PASS"
    assert verdict_by_id["FCE-R5"]["complete"] is True
    assert verdict_by_id["FCE-R5"]["verdict"] == "PASS"
    labels_by_id = {item["scenario_id"]: item for item in ops_inventory["evidence_root_label_inventory"]}
    assert labels_by_id["FCE-B5"]["claim_boundary_evidence_class"] == "FIXTURE"
    assert labels_by_id["FCE-R5"]["claim_boundary_evidence_class"] == "REAL"
    assert ops_inventory["zero_byte_file_report"]["clean"] is True
    assert ops_inventory["zero_byte_file_report"]["unclassified"] == []

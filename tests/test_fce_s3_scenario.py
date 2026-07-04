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


def test_fce_s3_governance_entry_convergence_scenario(tmp_path: Path) -> None:
    out = tmp_path / "fce_run"
    proc = subprocess.run(
        [
            "python3",
            str(TOOLS / "scenarios" / "FCE-S3.py"),
            "--root",
            str(out),
            "--repo",
            str(REPO),
            "--plan-root",
            str(PLAN_ROOT),
            "--scenario-id",
            "FCE-S3",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout
    verdict = load_json(out / "FCE-S3" / "FCE-S3_verdict.json")
    assert verdict["verdict"] == "PASS"
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["goals_served"] == ["G1"]
    assert verdict["automatic_fail_triggered"] is None
    assert {item["criterion"] for item in verdict["pass_criteria_results"]} >= {
        "session_1_claude_md_chain_fully_resolved",
        "session_1_claude_md_verify_alignment_green",
        "session_2_agents_md_chain_fully_resolved",
        "session_2_agents_md_verify_alignment_green",
        "session_3_plan_index_chain_fully_resolved",
        "session_3_plan_index_verify_alignment_green",
        "three_of_three_sessions_resolve_identical_authority_chain",
        "three_of_three_verify_alignment_runs_green",
    }
    assert all(item["result"] is True for item in verdict["pass_criteria_results"])

    # Every evidence path listed in the verdict must exist and its recorded
    # digest must match the file's real bytes (no fabricated digests).
    for evidence_path in verdict["evidence"]:
        full_path = out / evidence_path
        assert full_path.is_file(), f"missing evidence file: {evidence_path}"
        recorded = verdict["evidence_sha256"][evidence_path]
        assert recorded.startswith("sha256:")

    comparison = load_json(out / "FCE-S3" / "session_comparison.json")
    assert comparison["resolved_chains_identical"] is True
    assert len(comparison["resolved_chains"]) == 3
    chains = comparison["resolved_chains"]
    assert chains[0] == chains[1] == chains[2]
    assert chains[0]["constitution_path"].endswith("constitution_root_law.md")
    assert chains[0]["constitution_sha256_cited"] == (
        "a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0"
    )
    assert chains[0]["status_ceiling"] == "ADDRESSED"
    assert chains[0]["human_gate_1"] is not None
    assert chains[0]["human_gate_2"] is not None
    assert all(green["green"] is True for green in comparison["verify_alignment_green_per_session"])

    assert "FCE-S3/CLAIM_BOUNDARY.json" in verdict["evidence"]
    claim_boundary = load_json(out / "FCE-S3" / "CLAIM_BOUNDARY.json")
    assert claim_boundary["evidence_class"] == "REAL"

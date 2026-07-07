import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_campaign(root: Path, *, bad_shard: bool = False):
    root.mkdir(parents=True, exist_ok=True)
    (root / "CLAIM_BOUNDARY.json").write_text(
        json.dumps(
            {
                "campaign_kind": "internal_official_harness_run",
                "dataset": "SWE-bench Verified",
                "task_count": 500,
                "selection_policy": "ALL",
                "full_swe_bench_dataset_claim_allowed": False,
                "full_swe_bench_verified_500_claim_allowed_after_fg_pass": True,
                "full_score_claim_allowed_before_fg_pass": False,
                "leaderboard_equivalence_claim_allowed": False,
                "official_leaderboard_submission_claim_allowed": False,
                "gold_patch_shortcut_allowed": False,
                "repo_local_evaluator_official_claim_allowed": False,
                "phase_g_release_allowed_before_official_harness_gates": False,
            },
            indent=2,
        )
        + "\n"
    )
    (root / "task_manifest.json").write_text(
        json.dumps({"task_count": 500, "instance_ids": [f"repo__task-{i:03d}" for i in range(500)]}) + "\n"
    )
    for shard_idx in range(10):
        shard = f"S{shard_idx:02d}"
        shard_dir = root / "shards" / shard
        shard_dir.mkdir(parents=True, exist_ok=True)
        shard_report = {
            "shard_id": shard,
            "status": "FAIL" if bad_shard and shard_idx == 3 else "PASS",
            "task_count": 50,
            "completed_count": 50,
            "resolved_count": 25,
            "unresolved_count": 25,
            "infra_failed_count": 0,
        }
        (shard_dir / "shard_audit.json").write_text(json.dumps(shard_report, indent=2) + "\n")


def test_campaign_audit_reduces_10_passed_shards(tmp_path):
    auditor = load_module("campaign_auditor", REPO / "tools/bench/audit_swebench_campaign.py")
    write_campaign(tmp_path)

    report = auditor.audit_campaign(tmp_path)

    assert report["status"] == "PASS"
    assert report["shard_count"] == 10
    assert report["task_count"] == 500
    assert report["leaderboard_equivalence_claim_allowed"] is False
    assert report["next_action"] == "final_positioning_report"


def test_campaign_audit_blocks_if_any_shard_failed(tmp_path):
    auditor = load_module("campaign_auditor", REPO / "tools/bench/audit_swebench_campaign.py")
    write_campaign(tmp_path, bad_shard=True)

    report = auditor.audit_campaign(tmp_path)

    assert report["status"] == "BLOCKED"
    assert "shard S03 status is FAIL" in report["problems"]


def test_campaign_audit_cli(tmp_path):
    write_campaign(tmp_path)

    subprocess.run(
        ["python3", "tools/bench/audit_swebench_campaign.py", "--root", str(tmp_path)],
        cwd=REPO,
        check=True,
    )

    assert json.loads((tmp_path / "final/campaign_audit.json").read_text())["status"] == "PASS"

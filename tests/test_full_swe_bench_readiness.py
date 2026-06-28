import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PHASE_F_ROOT = REPO / "evidence/bench/swe_bench_phase_f_evaluator_proof_20260628"
PHASE_F_REPAIR_ROOT = REPO / "evidence/bench/swe_bench_phase_f_repair_loop_20260628"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def minimal_full_manifest(task_count: int = 50) -> dict:
    instance_ids = [f"repo__task-{index:04d}" for index in range(task_count)]
    return {
        "schema_id": "FullSweBenchTaskManifest.v1",
        "source_dataset": "SWE-bench Verified",
        "source_dataset_digest": "sha256:" + "1" * 64,
        "official_harness_digest": "sha256:" + "2" * 64,
        "selection_policy": "ALL",
        "task_count": task_count,
        "official_dataset_task_count": task_count,
        "instance_ids": instance_ids,
        "excluded_instances": [],
        "exclusion_reason": {},
        "frozen_before_run": True,
    }


def minimal_full_loop_manifest() -> dict:
    return {
        "schema_id": "FullSweBenchLoopManifest.v1",
        "authorization_mode": "required",
        "fallback_to_auto_authorization_allowed": False,
        "manual_patch_count_allowed": 0,
        "manual_rerun_selection_allowed": 0,
        "full_score_claim_gate": {
            "full_score_claim_allowed_before_run": False,
            "requires_unsolved_count_zero": True,
            "requires_every_task_official_pass": True,
            "requires_final_pput_progress_one": True,
        },
        "budget_profile": {
            "max_attempts_per_instance": 3,
            "max_wall_seconds_per_instance": 3600,
            "max_tokens_per_instance": 200000,
            "max_total_wall_seconds": 180000,
            "max_total_tokens": 10000000,
        },
    }


def test_current_phase_f_blocks_full_swe_bench_readiness():
    auditor = load_module(
        "full_readiness_auditor",
        REPO / "tools/bench/audit_full_swe_bench_readiness.py",
    )

    report = auditor.audit_full_swe_bench_readiness(
        phase_f_root=PHASE_F_ROOT,
        repair_loop_root=PHASE_F_REPAIR_ROOT,
        full_manifest_root=REPO / "evidence/bench/swe_bench_full_manifest_20260628",
    )

    assert report["status"] == "BLOCKED"
    assert report["full_swe_bench_ready"] is False
    assert report["release_phase_g"] is False
    assert report["phase_f"]["status"] == "PARTIAL"
    assert report["repair_loop"]["status"] == "BLOCKED"
    assert "fresh_stage16r_real_evaluator_bundles_required" in report["blockers"]
    assert "phase_f_evaluator_proof_pass_required" in report["blockers"]
    assert report["next_loop"] == "stage16r_real_evaluator_bundle_loop"


def test_phase_f_pass_still_blocks_without_full_manifest_freeze(tmp_path):
    auditor = load_module(
        "full_readiness_auditor",
        REPO / "tools/bench/audit_full_swe_bench_readiness.py",
    )
    phase_f_root = tmp_path / "phase_f"
    repair_root = tmp_path / "repair"
    full_manifest_root = tmp_path / "full_manifest"
    write_json(
        phase_f_root / "official_eval_replay_audit.json",
        {
            "status": "PASS",
            "official_evaluator_executable_replay": True,
            "release_next_phase_g": True,
            "full_swe_bench_score_claim_allowed": False,
            "full_dataset_claim_allowed": False,
            "leaderboard_equivalence_claim_allowed": False,
        },
    )
    write_json(
        repair_root / "phase_f_repair_loop_audit.json",
        {
            "status": "PASS",
            "release_next_phase_g": False,
            "phase_f_evaluator_proof_required": True,
            "required_next_action": "rerun_phase_f_evaluator_proof",
        },
    )

    report = auditor.audit_full_swe_bench_readiness(
        phase_f_root=phase_f_root,
        repair_loop_root=repair_root,
        full_manifest_root=full_manifest_root,
    )

    assert report["status"] == "BLOCKED"
    assert report["full_swe_bench_ready"] is False
    assert "full_dataset_manifest_freeze_required" in report["blockers"]
    assert report["next_loop"] == "phase_g_full_manifest_freeze"


def test_full_swe_bench_ready_requires_phase_f_pass_and_full_manifest(tmp_path):
    auditor = load_module(
        "full_readiness_auditor",
        REPO / "tools/bench/audit_full_swe_bench_readiness.py",
    )
    phase_f_root = tmp_path / "phase_f"
    repair_root = tmp_path / "repair"
    full_manifest_root = tmp_path / "full_manifest"
    write_json(
        phase_f_root / "official_eval_replay_audit.json",
        {
            "status": "PASS",
            "official_evaluator_executable_replay": True,
            "release_next_phase_g": True,
            "full_swe_bench_score_claim_allowed": False,
            "full_dataset_claim_allowed": False,
            "leaderboard_equivalence_claim_allowed": False,
        },
    )
    write_json(
        repair_root / "phase_f_repair_loop_audit.json",
        {
            "status": "PASS",
            "release_next_phase_g": False,
            "phase_f_evaluator_proof_required": True,
            "required_next_action": "rerun_phase_f_evaluator_proof",
        },
    )
    write_json(full_manifest_root / "task_manifest.json", minimal_full_manifest())
    write_json(full_manifest_root / "loop_manifest.json", minimal_full_loop_manifest())
    (full_manifest_root / "full_campaign_acceptance_commands.md").write_text(
        "python3 tools/bench/audit_micro_tape_decision_dag.py --strict-vpput\n"
    )
    write_json(
        full_manifest_root / "CLAIM_BOUNDARY.json",
        {
            "schema_id": "FullSweBenchClaimBoundary.v1",
            "not_sampled_subset": True,
            "full_swe_bench_score_claim_allowed_before_run": False,
            "leaderboard_equivalence_claim_allowed_before_run": False,
        },
    )

    report = auditor.audit_full_swe_bench_readiness(
        phase_f_root=phase_f_root,
        repair_loop_root=repair_root,
        full_manifest_root=full_manifest_root,
    )

    assert report["status"] == "READY"
    assert report["full_swe_bench_ready"] is True
    assert report["release_phase_g"] is True
    assert report["blockers"] == []
    assert report["next_loop"] == "start_full_swe_bench_sharded_sealed_campaign"


def test_full_swe_bench_readiness_rejects_full_score_overclaim(tmp_path):
    auditor = load_module(
        "full_readiness_auditor",
        REPO / "tools/bench/audit_full_swe_bench_readiness.py",
    )
    phase_f_root = tmp_path / "phase_f"
    repair_root = tmp_path / "repair"
    full_manifest_root = tmp_path / "full_manifest"
    write_json(
        phase_f_root / "official_eval_replay_audit.json",
        {
            "status": "PASS",
            "official_evaluator_executable_replay": True,
            "release_next_phase_g": True,
            "full_swe_bench_score_claim_allowed": False,
            "full_dataset_claim_allowed": False,
            "leaderboard_equivalence_claim_allowed": False,
        },
    )
    write_json(
        repair_root / "phase_f_repair_loop_audit.json",
        {
            "status": "PASS",
            "release_next_phase_g": False,
            "phase_f_evaluator_proof_required": True,
            "required_next_action": "rerun_phase_f_evaluator_proof",
        },
    )
    manifest = minimal_full_manifest()
    write_json(full_manifest_root / "task_manifest.json", manifest)
    loop = minimal_full_loop_manifest()
    loop["full_score_claim_gate"]["full_score_claim_allowed_before_run"] = True
    write_json(full_manifest_root / "loop_manifest.json", loop)
    (full_manifest_root / "full_campaign_acceptance_commands.md").write_text("run\n")
    write_json(
        full_manifest_root / "CLAIM_BOUNDARY.json",
        {
            "not_sampled_subset": True,
            "full_swe_bench_score_claim_allowed_before_run": True,
            "leaderboard_equivalence_claim_allowed_before_run": False,
        },
    )

    report = auditor.audit_full_swe_bench_readiness(
        phase_f_root=phase_f_root,
        repair_loop_root=repair_root,
        full_manifest_root=full_manifest_root,
    )

    assert report["status"] == "FAIL"
    assert "full_score_claim_before_run_forbidden" in report["problems"]

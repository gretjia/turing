import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def load_validator():
    path = REPO / "tools" / "bench" / "validate_stage12_contract.py"
    spec = importlib.util.spec_from_file_location("stage12_validator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_contract(root: Path, *, task_count: int = 20, duplicates: bool = False, mutate_loop=None, claim_text=None):
    root.mkdir(parents=True, exist_ok=True)
    instance_ids = [f"django__django-{12000 + i}" for i in range(task_count)]
    if duplicates and len(instance_ids) >= 2:
        instance_ids[-1] = instance_ids[0]
    task_manifest = {
        "schema_id": "turingos.stage12.task_manifest.v1",
        "stage": "Stage12",
        "created_at_utc": "2026-06-28T00:00:00Z",
        "base_commit_sha": "38bae9971863db9196643084a926a7590c157cce",
        "source_dataset": "SWE-bench Verified Mini 50",
        "source_dataset_digest": "sha256:" + "a" * 64,
        "source_dataset_reference": "/tmp/turingos-swebench-data/verified-mini-50.jsonl",
        "official_harness_version": "repo-local",
        "official_harness_digest": "sha256:" + "b" * 64,
        "selection_policy": "first_20_from_frozen_verified_mini_50_before_run",
        "selection_seed": "stage12-first-20-v1",
        "task_count": task_count,
        "instance_ids": instance_ids,
        "excluded_instances": ["django__django-12406"],
        "exclusion_reason": {"django__django-12406": "outside first 20 frozen Stage12 slice"},
        "task_order": instance_ids,
        "frozen_before_run": True,
        "old_stage_evidence_immutable": True,
    }
    loop_manifest = {
        "schema_id": "turingos.stage12.loop_manifest.v1",
        "stage": "Stage12",
        "authorization_mode": "required",
        "no_hitl_policy": {"human_interventions_allowed": False},
        "human_interventions_allowed": False,
        "manual_patch_count_allowed": 0,
        "manual_rerun_selection_allowed": 0,
        "fallback_to_auto_authorization_allowed": False,
        "budget_profile": {
            "max_attempts_per_instance": 4,
            "max_wall_seconds_per_instance": 7200,
            "max_tokens_per_instance": 200000,
            "max_total_wall_seconds": 172800,
            "max_total_tokens": 4000000,
        },
        "retry_policy": {
            "allowed_retry_authorization_events": ["RetryAuthorized", "WorkerDispatchAuthorized"],
            "max_retries": 3,
            "budget_terminal_event": "BudgetExhausted",
        },
        "vpput_policy": {
            "failed_progress": 0,
            "solved_progress": 1,
            "cost_includes_all_agents_branches_failed_proposals_tool_stdout_context_reranks_abandoned_routes_wall_time": True,
        },
        "stage_release_policy": {
            "exact_20_bundles_required": True,
            "dry_run_can_release": False,
            "external_exact_sha_audit_required": True,
            "static_only_external_review_can_release": False,
        },
    }
    if mutate_loop:
        mutate_loop(loop_manifest)
    (root / "task_manifest.json").write_text(json.dumps(task_manifest, indent=2, sort_keys=True) + "\n")
    (root / "loop_manifest.json").write_text(json.dumps(loop_manifest, indent=2, sort_keys=True) + "\n")
    (root / "README.md").write_text(
        "Run: python3 tools/bench/validate_stage12_contract.py --root "
        "evidence/bench/mini_swe_bench_stage12_20task_loop_20260628\n"
    )
    (root / "stage12_acceptance_commands.md").write_text("Final assertion prints STAGE12_A01_CONTRACT_FROZEN.\n")
    (root / "stage12_claim_boundary.md").write_text(
        claim_text
        or "\n".join(
            [
                "Stage12 is 20-task scale/protocol evidence only.",
                "Stage12 is not statistically powered.",
                "Stage12 makes no product superiority claim.",
                "Stage12 makes no full SWE-bench score claim.",
                "Stage12 does not upgrade external CLI worker provenance to FULL.",
                "Stage12 release to Stage13 requires exact-SHA executable/fetching external audit.",
            ]
        )
        + "\n"
    )


def test_stage12_contract_accepts_valid_manifest(tmp_path):
    validator = load_validator()
    write_contract(tmp_path)

    report = validator.validate_root(tmp_path)

    assert report["status"] == "PASS"
    assert report["task_count"] == 20


def test_stage12_contract_rejects_19_or_21_tasks(tmp_path):
    validator = load_validator()
    for count in (19, 21):
        root = tmp_path / str(count)
        write_contract(root, task_count=count)
        report = validator.validate_root(root)
        assert report["status"] == "FAIL"
        assert any("task_count must be 20" in problem for problem in report["problems"])


def test_stage12_contract_rejects_duplicate_instance_id(tmp_path):
    validator = load_validator()
    write_contract(tmp_path, duplicates=True)

    report = validator.validate_root(tmp_path)

    assert report["status"] == "FAIL"
    assert any("duplicate instance_id" in problem for problem in report["problems"])


def test_stage12_contract_rejects_missing_budget_profile(tmp_path):
    validator = load_validator()
    write_contract(tmp_path, mutate_loop=lambda loop: loop.pop("budget_profile"))

    report = validator.validate_root(tmp_path)

    assert report["status"] == "FAIL"
    assert any("budget_profile missing" in problem for problem in report["problems"])


def test_stage12_contract_rejects_auth_auto_fallback(tmp_path):
    validator = load_validator()
    write_contract(tmp_path, mutate_loop=lambda loop: loop.update({"fallback_to_auto_authorization_allowed": True}))

    report = validator.validate_root(tmp_path)

    assert report["status"] == "FAIL"
    assert any("fallback_to_auto_authorization_allowed must be false" in problem for problem in report["problems"])


def test_stage12_contract_rejects_dry_run_release(tmp_path):
    validator = load_validator()

    def mutate(loop):
        loop["stage_release_policy"]["dry_run_can_release"] = True

    write_contract(tmp_path, mutate_loop=mutate)
    report = validator.validate_root(tmp_path)

    assert report["status"] == "FAIL"
    assert any("dry_run_can_release must be false" in problem for problem in report["problems"])


def test_stage12_contract_rejects_statistical_superiority_claim(tmp_path):
    validator = load_validator()
    write_contract(tmp_path, claim_text="Stage12 proves statistical superiority over baseline.\n")

    report = validator.validate_root(tmp_path)

    assert report["status"] == "FAIL"
    assert any("statistical superiority" in problem for problem in report["problems"])


def test_stage12_contract_rejects_full_score_claim(tmp_path):
    validator = load_validator()
    write_contract(tmp_path, claim_text="Stage12 proves full SWE-bench score.\n")

    report = validator.validate_root(tmp_path)

    assert report["status"] == "FAIL"
    assert any("full-score" in problem or "full SWE-bench" in problem for problem in report["problems"])


def test_stage12_contract_secret_scan_rejects_credential_like_marker(tmp_path):
    validator = load_validator()
    write_contract(tmp_path, claim_text="credential sk-" + "x" * 32 + "\n")

    report = validator.validate_root(tmp_path)

    assert report["status"] == "FAIL"
    assert any("credential-shaped value" in problem for problem in report["problems"])

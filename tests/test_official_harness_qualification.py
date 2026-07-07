import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PHASE_F_REAL = REPO / "evidence/bench/swe_bench_phase_f_evaluator_proof_real_20260628"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_complete_packet(root: Path, **overrides):
    predictions = root / "predictions_phase_f_20.jsonl"
    predictions.parent.mkdir(parents=True, exist_ok=True)
    predictions.write_text(
        json.dumps(
            {
                "instance_id": "django__django-11790",
                "model_name_or_path": "turingos-phase-f-official",
                "model_patch": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n",
                "candidate_patch_sha256": "sha256:" + "1" * 64,
                "candidate_source": "worker_derived",
            },
            sort_keys=True,
        )
        + "\n"
    )
    (root / "evaluation_results").mkdir(parents=True, exist_ok=True)
    result = root / "evaluation_results/results.json"
    write_json(result, {"resolved": {"django__django-11790": True}, "fail_to_pass": True, "pass_to_pass": True})
    stdout = root / "logs/run_stdout.txt"
    stderr = root / "logs/run_stderr.txt"
    docker_log = root / "logs/docker_build.log"
    stdout.parent.mkdir(parents=True, exist_ok=True)
    stdout.write_text("swebench stdout\n")
    stderr.write_text("")
    docker_log.write_text("docker build/cache log\n")
    data = {
        "schema_id": "turingos.official_swebench_harness_qualification.v1",
        "status": "PASS",
        "official_harness_kind": "upstream_swebench_docker",
        "command": "python -m swebench.harness.run_evaluation --dataset_name princeton-nlp/SWE-bench_Verified --split test --predictions_path predictions_phase_f_20.jsonl --run_id unit --max_workers 2",
        "dataset_name": "princeton-nlp/SWE-bench_Verified",
        "split": "test",
        "docker_environment_used": True,
        "swebench_package_present": True,
        "evaluation_results_present": True,
        "stdout_stderr_digests_present": True,
        "docker_build_or_cache_logs_present": True,
        "fail_to_pass_checked": True,
        "pass_to_pass_checked": True,
        "repo_local_evaluator_marked_official": False,
        "predictions_path": "predictions_phase_f_20.jsonl",
        "evaluation_results_path": "evaluation_results/results.json",
        "stdout_path": "logs/run_stdout.txt",
        "stderr_path": "logs/run_stderr.txt",
        "docker_build_or_cache_log_path": "logs/docker_build.log",
        "release_next_phase_g": True,
        "required_next_action": "regenerate_full_readiness_audit_with_official_harness_identity",
    }
    data.update(overrides)
    write_json(root / "official_harness_qualification.json", data)
    write_json(
        root / "CLAIM_BOUNDARY.json",
        {
            "artifact_kind": "OFFICIAL_SWEBENCH_DOCKER_HARNESS_QUALIFICATION",
            "full_swe_bench_score_claim_allowed": False,
            "leaderboard_equivalence_claim_allowed": False,
            "repo_local_evaluator_official_claim_allowed": False,
        },
    )


def test_official_harness_qualification_audit_accepts_complete_upstream_packet(tmp_path):
    auditor = load_module("official_harness_qualification", REPO / "tools/bench/audit_official_harness_qualification.py")
    write_complete_packet(tmp_path)

    report = auditor.audit_qualification(tmp_path)

    assert report["status"] == "PASS"
    assert report["official_harness_kind"] == "upstream_swebench_docker"
    assert report["release_next_phase_g"] is True


def test_official_harness_qualification_rejects_repo_local_evaluator(tmp_path):
    auditor = load_module("official_harness_qualification", REPO / "tools/bench/audit_official_harness_qualification.py")
    write_complete_packet(
        tmp_path,
        official_harness_kind="repo_local",
        command="python tools/bench/evaluate_django_swe_bench_patches.py --out x",
        repo_local_evaluator_marked_official=True,
    )

    report = auditor.audit_qualification(tmp_path)

    assert report["status"] == "FAIL"
    assert "official_harness_kind must be upstream_swebench_docker" in report["problems"]
    assert "repo-local evaluator cannot be marked official" in report["problems"]


def test_official_harness_qualification_rejects_missing_pass_to_pass(tmp_path):
    auditor = load_module("official_harness_qualification", REPO / "tools/bench/audit_official_harness_qualification.py")
    write_complete_packet(tmp_path, pass_to_pass_checked=False)

    report = auditor.audit_qualification(tmp_path)

    assert report["status"] == "FAIL"
    assert "pass_to_pass_checked must be true" in report["problems"]


def test_official_harness_qualification_rejects_gold_patch_prediction_source(tmp_path):
    auditor = load_module("official_harness_qualification", REPO / "tools/bench/audit_official_harness_qualification.py")
    write_complete_packet(tmp_path)
    row = json.loads((tmp_path / "predictions_phase_f_20.jsonl").read_text())
    row["candidate_source"] = "dataset_gold_patch"
    (tmp_path / "predictions_phase_f_20.jsonl").write_text(json.dumps(row) + "\n")

    report = auditor.audit_qualification(tmp_path)

    assert report["status"] == "FAIL"
    assert "prediction uses forbidden candidate source: django__django-11790" in report["problems"]


def test_official_harness_qualification_blocks_unresolved_phase_f_replay(tmp_path):
    auditor = load_module("official_harness_qualification", REPO / "tools/bench/audit_official_harness_qualification.py")
    write_complete_packet(tmp_path)
    write_json(
        tmp_path / "evaluation_results/results.json",
        {
            "total_instances": 500,
            "submitted_instances": 20,
            "completed_instances": 20,
            "resolved_instances": 19,
            "unresolved_instances": 1,
            "error_instances": 0,
            "resolved_ids": ["ok"] * 19,
            "unresolved_ids": ["django__django-11885"],
            "error_ids": [],
        },
    )
    q_path = tmp_path / "official_harness_qualification.json"
    q = json.loads(q_path.read_text())
    q["phase_f_expected_task_count"] = 20
    q["phase_f_requires_all_resolved"] = True
    q_path.write_text(json.dumps(q, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_qualification(tmp_path)

    assert report["status"] == "BLOCKED"
    assert report["release_next_phase_g"] is False
    assert report["required_next_action"] == "repair_unresolved_official_phase_f_target"
    assert "Phase F official replay unresolved ids: django__django-11885" in report["problems"]


def test_official_harness_qualification_builder_blocks_without_executable_results(tmp_path):
    builder = load_module("official_harness_builder", REPO / "tools/bench/build_official_harness_qualification.py")
    auditor = load_module("official_harness_qualification", REPO / "tools/bench/audit_official_harness_qualification.py")
    out = tmp_path / "qualification"

    builder.build_qualification(PHASE_F_REAL, out, swebench_package_present=False)
    report = auditor.audit_qualification(out)

    assert report["status"] == "BLOCKED"
    assert report["release_next_phase_g"] is False
    assert "swebench_package_present must be true" in report["problems"]
    assert "evaluation_results_present must be true" in report["problems"]
    assert (out / "predictions_phase_f_20.jsonl").exists()


def test_official_harness_qualification_cli_build_and_audit(tmp_path):
    out = tmp_path / "qualification_cli"

    subprocess.run(
        [
            "python3",
            "tools/bench/build_official_harness_qualification.py",
            "--phase-f-root",
            str(PHASE_F_REAL),
            "--out-root",
            str(out),
        ],
        cwd=REPO,
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/bench/audit_official_harness_qualification.py",
            "--root",
            str(out),
            "--out",
            str(out / "official_harness_qualification_audit.json"),
        ],
        cwd=REPO,
        check=False,
    )

    assert json.loads((out / "official_harness_qualification_audit.json").read_text())["status"] in {
        "PASS",
        "BLOCKED",
    }

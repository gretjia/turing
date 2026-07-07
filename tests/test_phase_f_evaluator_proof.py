import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
STAGE16_ROOT = REPO / "evidence/bench/swe_bench_stage16_full_sealed_20260628"
STAGE16R_ROOT = REPO / "evidence/bench/swe_bench_stage16r_unsolved_repair_20260628"
STAGE16R_REAL_COMPLETED_ROOT = REPO / "evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase_f_builder_creates_evaluator_proof_for_20_task_shard(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"

    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    claim = json.loads((out_dir / "CLAIM_BOUNDARY.json").read_text())
    patch_manifest = json.loads((out_dir / "patch_manifest.json").read_text())
    evidence_manifest = json.loads((out_dir / "required_evidence_manifest.json").read_text())

    assert report["status"] == "PARTIAL"
    assert report["task_count"] == 20
    assert report["full_swe_bench_score_claim_allowed"] is False
    assert report["full_dataset_claim_allowed"] is False
    assert report["leaderboard_equivalence_claim_allowed"] is False
    assert report["release_next_phase_g"] is False
    assert report["artifact_microtape_digest_binding"] is True
    assert report["all_solved_tasks_have_reproducible_official_eval"] is False
    assert report["all_candidate_accepts_have_required_evidence"] is True
    assert any("Stage16R" in blocker for blocker in report["blockers"])
    assert claim["not_full_swe_bench_dataset"] is True
    assert claim["leaderboard_equivalence_claim_allowed"] is False
    assert len(patch_manifest["patches"]) == 20
    assert len(evidence_manifest["required_evidence"]) == 80
    assert (out_dir / "phase_f_external_auditor_prompt.md").exists()
    harness = json.loads((out_dir / "official_harness_digest.json").read_text())
    assert harness["recorded_harness_artifact_sha256"] == harness["recorded_harness_digest"]
    assert (out_dir / harness["recorded_harness_artifact_path"]).exists()


def test_phase_f_builder_uses_real_stage16r_artifacts_when_available(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f_real"

    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_REAL_COMPLETED_ROOT, out_dir)
    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_REAL_COMPLETED_ROOT, out_dir)
    patch_manifest = json.loads((out_dir / "patch_manifest.json").read_text())
    stage16r_patches = [item for item in patch_manifest["patches"] if item["source_stage"] == "Stage16R"]

    assert report["status"] == "PASS"
    assert report["official_evaluator_executable_replay"] is True
    assert report["release_next_phase_g"] is False
    assert report["release_next_phase_g_as_internal_rehearsal"] is True
    assert report["release_next_phase_g_as_official_campaign"] is False
    assert report["official_harness_kind"] == "turingos_internal_target_test_replay"
    assert report["upstream_swebench_official_docker_harness"] is False
    assert report["phase_f_real_evaluator_proof_as_official_swebench"] == "BLOCKED"
    assert report["all_solved_tasks_have_reproducible_internal_replay"] is True
    assert len(stage16r_patches) == 7
    assert all(item["source_kind"] == "stage16r_real_worker_derived_patch_eval_artifact" for item in stage16r_patches)
    assert not (out_dir / "harness_inputs" / "tasks_20.jsonl").exists()
    evaluator_manifest = json.loads((out_dir / "evaluator_manifest.json").read_text())
    assert evaluator_manifest["tasks_jsonl_committed"] is False


def test_phase_f_audit_rejects_non_required_evidence_descriptor(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"
    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    manifest_path = out_dir / "required_evidence_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["required_evidence"][0]["required"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("required evidence" in problem for problem in report["problems"])


def test_phase_f_audit_rejects_patch_digest_mismatch(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"
    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    patch_manifest_path = out_dir / "patch_manifest.json"
    patch_manifest = json.loads(patch_manifest_path.read_text())
    patch_path = out_dir / patch_manifest["patches"][0]["candidate_patch_path"]
    patch_path.write_text(patch_path.read_text() + "\n# digest drift\n")

    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("candidate patch digest" in problem for problem in report["problems"])


def test_phase_f_audit_rejects_full_dataset_overclaim(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"
    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    claim_path = out_dir / "CLAIM_BOUNDARY.json"
    claim = json.loads(claim_path.read_text())
    claim["full_dataset_claim_allowed"] = True
    claim_path.write_text(json.dumps(claim, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("full dataset" in problem for problem in report["problems"])


def test_phase_f_audit_rejects_leaderboard_overclaim(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"
    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    claim_path = out_dir / "CLAIM_BOUNDARY.json"
    claim = json.loads(claim_path.read_text())
    claim["leaderboard_equivalence_claim_allowed"] = True
    claim_path.write_text(json.dumps(claim, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("leaderboard" in problem for problem in report["problems"])


def test_phase_f_audit_rejects_unsupported_evaluator_command(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"
    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    manifest_path = out_dir / "evaluator_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["evaluations"][0]["evaluator_command"] = (
        "python3 tools/bench/evaluate_django_swe_bench_patches.py "
        "--instance-id django__django-11790 --candidate-patch x --test-patch y"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("unsupported evaluator command" in problem for problem in report["problems"])


def test_phase_f_audit_rejects_evaluator_stdout_hash_drift(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"
    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    manifest_path = out_dir / "evaluator_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["evaluations"][0]["stdout_sha256"] = "sha256:" + "0" * 64
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("stdout manifest digest mismatch" in problem for problem in report["problems"])


def test_phase_f_audit_rejects_dataset_count_drift(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"
    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    manifest_path = out_dir / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["task_count"] = 21
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("dataset task_count" in problem for problem in report["problems"])


def test_phase_f_audit_rejects_extra_patch_entry(tmp_path):
    builder = load_module("phase_f_builder", REPO / "tools/bench/build_phase_f_evaluator_proof.py")
    auditor = load_module("phase_f_auditor", REPO / "tools/bench/audit_phase_f_evaluator_proof.py")
    out_dir = tmp_path / "phase_f"
    builder.build_phase_f_evaluator_proof(STAGE16_ROOT, STAGE16R_ROOT, out_dir)
    manifest_path = out_dir / "patch_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["patches"].append(dict(manifest["patches"][0], instance_id="extra__task"))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f(STAGE16_ROOT, STAGE16R_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("patch_manifest" in problem for problem in report["problems"])


def test_phase_f_cli_build_and_audit(tmp_path):
    out_dir = tmp_path / "phase_f_cli"

    subprocess.run(
        [
            "python3",
            "tools/bench/build_phase_f_evaluator_proof.py",
            "--stage16-root",
            str(STAGE16_ROOT),
            "--stage16r-root",
            str(STAGE16R_ROOT),
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/bench/audit_phase_f_evaluator_proof.py",
            "--stage16-root",
            str(STAGE16_ROOT),
            "--stage16r-root",
            str(STAGE16R_ROOT),
            "--root",
            str(out_dir),
            "--out",
            str(out_dir / "official_eval_replay_audit.json"),
        ],
        cwd=REPO,
        check=True,
    )

    report = json.loads((out_dir / "official_eval_replay_audit.json").read_text())
    assert report["status"] == "PARTIAL"
    assert report["task_count"] == 20

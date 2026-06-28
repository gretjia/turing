import importlib.util
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PHASE_F_ROOT = REPO / "evidence/bench/swe_bench_phase_f_evaluator_proof_20260628"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_stage16r_source_artifacts_replayable(source_root: Path) -> None:
    manifest_path = source_root / "patch_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    candidate_diff = (
        "diff --git a/django/example.py b/django/example.py\n"
        "--- a/django/example.py\n"
        "+++ b/django/example.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    test_diff = (
        "diff --git a/tests/example.py b/tests/example.py\n"
        "--- a/tests/example.py\n"
        "+++ b/tests/example.py\n"
        "@@ -1 +1 @@\n"
        "-old test\n"
        "+new test\n"
    )
    for patch in manifest["patches"]:
        if patch["source_stage"] != "Stage16R":
            continue
        candidate_path = source_root / patch["candidate_patch_path"]
        test_path = source_root / patch["test_patch_path"]
        candidate_path.write_text(candidate_diff)
        test_path.write_text(test_diff)
        patch["candidate_patch_sha256"] = _sha256_text(candidate_diff)
        patch["official_test_patch_sha256"] = _sha256_text(test_diff)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def test_phase_f_repair_loop_blocks_phase_g_until_real_replayable_diffs_exist(tmp_path):
    builder = load_module("phase_f_repair_builder", REPO / "tools/bench/build_phase_f_repair_loop.py")
    auditor = load_module("phase_f_repair_auditor", REPO / "tools/bench/audit_phase_f_repair_loop.py")
    out_dir = tmp_path / "phase_f_repair"

    builder.build_phase_f_repair_loop(PHASE_F_ROOT, out_dir)
    report = auditor.audit_phase_f_repair_loop(PHASE_F_ROOT, out_dir)
    claim = json.loads((out_dir / "CLAIM_BOUNDARY.json").read_text())
    manifest = json.loads((out_dir / "repair_manifest.json").read_text())

    assert report["status"] == "BLOCKED"
    assert report["release_next_phase_g"] is False
    assert report["repair_target_count"] == 7
    assert report["replayable_repair_bundle_count"] == 0
    assert report["gold_patch_shortcut_rejected"] is True
    assert report["old_microtape_immutable"] is True
    assert report["required_next_action"] == "fresh_stage16r_real_evaluator_bundles"
    assert all(not target["existing_artifacts_replayable"] for target in report["repair_targets"])
    assert all(target["required_next_action"] == "fresh_stage16r_real_evaluator_bundle" for target in report["repair_targets"])
    assert claim["full_swe_bench_score_claim_allowed"] is False
    assert claim["full_dataset_claim_allowed"] is False
    assert claim["leaderboard_equivalence_claim_allowed"] is False
    assert claim["phase_g_release_allowed"] is False
    assert manifest["dataset_gold_patch_use_allowed"] is False
    assert (out_dir / "next_stage16r_real_evaluator_contract.md").exists()
    assert (out_dir / "phase_f_repair_external_auditor_prompt.md").exists()


def test_phase_f_repair_loop_rejects_gold_patch_shortcut(tmp_path):
    builder = load_module("phase_f_repair_builder", REPO / "tools/bench/build_phase_f_repair_loop.py")
    auditor = load_module("phase_f_repair_auditor", REPO / "tools/bench/audit_phase_f_repair_loop.py")
    out_dir = tmp_path / "phase_f_repair"
    builder.build_phase_f_repair_loop(PHASE_F_ROOT, out_dir)
    manifest_path = out_dir / "repair_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dataset_gold_patch_use_allowed"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f_repair_loop(PHASE_F_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("gold patch" in problem for problem in report["problems"])


def test_phase_f_repair_loop_rejects_phase_g_release_overclaim(tmp_path):
    builder = load_module("phase_f_repair_builder", REPO / "tools/bench/build_phase_f_repair_loop.py")
    auditor = load_module("phase_f_repair_auditor", REPO / "tools/bench/audit_phase_f_repair_loop.py")
    out_dir = tmp_path / "phase_f_repair"
    builder.build_phase_f_repair_loop(PHASE_F_ROOT, out_dir)
    claim_path = out_dir / "CLAIM_BOUNDARY.json"
    claim = json.loads(claim_path.read_text())
    claim["phase_g_release_allowed"] = True
    claim_path.write_text(json.dumps(claim, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f_repair_loop(PHASE_F_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("Phase G" in problem for problem in report["problems"])


def test_phase_f_repair_loop_rejects_missing_repair_target(tmp_path):
    builder = load_module("phase_f_repair_builder", REPO / "tools/bench/build_phase_f_repair_loop.py")
    auditor = load_module("phase_f_repair_auditor", REPO / "tools/bench/audit_phase_f_repair_loop.py")
    out_dir = tmp_path / "phase_f_repair"
    builder.build_phase_f_repair_loop(PHASE_F_ROOT, out_dir)
    manifest_path = out_dir / "repair_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["repair_targets"] = manifest["repair_targets"][:-1]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_phase_f_repair_loop(PHASE_F_ROOT, out_dir)

    assert report["status"] == "FAIL"
    assert any("exactly the Phase F Stage16R blocker targets" in problem for problem in report["problems"])


def test_phase_f_repair_loop_structural_pass_still_requires_phase_f_evaluator_proof(tmp_path):
    builder = load_module("phase_f_repair_builder", REPO / "tools/bench/build_phase_f_repair_loop.py")
    auditor = load_module("phase_f_repair_auditor", REPO / "tools/bench/audit_phase_f_repair_loop.py")
    source_root = tmp_path / "phase_f_source"
    out_dir = tmp_path / "phase_f_repair"
    shutil.copytree(PHASE_F_ROOT, source_root)
    _make_stage16r_source_artifacts_replayable(source_root)

    builder.build_phase_f_repair_loop(source_root, out_dir)
    report = auditor.audit_phase_f_repair_loop(source_root, out_dir)

    assert report["status"] == "PASS"
    assert report["replayable_repair_bundle_count"] == 7
    assert report["release_next_phase_g"] is False
    assert report["required_next_action"] == "rerun_phase_f_evaluator_proof"


def test_phase_f_repair_loop_cli_build_and_audit(tmp_path):
    out_dir = tmp_path / "phase_f_repair_cli"

    subprocess.run(
        [
            "python3",
            "tools/bench/build_phase_f_repair_loop.py",
            "--phase-f-root",
            str(PHASE_F_ROOT),
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/bench/audit_phase_f_repair_loop.py",
            "--phase-f-root",
            str(PHASE_F_ROOT),
            "--root",
            str(out_dir),
            "--out",
            str(out_dir / "phase_f_repair_loop_audit.json"),
        ],
        cwd=REPO,
        check=True,
    )

    report = json.loads((out_dir / "phase_f_repair_loop_audit.json").read_text())
    assert report["status"] == "BLOCKED"
    assert report["release_next_phase_g"] is False

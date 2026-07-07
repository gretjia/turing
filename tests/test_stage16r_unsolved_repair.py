import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SOURCE_STAGE16 = REPO / "evidence/bench/swe_bench_stage16_full_sealed_20260628"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage16r_builder_repairs_exact_7_unsolved_and_keeps_claim_boundary(tmp_path):
    builder = load_module("builder", REPO / "tools/bench/build_stage16r_unsolved_repair.py")
    auditor = load_module("auditor", REPO / "tools/bench/audit_stage16r_repair.py")
    out_dir = tmp_path / "stage16r"

    builder.build_stage16r_repair(SOURCE_STAGE16, out_dir)
    report = auditor.audit_stage16r(SOURCE_STAGE16, out_dir)
    claim = json.loads((out_dir / "CLAIM_BOUNDARY.json").read_text())

    assert report["status"] == "PASS"
    assert report["source_unsolved_count"] == 7
    assert report["repaired_count"] == 7
    assert report["remaining_unsolved_count"] == 0
    assert report["twenty_task_shard_after_repair"]["total_solved_count"] == 20
    assert report["twenty_task_shard_after_repair"]["twenty_task_shard_full_pass_claim_allowed"] is True
    assert report["full_swe_bench_score_claim_allowed"] is False
    assert claim["not_full_swe_bench_dataset"] is True
    assert claim["full_swe_bench_score_claim_allowed"] is False
    assert claim["twenty_task_shard_full_pass_claim_allowed"] is True
    assert len((out_dir / "bundle_sha256s.txt").read_text().splitlines()) == 7
    assert (out_dir / "stage16r_external_auditor_prompt.md").exists()


def test_stage16r_rejects_full_swe_bench_overclaim(tmp_path):
    builder = load_module("builder", REPO / "tools/bench/build_stage16r_unsolved_repair.py")
    auditor = load_module("auditor", REPO / "tools/bench/audit_stage16r_repair.py")
    out_dir = tmp_path / "stage16r"
    builder.build_stage16r_repair(SOURCE_STAGE16, out_dir)
    claim = json.loads((out_dir / "CLAIM_BOUNDARY.json").read_text())
    claim["full_swe_bench_score_claim_allowed"] = True
    (out_dir / "CLAIM_BOUNDARY.json").write_text(json.dumps(claim, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_stage16r(SOURCE_STAGE16, out_dir)

    assert report["status"] == "FAIL"
    assert any("full SWE-bench score claim" in problem for problem in report["problems"])


def test_stage16r_rejects_missing_one_repair_bundle(tmp_path):
    builder = load_module("builder", REPO / "tools/bench/build_stage16r_unsolved_repair.py")
    auditor = load_module("auditor", REPO / "tools/bench/audit_stage16r_repair.py")
    out_dir = tmp_path / "stage16r"
    builder.build_stage16r_repair(SOURCE_STAGE16, out_dir)
    first_bundle = next((out_dir / "instances").glob("*/micro_tape.bundle"))
    first_bundle.unlink()

    report = auditor.audit_stage16r(SOURCE_STAGE16, out_dir)

    assert report["status"] == "FAIL"
    assert any("missing repair bundle" in problem for problem in report["problems"])


def test_stage16r_rejects_visible_capsule_leak(tmp_path):
    builder = load_module("builder", REPO / "tools/bench/build_stage16r_unsolved_repair.py")
    auditor = load_module("auditor", REPO / "tools/bench/audit_stage16r_repair.py")
    out_dir = tmp_path / "stage16r"
    builder.build_stage16r_repair(SOURCE_STAGE16, out_dir)
    coverage = json.loads((out_dir / "substrate_coverage.json").read_text())
    coverage["turingos_arm_runs"][0]["visible_capsule_text"] = "raw stderr hidden predicate pput formula"
    (out_dir / "substrate_coverage.json").write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_stage16r(SOURCE_STAGE16, out_dir)

    assert report["status"] == "FAIL"
    assert any("visible capsule" in problem for problem in report["problems"])


def test_stage16r_cli_build_and_audit(tmp_path):
    out_dir = tmp_path / "stage16r_cli"

    subprocess.run(
        [
            "python3",
            "tools/bench/build_stage16r_unsolved_repair.py",
            "--source-stage16-root",
            str(SOURCE_STAGE16),
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/bench/audit_stage16r_repair.py",
            "--source-stage16-root",
            str(SOURCE_STAGE16),
            "--root",
            str(out_dir),
            "--out",
            str(out_dir / "stage16r_repair_audit.json"),
        ],
        cwd=REPO,
        check=True,
    )

    report = json.loads((out_dir / "stage16r_repair_audit.json").read_text())
    assert report["status"] == "PASS"
    assert report["repaired_count"] == 7
    assert report["remaining_unsolved_count"] == 0

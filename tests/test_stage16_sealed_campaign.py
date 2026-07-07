import importlib.util
import json
import shutil
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
STAGE12_ROOT = REPO / "evidence/bench/mini_swe_bench_stage12_20task_loop_20260628"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage16_builder_creates_sealed_campaign_with_full_pass_gate(tmp_path):
    builder = load_module("stage16_builder", REPO / "tools/bench/build_stage16_sealed_campaign.py")
    audit = load_module("stage16_audit", REPO / "tools/bench/audit_stage16_sealed_campaign.py")
    out_dir = tmp_path / "stage16"

    builder.build_stage16_campaign(STAGE12_ROOT, out_dir)
    report = audit.audit_stage16(out_dir)

    assert report["status"] == "PASS"
    assert report["stage16_replay_campaign_pass"] is True
    assert report["stage16_full_pass_claim_allowed"] is False
    assert report["run_count"] == 20
    assert report["solved_count"] == 13
    assert report["unsolved_count"] == 7
    assert report["full_score_claim_gate"]["status"] == "PASS"
    assert report["claim_boundary"] == "sealed replay campaign; no full-score claim because unsolved_count > 0"
    claim = json.loads((out_dir / "CLAIM_BOUNDARY.json").read_text())
    assert claim["stage16_artifact_kind"] == "STAGE16_SHARD_SEALED_REPLAY"
    assert claim["not_full_swe_bench_dataset"] is True
    assert claim["full_swe_bench_campaign_not_run"] is True
    assert claim["full_score_claim_allowed"] is False
    assert (out_dir / "stage16_aggregate_report.json").exists()
    assert (out_dir / "stage16_external_auditor_prompt.md").exists()
    assert (out_dir / "instances/django__django-11790/micro_tape.bundle").exists()
    market = json.loads((out_dir / "stage16_market_audit.json").read_text())
    assert len(market["per_instance"]) == 20
    vpput = json.loads((out_dir / "stage16_vpput_report.json").read_text())
    assert all(run["vpput_cost_completeness"] for run in vpput["runs"])


def test_stage16_audit_rejects_full_pass_overclaim_when_unsolved_exist(tmp_path):
    builder = load_module("stage16_builder", REPO / "tools/bench/build_stage16_sealed_campaign.py")
    audit = load_module("stage16_audit", REPO / "tools/bench/audit_stage16_sealed_campaign.py")
    out_dir = tmp_path / "stage16"
    builder.build_stage16_campaign(STAGE12_ROOT, out_dir)
    aggregate = out_dir / "stage16_aggregate_report.json"
    data = json.loads(aggregate.read_text())
    data["stage16_full_pass_claim_allowed"] = True
    aggregate.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = audit.audit_stage16(out_dir)

    assert report["status"] == "FAIL"
    assert any("full-pass claim" in problem for problem in report["problems"])


def test_stage16_audit_rejects_missing_bundle(tmp_path):
    builder = load_module("stage16_builder", REPO / "tools/bench/build_stage16_sealed_campaign.py")
    audit = load_module("stage16_audit", REPO / "tools/bench/audit_stage16_sealed_campaign.py")
    out_dir = tmp_path / "stage16"
    builder.build_stage16_campaign(STAGE12_ROOT, out_dir)
    first_bundle = next((out_dir / "instances").glob("*/micro_tape.bundle"))
    first_bundle.unlink()

    report = audit.audit_stage16(out_dir)

    assert report["status"] == "FAIL"
    assert any("missing bundle" in problem for problem in report["problems"])


def test_stage16_cli_build_and_audit(tmp_path):
    out_dir = tmp_path / "stage16_cli"

    subprocess.run(
        [
            "python3",
            "tools/bench/build_stage16_sealed_campaign.py",
            "--source-root",
            str(STAGE12_ROOT),
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/bench/audit_stage16_sealed_campaign.py",
            "--root",
            str(out_dir),
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )

    assert json.loads((out_dir / "stage16_aggregate_report.json").read_text())["stage16_replay_campaign_pass"] is True
    assert json.loads((out_dir / "stage16_aggregate_report.json").read_text())["stage16_full_pass_claim_allowed"] is False

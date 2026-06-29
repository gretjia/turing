import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PHASE_G_MANIFEST = REPO / "evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/task_manifest.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_verified_500_manifest_creates_10_sealed_50_task_shards(tmp_path):
    builder = load_module("campaign_manifest_builder", REPO / "tools/bench/build_verified_500_manifest.py")
    auditor = load_module("campaign_manifest_auditor", REPO / "tools/bench/audit_verified_500_manifest.py")
    out = tmp_path / "campaign"

    builder.build_manifest(PHASE_G_MANIFEST, out)
    report = auditor.audit_manifest(out)

    assert report["status"] == "PASS"
    assert report["task_count"] == 500
    assert report["shard_count"] == 10
    assert report["shard_size"] == 50
    assert report["ipqc_window_size"] == 10
    assert report["one_shot_500_run"] == "FORBIDDEN"
    assert report["official_harness_identity_gate"] == "REQUIRED"
    assert report["selection_policy"] == "ALL"
    manifest = json.loads((out / "task_manifest.json").read_text())
    assert len({item["instance_id"] for item in manifest["tasks"]}) == 500
    assert {item["shard_id"] for item in manifest["tasks"]} == {f"S{i:02d}" for i in range(10)}
    assert all(len(list((out / "shards").glob(f"{shard}/shard_manifest.json"))) == 1 for shard in {f"S{i:02d}" for i in range(10)})


def test_campaign_manifest_audit_rejects_one_shot_500_policy(tmp_path):
    builder = load_module("campaign_manifest_builder", REPO / "tools/bench/build_verified_500_manifest.py")
    auditor = load_module("campaign_manifest_auditor", REPO / "tools/bench/audit_verified_500_manifest.py")
    out = tmp_path / "campaign"
    builder.build_manifest(PHASE_G_MANIFEST, out)
    config_path = out / "campaign_config.json"
    config = json.loads(config_path.read_text())
    config["one_shot_500_run"] = "ALLOWED"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")

    report = auditor.audit_manifest(out)

    assert report["status"] == "FAIL"
    assert "one_shot_500_run must be FORBIDDEN" in report["problems"]


def test_campaign_manifest_cli_build_and_audit(tmp_path):
    out = tmp_path / "campaign_cli"

    subprocess.run(
        [
            "python3",
            "tools/bench/build_verified_500_manifest.py",
            "--source-manifest",
            str(PHASE_G_MANIFEST),
            "--out-root",
            str(out),
        ],
        cwd=REPO,
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/bench/audit_verified_500_manifest.py",
            "--root",
            str(out),
            "--out",
            str(out / "manifest_audit.json"),
        ],
        cwd=REPO,
        check=True,
    )

    assert json.loads((out / "manifest_audit.json").read_text())["status"] == "PASS"

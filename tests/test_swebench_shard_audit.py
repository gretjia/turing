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


def write_task(root: Path, shard: str, instance: str, *, resolved: bool = True, missing_evidence: bool = False):
    task = root / f"shards/{shard}/tasks/{instance}"
    task.mkdir(parents=True, exist_ok=True)
    required = [
        "task_manifest_entry.json",
        "worker_capsule.md",
        "worker_receipt.json",
        "candidate.patch",
        "candidate.patch.sha256",
        "prediction_row.json",
        "official_eval/evaluation_result.json",
        "official_eval/stdout.sha256",
        "official_eval/stderr.sha256",
        "microtape/bundle.json",
        "microtape/replay_report.json",
        "qc_report.json",
    ]
    for name in required:
        path = task / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if name.endswith(".json") else "ok\n")
    if missing_evidence:
        (task / "official_eval/stdout.sha256").unlink()
    (task / "official_eval/evaluation_result.json").write_text(
        json.dumps({"resolved": resolved, "fail_to_pass": resolved, "pass_to_pass": True}) + "\n"
    )
    (task / "microtape/replay_report.json").write_text(json.dumps({"status": "PASS"}) + "\n")
    (task / "qc_report.json").write_text(json.dumps({"status": "PASS", "failure_class": None if resolved else "SEMANTIC_FAIL"}) + "\n")


def write_shard(root: Path, shard: str = "S00", count: int = 50, missing_evidence: bool = False):
    ids = [f"repo__task-{i:03d}" for i in range(count)]
    shard_dir = root / "shards" / shard
    shard_dir.mkdir(parents=True, exist_ok=True)
    (shard_dir / "shard_manifest.json").write_text(
        json.dumps({"shard_id": shard, "tasks": [{"instance_id": i} for i in ids]}, indent=2) + "\n"
    )
    for index, instance in enumerate(ids):
        write_task(root, shard, instance, resolved=index % 2 == 0, missing_evidence=missing_evidence and index == 0)
    for window in range(5):
        report = {
            "window_id": f"{shard}-W{window:02d}",
            "task_count": 10,
            "completed": 10,
            "missing_evidence": 0,
            "digest_mismatch": 0,
            "gold_patch_guard_violation": 0,
            "official_harness_identity_violation": 0,
            "infra_failed": 0,
            "repeated_failure_classes": [],
        }
        (shard_dir / "ipqc").mkdir(exist_ok=True)
        (shard_dir / f"ipqc/{shard}_W{window:02d}_ipqc_report.json").write_text(json.dumps(report) + "\n")


def test_shard_audit_passes_complete_50_task_shard(tmp_path):
    auditor = load_module("shard_auditor", REPO / "tools/bench/audit_swebench_shard.py")
    write_shard(tmp_path)

    report = auditor.audit_shard(tmp_path, "S00")

    assert report["status"] == "PASS"
    assert report["task_count"] == 50
    assert report["completed_count"] == 50
    assert report["official_harness_identity"] == "PASS"
    assert report["gold_patch_guard"] == "PASS"
    assert report["microtape_replay"] == "PASS"
    assert report["next_action"] == "release_next_shard"


def test_shard_audit_blocks_missing_required_evidence(tmp_path):
    auditor = load_module("shard_auditor", REPO / "tools/bench/audit_swebench_shard.py")
    write_shard(tmp_path, missing_evidence=True)

    report = auditor.audit_shard(tmp_path, "S00")

    assert report["status"] == "BLOCKED"
    assert report["required_evidence_missing"] == 1
    assert report["next_action"] == "rerun_blocked_tasks"


def test_shard_audit_cli(tmp_path):
    write_shard(tmp_path)

    subprocess.run(
        ["python3", "tools/bench/audit_swebench_shard.py", "--root", str(tmp_path), "--shard", "S00"],
        cwd=REPO,
        check=True,
    )

    assert json.loads((tmp_path / "shards/S00/shard_audit.json").read_text())["status"] == "PASS"

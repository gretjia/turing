import importlib.util
import hashlib
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


def make_patch(path: Path, text: str = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_candidate_audit(root: Path, shard: str, instance_id: str, patch_path: Path, *, status: str = "PASS"):
    patch_sha = "sha256:" + hashlib.sha256(patch_path.read_bytes()).hexdigest()
    audit_path = root / f"shards/{shard}/tasks/{instance_id}/worker_candidate_audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(
            {
                "status": status,
                "instance_id": instance_id,
                "candidate_source": "worker_derived",
                "submitted_patch_scope": "source_only",
                "candidate_patch_path": str(patch_path.relative_to(root)),
                "candidate_patch_sha256": patch_sha,
                "problems": [] if status == "PASS" else ["forced failure"],
            },
            indent=2,
        )
        + "\n"
    )


def test_predictions_builder_uses_worker_patch_digest_and_writes_jsonl(tmp_path):
    builder = load_module("predictions_builder", REPO / "tools/bench/build_predictions_jsonl.py")
    root = tmp_path / "campaign"
    patch = root / "shards/S00/tasks/repo__task-1/candidate.patch"
    make_patch(patch)
    write_candidate_audit(root, "S00", "repo__task-1", patch)
    shard_manifest = root / "shards/S00/shard_manifest.json"
    shard_manifest.parent.mkdir(parents=True, exist_ok=True)
    shard_manifest.write_text(
        json.dumps(
            {
                "shard_id": "S00",
                "tasks": [
                    {
                        "instance_id": "repo__task-1",
                        "candidate_patch_path": "shards/S00/tasks/repo__task-1/candidate.patch",
                        "candidate_source": "worker_derived",
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )

    report = builder.build_predictions(root, "S00")

    assert report["status"] == "PASS"
    row = json.loads((root / "predictions/shard_S00_predictions.jsonl").read_text().strip())
    assert row["instance_id"] == "repo__task-1"
    assert row["model_patch"].startswith("diff --git")
    assert row["candidate_patch_sha256"].startswith("sha256:")
    assert row["candidate_source"] == "worker_derived"


def test_predictions_builder_rejects_candidate_without_passed_audit(tmp_path):
    builder = load_module("predictions_builder", REPO / "tools/bench/build_predictions_jsonl.py")
    root = tmp_path / "campaign"
    patch = root / "shards/S00/tasks/repo__task-1/candidate.patch"
    make_patch(patch)
    shard_manifest = root / "shards/S00/shard_manifest.json"
    shard_manifest.parent.mkdir(parents=True, exist_ok=True)
    shard_manifest.write_text(
        json.dumps(
            {
                "shard_id": "S00",
                "tasks": [
                    {
                        "instance_id": "repo__task-1",
                        "candidate_patch_path": "shards/S00/tasks/repo__task-1/candidate.patch",
                        "candidate_source": "worker_derived",
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )

    report = builder.build_predictions(root, "S00")

    assert report["status"] == "FAIL"
    assert "candidate audit missing: repo__task-1" in report["problems"]


def test_gold_patch_guard_rejects_candidate_sourced_from_dataset_patch(tmp_path):
    auditor = load_module("gold_patch_guard", REPO / "tools/bench/audit_gold_patch_guard.py")
    root = tmp_path / "campaign"
    patch = root / "shards/S00/tasks/repo__task-1/candidate.patch"
    make_patch(patch)
    write_candidate_audit(root, "S00", "repo__task-1", patch)
    shard_manifest = root / "shards/S00/shard_manifest.json"
    shard_manifest.parent.mkdir(parents=True, exist_ok=True)
    shard_manifest.write_text(
        json.dumps(
            {
                "shard_id": "S00",
                "tasks": [
                    {
                        "instance_id": "repo__task-1",
                        "candidate_patch_path": "shards/S00/tasks/repo__task-1/candidate.patch",
                        "candidate_source": "dataset_gold_patch",
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )

    report = auditor.audit_shard(root, "S00")

    assert report["status"] == "FAIL"
    assert "dataset gold patch used as candidate source: repo__task-1" in report["problems"]


def test_predictions_builder_cli(tmp_path):
    root = tmp_path / "campaign"
    patch = root / "shards/S00/tasks/repo__task-1/candidate.patch"
    make_patch(patch)
    write_candidate_audit(root, "S00", "repo__task-1", patch)
    shard_manifest = root / "shards/S00/shard_manifest.json"
    shard_manifest.parent.mkdir(parents=True, exist_ok=True)
    shard_manifest.write_text(
        json.dumps(
            {
                "shard_id": "S00",
                "tasks": [
                    {
                        "instance_id": "repo__task-1",
                        "candidate_patch_path": "shards/S00/tasks/repo__task-1/candidate.patch",
                        "candidate_source": "worker_derived",
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )

    subprocess.run(
        ["python3", "tools/bench/build_predictions_jsonl.py", "--root", str(root), "--shard", "S00"],
        cwd=REPO,
        check=True,
    )

    assert (root / "predictions/shard_S00_predictions.jsonl").exists()

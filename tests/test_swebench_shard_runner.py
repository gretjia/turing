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


def write_shard_manifest(root: Path, shard: str = "S00", count: int = 2, *, source: str = "worker_derived"):
    shard_dir = root / "shards" / shard
    shard_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        {
            "instance_id": f"repo__task-{index}",
            "candidate_source": source,
            "candidate_patch_path": f"shards/{shard}/tasks/repo__task-{index}/candidate.patch",
        }
        for index in range(count)
    ]
    (shard_dir / "shard_manifest.json").write_text(
        json.dumps({"shard_id": shard, "tasks": tasks}, indent=2) + "\n",
        encoding="utf-8",
    )
    return [task["instance_id"] for task in tasks]


def write_predictions(root: Path, shard: str, rows: list[dict[str, str]]):
    path = root / "predictions" / f"shard_{shard}_predictions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def prediction(instance_id: str, patch: str | None = None, *, source: str = "worker_derived"):
    return {
        "instance_id": instance_id,
        "model_name_or_path": "turingos-test",
        "model_patch": patch or "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n",
        "candidate_patch_sha256": "sha256:" + "0" * 64,
        "candidate_source": source,
    }


def test_shard_runner_blocks_execution_without_predictions(tmp_path):
    runner = load_module("shard_runner", REPO / "tools/bench/run_swebench_shard.py")
    root = tmp_path / "campaign"
    write_shard_manifest(root)

    packet = runner.build_command(root, "S00", 2, execution_requested=True)

    assert packet["status"] == "BLOCKED"
    assert packet["execute_now"] is False
    assert "predictions missing" in packet["problems"]


def test_shard_runner_blocks_execution_when_prediction_count_mismatches_manifest(tmp_path):
    runner = load_module("shard_runner", REPO / "tools/bench/run_swebench_shard.py")
    root = tmp_path / "campaign"
    instance_ids = write_shard_manifest(root, count=2)
    write_predictions(root, "S00", [prediction(instance_ids[0])])

    packet = runner.build_command(root, "S00", 2, execution_requested=True)

    assert packet["status"] == "BLOCKED"
    assert "prediction count mismatch: expected 2, got 1" in packet["problems"]


def test_shard_runner_blocks_execution_with_non_worker_candidate_source(tmp_path):
    runner = load_module("shard_runner", REPO / "tools/bench/run_swebench_shard.py")
    root = tmp_path / "campaign"
    instance_ids = write_shard_manifest(root, count=1)
    write_predictions(root, "S00", [prediction(instance_ids[0], source="dataset_gold_patch")])

    packet = runner.build_command(root, "S00", 2, execution_requested=True)

    assert packet["status"] == "BLOCKED"
    assert f"prediction source is not worker-derived: {instance_ids[0]}" in packet["problems"]


def test_shard_runner_blocks_execution_with_non_unified_diff_prediction(tmp_path):
    runner = load_module("shard_runner", REPO / "tools/bench/run_swebench_shard.py")
    root = tmp_path / "campaign"
    instance_ids = write_shard_manifest(root, count=1)
    write_predictions(root, "S00", [prediction(instance_ids[0], patch="not a diff\n")])

    packet = runner.build_command(root, "S00", 2, execution_requested=True)

    assert packet["status"] == "BLOCKED"
    assert f"prediction patch is not a unified diff: {instance_ids[0]}" in packet["problems"]


def test_shard_runner_marks_execution_ready_with_complete_worker_predictions(tmp_path):
    runner = load_module("shard_runner", REPO / "tools/bench/run_swebench_shard.py")
    root = tmp_path / "campaign"
    instance_ids = write_shard_manifest(root, count=2)
    write_predictions(root, "S00", [prediction(instance_id) for instance_id in instance_ids])

    packet = runner.build_command(root, "S00", 2, execution_requested=True)

    assert packet["status"] == "READY_TO_EXECUTE"
    assert packet["execute_now"] is True
    assert packet["validation"]["prediction_count"] == 2
    assert packet["problems"] == []


def test_shard_runner_execute_cli_exits_nonzero_when_predictions_are_missing(tmp_path):
    root = tmp_path / "campaign"
    write_shard_manifest(root)

    proc = subprocess.run(
        [
            "python3",
            "tools/bench/run_swebench_shard.py",
            "--root",
            str(root),
            "--shard",
            "S00",
            "--execute",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert proc.returncode == 1
    assert json.loads((root / "shards/S00/shard_run_packet.json").read_text())["status"] == "BLOCKED"

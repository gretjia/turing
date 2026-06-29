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


def write_dataset_jsonl(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "repo": "astropy/astropy",
        "instance_id": "astropy__astropy-12907",
        "base_commit": "d16bfe05a744909de4b27f5875fe0d4ed41ce607",
        "problem_statement": "Fix separability for nested compound models.",
        "version": "4.3",
        "difficulty": "15 min - 1 hour",
        "environment_setup_commit": "298ccb478e6bf092953bca67a3d29dc6c35f6752",
        "patch": "diff --git a/gold.py b/gold.py\n",
        "test_patch": "diff --git a/test_gold.py b/test_gold.py\n",
        "FAIL_TO_PASS": "[\"hidden test\"]",
        "PASS_TO_PASS": "[\"hidden regression\"]",
        "hints_text": "do not expose hints in first worker-safe packet",
    }
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")


def write_shard_manifest(root: Path):
    path = root / "shards/S00/shard_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "shard_id": "S00",
                "tasks": [
                    {
                        "instance_id": "astropy__astropy-12907",
                        "ipqc_window_id": "S00-W00",
                        "candidate_source_policy": "worker_derived_patch_only",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_materializer_writes_worker_safe_packet_without_gold_or_test_fields(tmp_path):
    materializer = load_module(
        "worker_safe_materializer", REPO / "tools/bench/materialize_swebench_worker_safe_tasks.py"
    )
    root = tmp_path / "campaign"
    write_shard_manifest(root)
    dataset = tmp_path / "dataset.jsonl"
    write_dataset_jsonl(dataset)

    report = materializer.materialize(root, "S00", "S00-W00", dataset_jsonl=dataset)

    assert report["status"] == "PASS"
    packet = json.loads(
        (root / "shards/S00/ipqc/S00-W00/worker_safe_tasks/astropy__astropy-12907/task_packet.json").read_text()
    )
    rendered = json.dumps(packet, sort_keys=True)
    assert packet["instance_id"] == "astropy__astropy-12907"
    assert packet["problem_statement"] == "Fix separability for nested compound models."
    assert "gold.py" not in rendered
    assert "test_gold.py" not in rendered
    assert "FAIL_TO_PASS" not in rendered
    assert "PASS_TO_PASS" not in rendered
    assert "hints_text" not in rendered
    assert packet["gold_patch_fields_removed"] is True


def test_materializer_blocks_when_shard_task_is_missing_from_dataset(tmp_path):
    materializer = load_module(
        "worker_safe_materializer", REPO / "tools/bench/materialize_swebench_worker_safe_tasks.py"
    )
    root = tmp_path / "campaign"
    write_shard_manifest(root)
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("", encoding="utf-8")

    report = materializer.materialize(root, "S00", "S00-W00", dataset_jsonl=dataset)

    assert report["status"] == "FAIL"
    assert "dataset row missing for shard task: astropy__astropy-12907" in report["problems"]


def test_materializer_cli(tmp_path):
    root = tmp_path / "campaign"
    write_shard_manifest(root)
    dataset = tmp_path / "dataset.jsonl"
    write_dataset_jsonl(dataset)

    subprocess.run(
        [
            "python3",
            "tools/bench/materialize_swebench_worker_safe_tasks.py",
            "--root",
            str(root),
            "--shard",
            "S00",
            "--window",
            "S00-W00",
            "--dataset-jsonl",
            str(dataset),
        ],
        cwd=REPO,
        check=True,
    )

    assert (root / "shards/S00/ipqc/S00-W00/worker_safe_tasks/worker_safe_tasks_report.json").exists()

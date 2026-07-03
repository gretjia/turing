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


def write_shard_manifest(root: Path, shard: str = "S01", count: int = 2):
    shard_dir = root / "shards" / shard
    shard_dir.mkdir(parents=True, exist_ok=True)
    tasks = [{"instance_id": f"repo__task-{index}", "repo": "repo"} for index in range(count)]
    (shard_dir / "shard_manifest.json").write_text(
        json.dumps({"shard_id": shard, "tasks": tasks}, indent=2) + "\n",
        encoding="utf-8",
    )
    return [task["instance_id"] for task in tasks]


def test_deterministic_floor_builder_writes_one_noop_source_patch_per_manifest_task(tmp_path):
    builder = load_module(
        "deterministic_floor",
        REPO / "tools/bench/build_deterministic_floor_predictions.py",
    )
    root = tmp_path / "campaign"
    instance_ids = write_shard_manifest(root)

    report = builder.build_deterministic_floor_predictions(
        root,
        "S01",
        model_name="deterministic-floor__armD__uplift-s01",
    )

    assert report["status"] == "PASS"
    assert report["prediction_count"] == len(instance_ids)
    assert report["candidate_source"] == "deterministic_floor"
    assert report["arm"] == "D"
    predictions_path = Path(report["predictions_path"])
    rows = [json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines()]
    assert [row["instance_id"] for row in rows] == instance_ids
    for row in rows:
        assert row["model_name_or_path"] == "deterministic-floor__armD__uplift-s01"
        assert row["candidate_source"] == "deterministic_floor"
        assert row["model_patch"].startswith("diff --git a/turingos_deterministic_floor_marker.py")
        assert "+++ b/turingos_deterministic_floor_marker.py" in row["model_patch"]
        assert "TURINGOS_ARM_D_FLOOR" in row["model_patch"]
        assert row["candidate_patch_sha256"].startswith("sha256:")


def test_deterministic_floor_builder_cli_writes_report(tmp_path):
    root = tmp_path / "campaign"
    write_shard_manifest(root, count=1)
    report_path = tmp_path / "floor_build_report.json"

    subprocess.run(
        [
            "python3",
            "tools/bench/build_deterministic_floor_predictions.py",
            "--root",
            str(root),
            "--shard",
            "S01",
            "--out",
            str(report_path),
        ],
        cwd=REPO,
        check=True,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert Path(report["predictions_path"]).exists()


def test_deterministic_floor_result_audit_passes_only_when_all_submitted_are_unresolved(tmp_path):
    auditor = load_module(
        "deterministic_floor_audit",
        REPO / "tools/bench/audit_deterministic_floor_result.py",
    )
    root = tmp_path / "campaign"
    instance_ids = write_shard_manifest(root, count=2)
    official_report = tmp_path / "official_report.json"
    official_report.write_text(
        json.dumps(
            {
                "submitted_instances": 2,
                "completed_instances": 2,
                "resolved_instances": 0,
                "unresolved_instances": 2,
                "empty_patch_instances": 0,
                "error_instances": 0,
                "submitted_ids": instance_ids,
                "resolved_ids": [],
                "unresolved_ids": instance_ids,
                "error_ids": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report = auditor.audit_deterministic_floor_result(root, "S01", official_report)

    assert report["status"] == "PASS"
    assert report["resolved_instances"] == 0
    assert report["stop_condition_triggered"] is False
    assert report["problems"] == []


def test_deterministic_floor_result_audit_stops_on_any_resolved_task(tmp_path):
    auditor = load_module(
        "deterministic_floor_audit",
        REPO / "tools/bench/audit_deterministic_floor_result.py",
    )
    root = tmp_path / "campaign"
    instance_ids = write_shard_manifest(root, count=2)
    official_report = tmp_path / "official_report.json"
    official_report.write_text(
        json.dumps(
            {
                "submitted_instances": 2,
                "completed_instances": 2,
                "resolved_instances": 1,
                "unresolved_instances": 1,
                "empty_patch_instances": 0,
                "error_instances": 0,
                "submitted_ids": instance_ids,
                "resolved_ids": [instance_ids[0]],
                "unresolved_ids": [instance_ids[1]],
                "error_ids": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report = auditor.audit_deterministic_floor_result(root, "S01", official_report)

    assert report["status"] == "STOP"
    assert report["stop_condition_triggered"] is True
    assert f"deterministic floor resolved tasks: {instance_ids[0]}" in report["problems"]

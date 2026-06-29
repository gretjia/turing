#!/usr/bin/env python3
"""Materialize worker-safe SWE-bench task packets for a shard/IPQC window.

The source SWE-bench rows contain gold patches, test patches, and official test
lists. This tool deliberately strips those fields before writing anything a
worker or visible capsule can consume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


SAFE_FIELDS = {
    "repo",
    "instance_id",
    "base_commit",
    "problem_statement",
    "version",
    "difficulty",
    "environment_setup_commit",
}

FORBIDDEN_FIELDS = {
    "patch",
    "test_patch",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "hints_text",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        yield row


def read_arrow(path: Path) -> Iterable[dict[str, Any]]:
    try:
        import pyarrow as pa
        import pyarrow.ipc as ipc
    except ImportError as exc:  # pragma: no cover - depends on local environment.
        raise RuntimeError("pyarrow is required to read SWE-bench arrow files") from exc

    with pa.memory_map(str(path), "r") as source:
        reader = ipc.open_stream(source)
        for batch in reader:
            yield from batch.to_pylist()


def default_verified_arrow_path() -> Path | None:
    base = Path.home() / ".cache/huggingface/datasets/princeton-nlp___swe-bench_verified"
    matches = sorted(base.glob("default/0.0.0/*/swe-bench_verified-test.arrow"))
    return matches[-1] if matches else None


def source_rows(*, dataset_jsonl: Path | None = None, dataset_arrow: Path | None = None) -> Iterable[dict[str, Any]]:
    if dataset_jsonl is not None:
        return read_jsonl(dataset_jsonl)
    if dataset_arrow is not None:
        return read_arrow(dataset_arrow)
    default_arrow = default_verified_arrow_path()
    if default_arrow is None:
        raise FileNotFoundError("no dataset source provided and no cached SWE-bench Verified arrow file found")
    return read_arrow(default_arrow)


def worker_safe_packet(row: dict[str, Any], *, shard: str, window: str) -> dict[str, Any]:
    packet = {field: row.get(field) for field in sorted(SAFE_FIELDS) if row.get(field) is not None}
    packet.update(
        {
            "schema_id": "turingos.swebench_worker_safe_task_packet.v1",
            "shard_id": shard,
            "ipqc_window_id": window,
            "visible_to_worker": True,
            "gold_patch_fields_removed": True,
            "forbidden_field_count_removed": sum(1 for field in FORBIDDEN_FIELDS if field in row),
            "candidate_source_policy": "worker_derived_patch_only",
        }
    )
    return packet


def worker_capsule_text(packet: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# SWE-bench Task {packet['instance_id']}",
            "",
            f"Repository: {packet.get('repo', '')}",
            f"Base commit: {packet.get('base_commit', '')}",
            f"Version: {packet.get('version', '')}",
            f"Difficulty: {packet.get('difficulty', '')}",
            "",
            "## Problem Statement",
            "",
            str(packet.get("problem_statement", "")).strip(),
            "",
            "## Candidate Policy",
            "",
            "Produce a worker-derived unified diff against the base commit. Do not use dataset gold patches, official solution patches, or hidden evaluator labels.",
            "",
        ]
    )


def materialize(
    root: Path,
    shard: str,
    window: str,
    *,
    dataset_jsonl: Path | None = None,
    dataset_arrow: Path | None = None,
) -> dict[str, Any]:
    shard_manifest = load_json(root / "shards" / shard / "shard_manifest.json")
    tasks = shard_manifest.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("shard manifest tasks must be a list")
    target_ids = [
        task["instance_id"]
        for task in tasks
        if isinstance(task, dict)
        and task.get("ipqc_window_id") == window
        and isinstance(task.get("instance_id"), str)
    ]
    if not target_ids:
        return {
            "schema_id": "turingos.swebench_worker_safe_tasks_report.v1",
            "status": "FAIL",
            "shard_id": shard,
            "ipqc_window_id": window,
            "task_count": 0,
            "problems": [f"no shard tasks found for window: {window}"],
        }

    target_set = set(target_ids)
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in source_rows(dataset_jsonl=dataset_jsonl, dataset_arrow=dataset_arrow):
        instance_id = row.get("instance_id")
        if instance_id in target_set:
            rows_by_id[instance_id] = row
        if len(rows_by_id) == len(target_set):
            break

    problems: list[str] = []
    out_root = root / "shards" / shard / "ipqc" / window / "worker_safe_tasks"
    written: list[dict[str, Any]] = []
    for instance_id in target_ids:
        row = rows_by_id.get(instance_id)
        if row is None:
            problems.append(f"dataset row missing for shard task: {instance_id}")
            continue
        packet = worker_safe_packet(row, shard=shard, window=window)
        task_dir = out_root / instance_id
        packet_path = task_dir / "task_packet.json"
        capsule_path = task_dir / "worker_capsule.md"
        write_json(packet_path, packet)
        capsule_path.parent.mkdir(parents=True, exist_ok=True)
        capsule_path.write_text(worker_capsule_text(packet), encoding="utf-8")
        written.append(
            {
                "instance_id": instance_id,
                "task_packet_path": str(packet_path.relative_to(root)),
                "task_packet_sha256": sha256_bytes(packet_path.read_bytes()),
                "worker_capsule_path": str(capsule_path.relative_to(root)),
                "worker_capsule_sha256": sha256_bytes(capsule_path.read_bytes()),
            }
        )

    report = {
        "schema_id": "turingos.swebench_worker_safe_tasks_report.v1",
        "status": "PASS" if not problems else "FAIL",
        "shard_id": shard,
        "ipqc_window_id": window,
        "task_count": len(target_ids),
        "written_count": len(written),
        "worker_visible_forbidden_fields": sorted(FORBIDDEN_FIELDS),
        "problems": problems,
        "tasks": written,
    }
    write_json(out_root / "worker_safe_tasks_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--dataset-jsonl", type=Path)
    parser.add_argument("--dataset-arrow", type=Path)
    args = parser.parse_args()
    report = materialize(
        args.root,
        args.shard,
        args.window,
        dataset_jsonl=args.dataset_jsonl,
        dataset_arrow=args.dataset_arrow,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

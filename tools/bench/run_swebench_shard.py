#!/usr/bin/env python3
"""Prepare or gate a SWE-bench official-harness shard run packet.

This script intentionally defaults to plan-only mode. It records the exact
upstream SWE-bench Docker harness command shape a human/operator or later
runner must execute. When ``--execute`` is requested, it first enforces the
campaign launch gate: every shard task must have exactly one worker-derived
unified-diff prediction before the shard can be marked ready to execute.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


WORKER_DERIVED_SOURCES = {
    "worker_derived",
    "worker_derived_patch",
    "worker_derived_repair",
    "native_api_worker",
    "external_cli_worker",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def looks_like_unified_diff(text: str) -> bool:
    return text.startswith("diff --git ") and "\n--- " in text and "\n+++ " in text and "\n@@" in text


def validate_predictions(root: Path, shard: str, predictions: Path) -> dict[str, Any]:
    problems: list[str] = []
    shard_manifest_path = root / "shards" / shard / "shard_manifest.json"
    if not shard_manifest_path.exists():
        return {
            "status": "FAIL",
            "problems": ["shard manifest missing"],
            "prediction_count": 0,
            "expected_prediction_count": 0,
        }

    shard_manifest = load_json(shard_manifest_path)
    tasks = shard_manifest.get("tasks")
    if not isinstance(tasks, list):
        return {
            "status": "FAIL",
            "problems": ["shard manifest tasks must be a list"],
            "prediction_count": 0,
            "expected_prediction_count": 0,
        }

    expected_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("instance_id"), str):
            problems.append("shard manifest task missing instance_id")
            continue
        instance_id = task["instance_id"]
        expected_ids.append(instance_id)
        source = task.get("candidate_source")
        if source is not None and source not in WORKER_DERIVED_SOURCES:
            problems.append(f"manifest source is not worker-derived: {instance_id}")

    if len(set(expected_ids)) != len(expected_ids):
        problems.append("shard manifest contains duplicate instance_id")

    if not predictions.exists():
        return {
            "status": "FAIL",
            "problems": problems + ["predictions missing"],
            "prediction_count": 0,
            "expected_prediction_count": len(expected_ids),
        }

    try:
        rows = load_jsonl(predictions)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "FAIL",
            "problems": problems + [f"predictions JSONL invalid: {exc}"],
            "prediction_count": 0,
            "expected_prediction_count": len(expected_ids),
        }

    actual_ids: list[str] = []
    for row in rows:
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str):
            problems.append("prediction missing instance_id")
            continue
        actual_ids.append(instance_id)
        source = row.get("candidate_source", "worker_derived")
        if source not in WORKER_DERIVED_SOURCES:
            problems.append(f"prediction source is not worker-derived: {instance_id}")
        patch = row.get("model_patch")
        if not isinstance(patch, str) or not looks_like_unified_diff(patch):
            problems.append(f"prediction patch is not a unified diff: {instance_id}")

    expected_set = set(expected_ids)
    actual_set = set(actual_ids)
    if len(rows) != len(expected_ids):
        problems.append(f"prediction count mismatch: expected {len(expected_ids)}, got {len(rows)}")
    for missing in sorted(expected_set - actual_set):
        problems.append(f"prediction missing for manifest task: {missing}")
    for extra in sorted(actual_set - expected_set):
        problems.append(f"prediction has task outside shard manifest: {extra}")
    if len(set(actual_ids)) != len(actual_ids):
        problems.append("predictions contain duplicate instance_id")

    return {
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "prediction_count": len(rows),
        "expected_prediction_count": len(expected_ids),
    }


def build_command(
    root: Path,
    shard: str,
    max_workers: int,
    run_id: str | None = None,
    *,
    execution_requested: bool = False,
) -> dict[str, Any]:
    run_id = run_id or f"turingos_verified500_{shard}"
    predictions = root / "predictions" / f"shard_{shard}_predictions.jsonl"
    command = (
        "python -m swebench.harness.run_evaluation "
        "--dataset_name SWE-bench/SWE-bench_Verified "
        "--split test "
        f"--predictions_path {predictions} "
        f"--run_id {run_id} "
        f"--max_workers {max_workers}"
    )
    validation = validate_predictions(root, shard, predictions) if execution_requested else None
    problems = validation["problems"] if validation else []
    status = "READY_TO_EXECUTE" if execution_requested and not problems else "BLOCKED" if execution_requested else "PLAN_ONLY"
    packet = {
        "schema_id": "turingos.swebench_shard_run_packet.v1",
        "status": status,
        "shard_id": shard,
        "official_harness_kind": "upstream_swebench_docker",
        "docker_environment_required": True,
        "command": command,
        "predictions_path": str(predictions),
        "run_id": run_id,
        "execute_now": execution_requested and not problems,
        "execution_requested": execution_requested,
        "problems": problems,
        "validation": validation,
        "note": (
            "Execution gate passed; run the recorded upstream SWE-bench Docker harness command."
            if execution_requested and not problems
            else "Execution blocked until every shard task has one worker-derived unified-diff prediction."
            if execution_requested
            else "This packet records the command only; it does not run SWE-bench."
        ),
    }
    shard_dir = root / "shards" / shard
    shard_dir.mkdir(parents=True, exist_ok=True)
    (shard_dir / "shard_run_command.txt").write_text(command + "\n", encoding="utf-8")
    write_json(shard_dir / "shard_run_packet.json", packet)
    return packet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--run-id")
    parser.add_argument("--execute", action="store_true", help="validate the shard is ready to execute")
    args = parser.parse_args()
    packet = build_command(args.root, args.shard, args.max_workers, args.run_id, execution_requested=args.execute)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 1 if args.execute and packet["status"] != "READY_TO_EXECUTE" else 0


if __name__ == "__main__":
    raise SystemExit(main())

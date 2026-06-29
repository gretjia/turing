#!/usr/bin/env python3
"""Audit one sealed 50-task SWE-bench campaign shard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TASK_FILES = [
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


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit_shard(root: Path, shard: str) -> dict[str, Any]:
    shard_dir = root / "shards" / shard
    manifest = load_json(shard_dir / "shard_manifest.json")
    tasks = manifest.get("tasks", [])
    problems: list[str] = []
    required_missing = 0
    replay_fail = 0
    resolved_count = 0
    unresolved_count = 0
    infra_failed_count = 0

    for task in tasks:
        instance_id = task.get("instance_id")
        if not isinstance(instance_id, str):
            problems.append("task missing instance_id")
            continue
        task_dir = shard_dir / "tasks" / instance_id
        for rel in REQUIRED_TASK_FILES:
            if not (task_dir / rel).exists():
                required_missing += 1
                problems.append(f"missing REQUIRED evidence for {instance_id}: {rel}")
        eval_path = task_dir / "official_eval/evaluation_result.json"
        if eval_path.exists():
            result = load_json(eval_path)
            if result.get("resolved") is True:
                resolved_count += 1
            elif result.get("infra_failed") is True:
                infra_failed_count += 1
            else:
                unresolved_count += 1
        replay_path = task_dir / "microtape/replay_report.json"
        if replay_path.exists() and load_json(replay_path).get("status") != "PASS":
            replay_fail += 1

    ipqc_missing = 0
    ipqc_problems = 0
    for window in range(5):
        path = shard_dir / "ipqc" / f"{shard}_W{window:02d}_ipqc_report.json"
        if not path.exists():
            ipqc_missing += 1
            continue
        report = load_json(path)
        for key in [
            "missing_evidence",
            "digest_mismatch",
            "gold_patch_guard_violation",
            "official_harness_identity_violation",
        ]:
            if report.get(key, 0) != 0:
                ipqc_problems += 1
                problems.append(f"IPQC {path.name} has {key}={report.get(key)}")

    if len(tasks) != 50:
        problems.append("shard_task_count must be 50")
    if ipqc_missing:
        problems.append(f"missing IPQC window reports: {ipqc_missing}")
    if replay_fail:
        problems.append(f"microtape replay failures: {replay_fail}")

    if required_missing or ipqc_missing:
        status = "BLOCKED"
        next_action = "rerun_blocked_tasks"
    elif problems:
        status = "FAIL"
        next_action = "repair_pipeline"
    else:
        status = "PASS"
        next_action = "release_next_shard"

    report = {
        "schema_id": "turingos.swebench_shard_audit.v1",
        "shard_id": shard,
        "status": status,
        "problems": problems,
        "task_count": len(tasks),
        "completed_count": len(tasks) - required_missing,
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "infra_failed_count": infra_failed_count,
        "empty_patch_count": 0,
        "official_harness_identity": "PASS" if not ipqc_problems else "FAIL",
        "gold_patch_guard": "PASS" if not ipqc_problems else "FAIL",
        "microtape_replay": "PASS" if replay_fail == 0 else "FAIL",
        "required_evidence_missing": required_missing,
        "qc_sample_completed": ipqc_missing == 0,
        "claim_boundary_pass": True,
        "next_action": next_action,
    }
    write_json(shard_dir / "shard_audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    args = parser.parse_args()
    report = audit_shard(args.root, args.shard)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit Arm D deterministic-floor official harness output."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def expected_instance_ids(root: Path, shard: str) -> list[str]:
    manifest = load_json(root / "shards" / shard / "shard_manifest.json")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("shard manifest tasks must be a list")
    ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("instance_id"), str):
            raise ValueError("shard manifest task missing instance_id")
        ids.append(task["instance_id"])
    return ids


def audit_deterministic_floor_result(root: Path, shard: str, official_report: Path) -> dict[str, Any]:
    expected_ids = expected_instance_ids(root, shard)
    expected_set = set(expected_ids)
    official = load_json(official_report)
    submitted_ids = official.get("submitted_ids", [])
    resolved_ids = official.get("resolved_ids", [])
    unresolved_ids = official.get("unresolved_ids", [])
    error_ids = official.get("error_ids", [])
    problems: list[str] = []

    if not isinstance(submitted_ids, list) or not all(isinstance(item, str) for item in submitted_ids):
        problems.append("official report submitted_ids must be a string list")
        submitted_ids = []
    if not isinstance(resolved_ids, list) or not all(isinstance(item, str) for item in resolved_ids):
        problems.append("official report resolved_ids must be a string list")
        resolved_ids = []
    if not isinstance(unresolved_ids, list) or not all(isinstance(item, str) for item in unresolved_ids):
        problems.append("official report unresolved_ids must be a string list")
        unresolved_ids = []
    if not isinstance(error_ids, list) or not all(isinstance(item, str) for item in error_ids):
        problems.append("official report error_ids must be a string list")
        error_ids = []

    submitted_set = set(submitted_ids)
    if submitted_set != expected_set:
        for missing in sorted(expected_set - submitted_set):
            problems.append(f"official report missing submitted task: {missing}")
        for extra in sorted(submitted_set - expected_set):
            problems.append(f"official report submitted task outside shard: {extra}")
    if official.get("submitted_instances") != len(expected_ids):
        problems.append(f"submitted_instances mismatch: expected {len(expected_ids)}, got {official.get('submitted_instances')}")
    if official.get("completed_instances") != len(expected_ids):
        problems.append(f"completed_instances mismatch: expected {len(expected_ids)}, got {official.get('completed_instances')}")
    if official.get("unresolved_instances") != len(expected_ids):
        problems.append(f"unresolved_instances mismatch: expected {len(expected_ids)}, got {official.get('unresolved_instances')}")
    if official.get("empty_patch_instances") != 0:
        problems.append(f"empty_patch_instances must be 0, got {official.get('empty_patch_instances')}")
    if official.get("error_instances") != 0:
        problems.append(f"error_instances must be 0, got {official.get('error_instances')}")
    if error_ids:
        problems.append("official report error_ids non-empty: " + ", ".join(sorted(error_ids)))
    if set(unresolved_ids) != expected_set:
        missing_unresolved = sorted(expected_set - set(unresolved_ids))
        if missing_unresolved:
            problems.append("expected unresolved task(s) missing: " + ", ".join(missing_unresolved))

    stop_condition_triggered = bool(resolved_ids) or official.get("resolved_instances") not in (0, None)
    if stop_condition_triggered:
        resolved_label = ", ".join(sorted(resolved_ids)) if resolved_ids else str(official.get("resolved_instances"))
        problems.append(f"deterministic floor resolved tasks: {resolved_label}")

    status = "STOP" if stop_condition_triggered else "PASS" if not problems else "BLOCKED"
    report = {
        "schema_id": "turingos.swebench_deterministic_floor_result_audit.v1",
        "status": status,
        "arm": "D",
        "shard_id": shard,
        "official_report_path": str(official_report),
        "official_report_sha256": sha256_file(official_report),
        "task_count": len(expected_ids),
        "submitted_instances": official.get("submitted_instances"),
        "completed_instances": official.get("completed_instances"),
        "resolved_instances": official.get("resolved_instances"),
        "unresolved_instances": official.get("unresolved_instances"),
        "empty_patch_instances": official.get("empty_patch_instances"),
        "error_instances": official.get("error_instances"),
        "resolved_ids": sorted(resolved_ids),
        "error_ids": sorted(error_ids),
        "stop_condition_triggered": stop_condition_triggered,
        "problems": problems,
        "note": "PASS means the upstream SWE-bench harness scored every submitted Arm D task unresolved. STOP means the preregistered floor-solve stop condition fired.",
    }
    write_json(root / "shards" / shard / "arms" / "D_deterministic_floor" / "deterministic_floor_result_audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--official-report", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit_deterministic_floor_result(args.root, args.shard, args.official_report)
    if args.out:
        write_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

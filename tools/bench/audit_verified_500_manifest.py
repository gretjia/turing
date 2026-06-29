#!/usr/bin/env python3
"""Audit the frozen SWE-bench Verified 500 campaign manifest."""

from __future__ import annotations

import argparse
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


def audit_manifest(root: Path) -> dict[str, Any]:
    problems: list[str] = []
    manifest_path = root / "task_manifest.json"
    config_path = root / "campaign_config.json"
    if not manifest_path.exists():
        problems.append("task_manifest.json missing")
        manifest: dict[str, Any] = {}
    else:
        manifest = load_json(manifest_path)
    if not config_path.exists():
        problems.append("campaign_config.json missing")
        config: dict[str, Any] = {}
    else:
        config = load_json(config_path)

    tasks = manifest.get("tasks")
    instance_ids = manifest.get("instance_ids")
    shards = sorted((root / "shards").glob("S*/shard_manifest.json")) if (root / "shards").exists() else []

    if config.get("one_shot_500_run") != "FORBIDDEN":
        problems.append("one_shot_500_run must be FORBIDDEN")
    if config.get("official_harness_identity_gate") != "REQUIRED":
        problems.append("official_harness_identity_gate must be REQUIRED")
    if config.get("process_qc_during_execution") != "REQUIRED":
        problems.append("process_qc_during_execution must be REQUIRED")

    if manifest.get("task_count") != 500:
        problems.append("task_count must be 500")
    if manifest.get("selection_policy") != "ALL":
        problems.append("selection_policy must be ALL")
    if not isinstance(instance_ids, list) or len(instance_ids) != 500:
        problems.append("instance_ids must contain exactly 500 entries")
    elif len(set(instance_ids)) != 500:
        problems.append("instance_ids must be unique")
    if not isinstance(tasks, list) or len(tasks) != 500:
        problems.append("tasks must contain exactly 500 entries")
    else:
        task_ids = [task.get("instance_id") for task in tasks]
        if len(set(task_ids)) != 500:
            problems.append("tasks instance_id must be unique")
        shard_ids = {task.get("shard_id") for task in tasks}
        if shard_ids != {f"S{i:02d}" for i in range(10)}:
            problems.append("tasks must cover shard ids S00..S09")
        for shard_id in [f"S{i:02d}" for i in range(10)]:
            if sum(1 for task in tasks if task.get("shard_id") == shard_id) != 50:
                problems.append(f"{shard_id} must contain 50 tasks")
    if len(shards) != 10:
        problems.append("exactly 10 shard manifests required")

    report = {
        "schema_id": "turingos.swebench_verified_500_manifest_audit.v1",
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "task_count": manifest.get("task_count"),
        "shard_count": len(shards),
        "shard_size": config.get("shard_size"),
        "ipqc_window_size": config.get("ipqc_window_size"),
        "one_shot_500_run": config.get("one_shot_500_run"),
        "official_harness_identity_gate": config.get("official_harness_identity_gate"),
        "selection_policy": manifest.get("selection_policy"),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit_manifest(args.root)
    out = args.out or args.root / "manifest_audit.json"
    write_json(out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

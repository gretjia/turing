#!/usr/bin/env python3
"""Audit materialized SWE-bench worker-safe task packets for leakage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORBIDDEN_PACKET_KEYS = {
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "hints_text",
    "patch",
    "test_patch",
}

FORBIDDEN_VISIBLE_MARKERS = [
    "fail_to_pass",
    "gold patch",
    "gold_patch",
    "hints_text",
    "official solution",
    "pass_to_pass",
    "test_patch",
]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def visible_marker_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in FORBIDDEN_VISIBLE_MARKERS if marker in lowered]


def audit_worker_safe_tasks(root: Path, shard: str, window: str) -> dict[str, Any]:
    tasks_root = root / "shards" / shard / "ipqc" / window / "worker_safe_tasks"
    problems: list[str] = []
    task_reports: list[dict[str, Any]] = []
    task_dirs = sorted(path for path in tasks_root.iterdir() if path.is_dir()) if tasks_root.exists() else []

    for task_dir in task_dirs:
        instance_id = task_dir.name
        packet_path = task_dir / "task_packet.json"
        capsule_path = task_dir / "worker_capsule.md"
        task_problems: list[str] = []

        if not packet_path.exists():
            task_problems.append(f"{instance_id} task_packet.json missing")
            packet: dict[str, Any] = {}
            packet_text = ""
        else:
            packet = load_json(packet_path)
            packet_text = packet_path.read_text(encoding="utf-8")

        if not capsule_path.exists():
            task_problems.append(f"{instance_id} worker_capsule.md missing")
            capsule_text = ""
        else:
            capsule_text = capsule_path.read_text(encoding="utf-8")

        for key in sorted(FORBIDDEN_PACKET_KEYS):
            if key in packet:
                task_problems.append(f"{instance_id} forbidden packet key: {key}")

        if packet.get("schema_id") != "turingos.swebench_worker_safe_task_packet.v1":
            task_problems.append(f"{instance_id} schema_id mismatch")
        if packet.get("visible_to_worker") is not True:
            task_problems.append(f"{instance_id} visible_to_worker is not true")
        if packet.get("restricted_source_fields_removed") is not True:
            task_problems.append(f"{instance_id} restricted_source_fields_removed is not true")
        if packet.get("candidate_source_policy") != "worker_derived_patch_only":
            task_problems.append(f"{instance_id} candidate_source_policy mismatch")

        for marker in visible_marker_hits(packet_text):
            task_problems.append(f"{instance_id} visible packet marker: {marker}")
        for marker in visible_marker_hits(capsule_text):
            task_problems.append(f"{instance_id} visible capsule marker: {marker}")

        problems.extend(task_problems)
        task_reports.append(
            {
                "instance_id": instance_id,
                "status": "PASS" if not task_problems else "FAIL",
                "problems": task_problems,
            }
        )

    if not task_reports:
        problems.append(f"no worker-safe task packets found for {shard}/{window}")

    report = {
        "schema_id": "turingos.worker_safe_task_packet_audit.v1",
        "status": "PASS" if not problems else "FAIL",
        "shard_id": shard,
        "ipqc_window_id": window,
        "packet_count": len(task_reports),
        "forbidden_packet_keys": sorted(FORBIDDEN_PACKET_KEYS),
        "forbidden_visible_markers": FORBIDDEN_VISIBLE_MARKERS,
        "problems": problems,
        "tasks": task_reports,
    }
    write_json(root / "shards" / shard / "ipqc" / window / "worker_safe_task_packet_audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit_worker_safe_tasks(args.root, args.shard, args.window)
    if args.out:
        write_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Detect forbidden dataset gold-patch candidate sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORBIDDEN_SOURCES = {
    "dataset_gold_patch",
    "dataset_patch",
    "official_solution_patch",
    "gold_patch",
    "test_patch_as_candidate",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit_shard(root: Path, shard: str) -> dict[str, Any]:
    manifest = load_json(root / "shards" / shard / "shard_manifest.json")
    problems: list[str] = []
    for task in manifest.get("tasks", []):
        instance_id = task.get("instance_id", "<unknown>")
        source = task.get("candidate_source")
        if source in FORBIDDEN_SOURCES:
            problems.append(f"dataset gold patch used as candidate source: {instance_id}")
    report = {
        "schema_id": "turingos.gold_patch_guard_audit.v1",
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "shard_id": shard,
        "task_count": len(manifest.get("tasks", [])),
        "gold_patch_shortcut_allowed": False,
    }
    write_json(root / "shards" / shard / "gold_patch_guard_audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit_shard(args.root, args.shard)
    if args.out:
        write_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

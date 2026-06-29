#!/usr/bin/env python3
"""Build SWE-bench predictions JSONL from worker-derived candidate patches."""

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


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build_predictions(root: Path, shard: str, *, model_name: str = "turingos-internal-rehearsal") -> dict[str, Any]:
    shard_manifest = load_json(root / "shards" / shard / "shard_manifest.json")
    rows: list[dict[str, Any]] = []
    problems: list[str] = []
    for task in shard_manifest.get("tasks", []):
        instance_id = task.get("instance_id")
        if not isinstance(instance_id, str):
            problems.append("task missing instance_id")
            continue
        if task.get("candidate_source") not in (None, "worker_derived", "worker_derived_patch"):
            problems.append(f"candidate source is not worker-derived: {instance_id}")
            continue
        patch_rel = task.get("candidate_patch_path") or f"shards/{shard}/tasks/{instance_id}/candidate.patch"
        patch_path = root / patch_rel
        if not patch_path.exists():
            problems.append(f"candidate patch missing: {instance_id}")
            continue
        patch_bytes = patch_path.read_bytes()
        patch_text = patch_bytes.decode("utf-8")
        rows.append(
            {
                "instance_id": instance_id,
                "model_name_or_path": model_name,
                "model_patch": patch_text,
                "candidate_patch_sha256": sha256_bytes(patch_bytes),
                "candidate_source": "worker_derived",
            }
        )

    out = root / "predictions" / f"shard_{shard}_predictions.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    report = {
        "schema_id": "turingos.swebench_predictions_build_report.v1",
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "shard_id": shard,
        "prediction_count": len(rows),
        "predictions_path": str(out),
        "predictions_sha256": sha256_bytes(out.read_bytes()),
    }
    write_json(root / "predictions" / f"shard_{shard}_predictions_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--model-name", default="turingos-internal-rehearsal")
    args = parser.parse_args()
    report = build_predictions(args.root, args.shard, model_name=args.model_name)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

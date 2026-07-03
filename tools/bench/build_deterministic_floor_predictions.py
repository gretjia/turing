#!/usr/bin/env python3
"""Build Arm D deterministic-floor SWE-bench predictions.

The floor patch is intentionally task-independent: it adds one inert source
marker file. The upstream harness still applies and scores it exactly like any
other prediction, so any resolved task remains a preregistered STOP signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_MODEL_NAME = "deterministic-floor__armD__uplift-s01"
DEFAULT_OUT_NAME = "shard_{shard}_armD_deterministic_floor_predictions.jsonl"
MARKER_PATH = "turingos_deterministic_floor_marker.py"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def marker_patch() -> str:
    return (
        f"diff --git a/{MARKER_PATH} b/{MARKER_PATH}\n"
        "new file mode 100644\n"
        "index 0000000000..a531b096c4\n"
        "--- /dev/null\n"
        f"+++ b/{MARKER_PATH}\n"
        "@@ -0,0 +1,3 @@\n"
        '+"""Deterministic no-op marker for TuringOS Arm D floor."""\n'
        "+\n"
        "+TURINGOS_ARM_D_FLOOR = True\n"
    )


def build_deterministic_floor_predictions(
    root: Path,
    shard: str,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    out_path: Path | None = None,
) -> dict[str, Any]:
    manifest_path = root / "shards" / shard / "shard_manifest.json"
    manifest = load_json(manifest_path)
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("shard manifest tasks must be a list")

    patch_text = marker_patch()
    patch_sha = sha256_text(patch_text)
    rows: list[dict[str, Any]] = []
    problems: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("instance_id"), str):
            problems.append("task missing instance_id")
            continue
        instance_id = task["instance_id"]
        if instance_id in seen:
            problems.append(f"duplicate instance_id: {instance_id}")
            continue
        seen.add(instance_id)
        rows.append(
            {
                "instance_id": instance_id,
                "model_name_or_path": model_name,
                "model_patch": patch_text,
                "candidate_patch_sha256": patch_sha,
                "candidate_source": "deterministic_floor",
                "arm": "D",
            }
        )

    out = out_path or root / "predictions" / DEFAULT_OUT_NAME.format(shard=shard)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    report = {
        "schema_id": "turingos.swebench_deterministic_floor_predictions_report.v1",
        "status": "PASS" if not problems else "FAIL",
        "arm": "D",
        "shard_id": shard,
        "candidate_source": "deterministic_floor",
        "model_name_or_path": model_name,
        "task_count": len(tasks),
        "prediction_count": len(rows),
        "problems": problems,
        "predictions_path": str(out),
        "predictions_sha256": sha256_bytes(out.read_bytes()),
        "patch_template_sha256": patch_sha,
        "source_manifest_path": str(manifest_path),
        "source_manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
        "note": "Arm D deterministic floor; any resolved task in upstream harness output is a preregistered STOP condition.",
    }
    write_json(root / "predictions" / f"shard_{shard}_armD_deterministic_floor_predictions_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--predictions-out", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    report = build_deterministic_floor_predictions(
        args.root,
        args.shard,
        model_name=args.model_name,
        out_path=args.predictions_out,
    )
    if args.out:
        write_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

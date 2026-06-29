#!/usr/bin/env python3
"""Prepare a SWE-bench official-harness shard run packet.

This script intentionally defaults to plan-only mode. It records the exact
upstream SWE-bench Docker harness command shape a human/operator or later
runner must execute, but it does not run the 50-task shard unless a future
implementation wires an explicit execution backend.
"""

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


def build_command(root: Path, shard: str, max_workers: int, run_id: str | None = None) -> dict[str, Any]:
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
    packet = {
        "schema_id": "turingos.swebench_shard_run_packet.v1",
        "status": "PLAN_ONLY",
        "shard_id": shard,
        "official_harness_kind": "upstream_swebench_docker",
        "docker_environment_required": True,
        "command": command,
        "predictions_path": str(predictions),
        "run_id": run_id,
        "execute_now": False,
        "note": "This packet records the command only; it does not run SWE-bench.",
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
    args = parser.parse_args()
    packet = build_command(args.root, args.shard, args.max_workers, args.run_id)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

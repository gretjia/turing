#!/usr/bin/env python3
"""Freeze the SWE-bench Verified 500 campaign control manifest.

This builder does not run SWE-bench. It converts the previously frozen Phase G
Verified 500 manifest into the sharded campaign control surface required before
any official Docker-harness run can start.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


SHARD_SIZE = 50
IPQC_WINDOW_SIZE = 10
SHARD_COUNT = 10


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


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def repo_name(instance_id: str) -> str:
    return instance_id.split("__", 1)[0] if "__" in instance_id else "unknown"


def stratified_round_robin(instance_ids: list[str]) -> list[str]:
    """Mix repositories without dropping or replacing any task."""

    buckets: dict[str, deque[str]] = defaultdict(deque)
    for instance_id in sorted(instance_ids):
        buckets[repo_name(instance_id)].append(instance_id)
    ordered: list[str] = []
    repos = sorted(buckets)
    while any(buckets[repo] for repo in repos):
        for repo in repos:
            if buckets[repo]:
                ordered.append(buckets[repo].popleft())
    return ordered


def claim_boundary() -> dict[str, Any]:
    return {
        "campaign_kind": "internal_official_harness_run",
        "dataset": "SWE-bench Verified",
        "task_count": 500,
        "selection_policy": "ALL",
        "full_swe_bench_dataset_claim_allowed": False,
        "full_swe_bench_verified_500_claim_allowed_after_fg_pass": True,
        "full_score_claim_allowed_before_fg_pass": False,
        "leaderboard_equivalence_claim_allowed": False,
        "official_leaderboard_submission_claim_allowed": False,
        "gold_patch_shortcut_allowed": False,
        "repo_local_evaluator_official_claim_allowed": False,
        "phase_g_release_allowed_before_official_harness_gates": False,
    }


def campaign_config() -> dict[str, Any]:
    return {
        "schema_id": "turingos.swebench_verified_500_campaign_config.v1",
        "one_shot_500_run": "FORBIDDEN",
        "process_qc_during_execution": "REQUIRED",
        "post_campaign_full_audit": "REQUIRED",
        "deep_qc_sampling": "REQUIRED",
        "official_harness_identity_gate": "REQUIRED",
        "gold_patch_shortcut": "FORBIDDEN",
        "leaderboard_equivalence_claim": "FORBIDDEN_UNLESS_EXTERNAL_LEADERBOARD_SUBMISSION_ACCEPTED",
        "execution_atom": "instance_id",
        "ipqc_window_size": IPQC_WINDOW_SIZE,
        "shard_size": SHARD_SIZE,
        "shard_count": SHARD_COUNT,
        "audit_atom": "50_task_sealed_shard",
        "campaign_shape": "10_shards_x_50",
    }


def build_manifest(source_manifest: Path, out_root: Path) -> dict[str, Any]:
    source = load_json(source_manifest)
    instance_ids = source.get("instance_ids")
    if not isinstance(instance_ids, list) or not all(isinstance(item, str) for item in instance_ids):
        raise ValueError("source manifest must contain string list instance_ids")
    if len(instance_ids) != 500:
        raise ValueError("source manifest must contain exactly 500 instance_ids")
    if len(set(instance_ids)) != 500:
        raise ValueError("source manifest instance_ids must be unique")

    out_root.mkdir(parents=True, exist_ok=True)
    execution_order = stratified_round_robin(instance_ids)
    original_index = {instance_id: index for index, instance_id in enumerate(instance_ids)}
    tasks: list[dict[str, Any]] = []
    for execution_index, instance_id in enumerate(execution_order):
        shard_index = execution_index // SHARD_SIZE
        shard_id = f"S{shard_index:02d}"
        tasks.append(
            {
                "instance_id": instance_id,
                "repo": repo_name(instance_id),
                "original_manifest_index": original_index[instance_id],
                "execution_order_index": execution_index,
                "shard_id": shard_id,
                "ipqc_window_id": f"{shard_id}-W{(execution_index % SHARD_SIZE) // IPQC_WINDOW_SIZE:02d}",
                "candidate_source_policy": "worker_derived_patch_only",
                "gold_patch_shortcut_allowed": False,
            }
        )

    manifest = {
        "schema_id": "turingos.swebench_verified_500_task_manifest.v1",
        "source_manifest_path": str(source_manifest),
        "source_manifest_sha256": sha256_file(source_manifest),
        "source_dataset": source.get("source_dataset", "SWE-bench Verified"),
        "source_dataset_reference": source.get("source_dataset_reference"),
        "source_dataset_digest": source.get("source_dataset_digest"),
        "source_dataset_repo_sha": source.get("source_dataset_repo_sha"),
        "official_dataset_task_count": 500,
        "task_count": 500,
        "selection_policy": "ALL",
        "exclusion_count": 0,
        "excluded_instances": [],
        "exclusion_reason": {},
        "frozen_before_run": True,
        "execution_order_policy": "deterministic_stratified_round_robin",
        "shard_count": SHARD_COUNT,
        "shard_size": SHARD_SIZE,
        "ipqc_window_size": IPQC_WINDOW_SIZE,
        "instance_ids": instance_ids,
        "execution_order_instance_ids": execution_order,
        "tasks": tasks,
        "claim_boundary": {
            "full_score_claim_allowed_before_completion": False,
            "leaderboard_equivalence_claim_allowed": False,
            "gold_patch_use_allowed": False,
        },
    }
    write_json(out_root / "task_manifest.json", manifest)
    (out_root / "task_manifest.sha256").write_text(sha256_file(out_root / "task_manifest.json") + "\n", encoding="utf-8")
    write_json(out_root / "CLAIM_BOUNDARY.json", claim_boundary())
    write_json(out_root / "campaign_config.json", campaign_config())
    write_json(
        out_root / "dataset_descriptor.json",
        {
            "dataset": "SWE-bench Verified",
            "task_count": 500,
            "selection_policy": "ALL",
            "source_dataset_digest": source.get("source_dataset_digest"),
            "source_dataset_repo_sha": source.get("source_dataset_repo_sha"),
            "raw_dataset_not_committed_reason": source.get("source_dataset_artifact_not_committed_reason"),
        },
    )
    write_json(
        out_root / "official_harness_descriptor.json",
        {
            "schema_id": "turingos.official_swebench_harness_descriptor.v1",
            "gate_status": "REQUIRED_BEFORE_OFFICIAL_CAMPAIGN",
            "official_harness_kind": "upstream_swebench_docker",
            "command_template": "python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Verified --split test --predictions_path <predictions.jsonl> --run_id <run_id> --max_workers <N>",
            "docker_environment_required": True,
            "repo_local_evaluator_may_be_marked_official": False,
            "fail_to_pass_required": True,
            "pass_to_pass_required": True,
        },
    )
    readme = """# SWE-bench Verified 500 Campaign Controller

This directory freezes the internal official-harness campaign control plane.
It does not run the 500 tasks and does not claim official leaderboard
equivalence. Upstream SWE-bench Docker harness identity must pass before any
official campaign launch.

Execution policy:
- one-shot 500 run: FORBIDDEN
- execution atom: one instance
- process QC: 10-task IPQC window
- audit atom: 50-task sealed shard
- full campaign: 10 shards x 50 tasks
"""
    (out_root / "CAMPAIGN_README.md").write_text(readme, encoding="utf-8")

    for shard_index in range(SHARD_COUNT):
        shard_id = f"S{shard_index:02d}"
        shard_tasks = [task for task in tasks if task["shard_id"] == shard_id]
        write_json(
            out_root / "shards" / shard_id / "shard_manifest.json",
            {
                "schema_id": "turingos.swebench_verified_500_shard_manifest.v1",
                "shard_id": shard_id,
                "task_count": len(shard_tasks),
                "audit_atom": "50_task_sealed_shard",
                "ipqc_window_size": IPQC_WINDOW_SIZE,
                "tasks": shard_tasks,
            },
        )

    return {"status": "PASS", "root": str(out_root), "task_count": 500, "shard_count": SHARD_COUNT}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    args = parser.parse_args()
    report = build_manifest(args.source_manifest, args.out_root)
    write_json(args.out_root / "build_manifest_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

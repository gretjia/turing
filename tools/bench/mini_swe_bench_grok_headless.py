#!/usr/bin/env python3
"""Plan SWE-bench Verified Mini runs with Grok headless as a TuringOS worker.

This harness is intentionally fail-closed. Dry-run produces an auditable run
packet without invoking Grok. Non-dry-run execution will be wired after the
deterministic fake-worker E2E gate is promoted to the benchmark track.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


THINKING_CONTRACT = "grok_no_plan_no_memory_no_subagents_plain_output"
DEFAULT_META_PROVIDER = "deepseek"
DEFAULT_META_MODEL = "deepseek-v4-pro"
DEFAULT_META_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_META_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEFAULT_RANDOMIZATION_SEED = 20260627
FORBIDDEN_ACCEPTANCE_SIGNALS = [
    "exit_code_0",
    "ci_green",
    "grok_self_report",
    "official_benchmark_result",
]


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def worker_id_for(model: str) -> str:
    seed = {
        "schema_id": "worker_identity_seed.v1",
        "provider": "grok",
        "kind": "CommandTemplate",
        "model": model,
        "thinking_mode": "off_via_low_reasoning_no_plan",
    }
    canonical = json.dumps(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "worker:sha256:" + hashlib.sha256(canonical).hexdigest()


def meta_ai_provider(
    provider: str,
    model: str,
    base_url: str,
    api_key_env: str,
) -> dict[str, Any]:
    return {
        "schema_id": "MetaAIProvider.v1",
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "credential_material": "env_only_not_serialized",
        "authority": "none",
        "accepted_head_authority": False,
    }


def experiment_design(randomization_seed: int) -> dict[str, Any]:
    return {
        "schema_id": "MiniSweBenchExperimentDesign.v1",
        "assignment": "paired_within_task",
        "arms": ["direct_grok_baseline", "turingos_grok_worker"],
        "statistical_unit": "swe_bench_instance",
        "minimum_real_tasks": 50,
        "randomization_seed": randomization_seed,
        "pre_registered_before_execution": True,
        "primary_metric": {
            "name": "resolved_by_predicate",
            "type": "paired_binary",
            "truth_source": "micro_tape_predicate_replay",
        },
        "secondary_metrics": [
            "cost_per_resolved_task",
            "wall_time_ms",
            "retry_count",
            "failure_class_distribution",
            "replay_pass_rate",
            "invalid_accepted_head_attempts",
        ],
        "statistical_tests": [
            {
                "name": "mcnemar_exact",
                "applies_to": "paired_binary_resolution",
            },
            {
                "name": "paired_bootstrap_ci",
                "confidence": "0.95",
                "applies_to": "paired_differences",
            },
        ],
        "multiple_runs_policy": "report_all_runs_no_best_of_n_unless_preregistered",
        "exclusion_policy": "no_post_hoc_exclusions",
    }


def arm_order_for_task(instance_id: str, randomization_seed: int) -> list[str]:
    arms = ["direct_grok_baseline", "turingos_grok_worker"]
    digest = hashlib.sha256(f"{randomization_seed}:{instance_id}".encode("utf-8")).digest()
    if digest[0] % 2 == 1:
        arms.reverse()
    return arms


def grok_worker_argv(cwd: str, prompt: str, model: str, max_turns: int) -> list[str]:
    return [
        "grok",
        "-p",
        prompt,
        "--cwd",
        cwd,
        "--output-format",
        "plain",
        "--model",
        model,
        "--always-approve",
        "--disable-web-search",
        "--no-plan",
        "--no-memory",
        "--no-subagents",
        "--max-turns",
        str(max_turns),
        "--verbatim",
    ]


def redacted_argv(argv: list[str]) -> list[str]:
    result = list(argv)
    for flag in ("-p", "--single"):
        if flag in result:
            index = result.index(flag)
            if index + 1 < len(result):
                result[index + 1] = "<visible_capsule_prompt>"
    return result


def read_tasks(path: Path, limit: int | None) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            task = json.loads(line)
            for key in ("instance_id", "repo", "base_commit", "problem_statement"):
                if key not in task:
                    raise ValueError(f"task is missing required key {key!r}")
            tasks.append(task)
            if limit is not None and len(tasks) >= limit:
                break
    return tasks


def visible_capsule_prompt(task: dict[str, Any], mode: str) -> str:
    return (
        "You are running under the TuringOS benchmark harness.\n"
        "Do not output chain-of-thought, private scratchpads, or model deliberation.\n"
        "TuringOS Micro Tape records the external progress trace.\n"
        "Acceptance is predicate-only; do not claim success from exit code, CI, self-report, or benchmark labels.\n"
        f"Mode: {mode}\n"
        f"Instance: {task['instance_id']}\n"
        f"Repo: {task['repo']}\n"
        f"Base commit: {task['base_commit']}\n"
        "Problem statement:\n"
        f"{task['problem_statement']}\n"
    )


def run_plan_for_task(
    task: dict[str, Any],
    mode: str,
    work_root: Path,
    model: str,
    max_turns: int,
    dry_run: bool,
) -> dict[str, Any]:
    worktree = work_root / task["instance_id"] / mode
    prompt = visible_capsule_prompt(task, mode)
    argv = grok_worker_argv(str(worktree), prompt, model, max_turns)
    not_run: list[str] = []
    if not dry_run:
        if shutil.which("grok") is None:
            not_run.append("grok_cli_missing")
        not_run.append("non_dry_run_execution_not_yet_enabled")
    return {
        "schema_id": "MiniSweBenchGrokRunPlan.v1",
        "mode": mode,
        "task": {
            "instance_id": task["instance_id"],
            "repo": task["repo"],
            "base_commit": task["base_commit"],
        },
        "grok_command": {
            "argv": redacted_argv(argv),
            "prompt_hash": sha256_text(prompt),
            "thinking_contract": THINKING_CONTRACT,
        },
        "status": "PLANNED" if dry_run else "NOT_RUN",
        "not_run": not_run,
        "turingos_truth_guard": {
            "accepted_head_policy": "predicate_only",
            "microtape_as_external_trace": True,
        },
    }


def build_packet(
    tasks: list[dict[str, Any]],
    work_root: Path,
    model: str,
    max_turns: int,
    dry_run: bool,
    meta_provider: str,
    meta_model: str,
    meta_base_url: str,
    meta_api_key_env: str,
    randomization_seed: int,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for task in tasks:
        for mode in arm_order_for_task(task["instance_id"], randomization_seed):
            runs.append(
                run_plan_for_task(
                    task,
                    mode,
                    work_root,
                    model,
                    max_turns,
                    dry_run,
                )
            )
    return {
        "schema_id": "MiniSweBenchGrokHeadlessRun.v1",
        "benchmark": "swe_bench_verified_mini",
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "model": model,
        "worker_id": worker_id_for(model),
        "experiment_design": experiment_design(randomization_seed),
        "meta_ai": meta_ai_provider(
            provider=meta_provider,
            model=meta_model,
            base_url=meta_base_url,
            api_key_env=meta_api_key_env,
        ),
        "thinking_contract": THINKING_CONTRACT,
        "dry_run": dry_run,
        "truth_guard": {
            "accepted_head_policy": "predicate_only",
            "forbidden_acceptance_signals": FORBIDDEN_ACCEPTANCE_SIGNALS,
            "microtape_as_external_trace": True,
        },
        "runs": runs,
    }


def write_json(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-jsonl", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--work-root", default="/tmp/turingos-mini-swe-bench")
    parser.add_argument("--model", default="grok-code-fast-1")
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--meta-provider", default=DEFAULT_META_PROVIDER)
    parser.add_argument("--meta-model", default=DEFAULT_META_MODEL)
    parser.add_argument("--meta-base-url", default=DEFAULT_META_BASE_URL)
    parser.add_argument("--meta-api-key-env", default=DEFAULT_META_API_KEY_ENV)
    parser.add_argument("--randomization-seed", type=int, default=DEFAULT_RANDOMIZATION_SEED)
    args = parser.parse_args(argv)

    tasks_path = Path(args.tasks_jsonl)
    if not tasks_path.exists():
        print(f"tasks jsonl not found: {tasks_path}", file=sys.stderr)
        return 2
    tasks = read_tasks(tasks_path, args.limit)
    if not tasks:
        print(f"no tasks found in {tasks_path}", file=sys.stderr)
        return 2

    packet = build_packet(
        tasks=tasks,
        work_root=Path(args.work_root),
        model=args.model,
        max_turns=args.max_turns,
        dry_run=args.dry_run,
        meta_provider=args.meta_provider,
        meta_model=args.meta_model,
        meta_base_url=args.meta_base_url,
        meta_api_key_env=args.meta_api_key_env,
        randomization_seed=args.randomization_seed,
    )
    write_json(Path(args.out), packet)
    if not args.dry_run:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

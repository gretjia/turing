#!/usr/bin/env python3
"""Clean auditor for Mini SWE-bench Grok headless plans.

This script intentionally does not import the benchmark harness. It treats the
plan JSON as an external artifact and verifies whether it is fit to start a
scientific benchmark run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


EXPECTED_ARMS = ["direct_grok_baseline", "turingos_grok_worker"]
SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}")


def finding(finding_id: str, message: str) -> dict[str, str]:
    return {"id": finding_id, "message": message}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("plan root must be a JSON object")
    return data


def argv_has_pair(argv: list[Any], flag: str, value: str) -> bool:
    return any(argv[index : index + 2] == [flag, value] for index in range(len(argv) - 1))


def audit_plan(plan: dict[str, Any], min_tasks: int, allow_smoke: bool) -> dict[str, Any]:
    blocking: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    raw = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    if SECRET_RE.search(raw):
        blocking.append(finding("credential_material_serialized", "plan contains API-key-shaped secret material"))

    if plan.get("schema_id") != "MiniSweBenchGrokHeadlessRun.v1":
        blocking.append(finding("schema_id", "unexpected benchmark plan schema"))
    if plan.get("benchmark") != "swe_bench_verified_mini":
        blocking.append(finding("benchmark", "benchmark must be swe_bench_verified_mini"))
    if plan.get("dry_run") is not True:
        blocking.append(finding("dry_run_required_for_plan_audit", "plan audit must run before real execution"))

    design = plan.get("experiment_design")
    if not isinstance(design, dict):
        blocking.append(finding("experiment_design_missing", "plan lacks a pre-registered experiment design"))
        design = {}

    expected_design = {
        "schema_id": "MiniSweBenchExperimentDesign.v1",
        "assignment": "paired_within_task",
        "arms": EXPECTED_ARMS,
        "statistical_unit": "swe_bench_instance",
        "pre_registered_before_execution": True,
        "multiple_runs_policy": "report_all_runs_no_best_of_n_unless_preregistered",
        "exclusion_policy": "no_post_hoc_exclusions",
    }
    for key, expected in expected_design.items():
        if design.get(key) != expected:
            blocking.append(finding(f"design_{key}", f"experiment_design.{key} must be {expected!r}"))

    primary = design.get("primary_metric")
    if primary != {
        "name": "resolved_by_predicate",
        "type": "paired_binary",
        "truth_source": "micro_tape_predicate_replay",
    }:
        blocking.append(finding("primary_metric", "primary metric must be predicate-resolved paired binary progress"))

    tests = design.get("statistical_tests")
    if not isinstance(tests, list):
        blocking.append(finding("statistical_tests_missing", "statistical_tests must be declared"))
        tests = []
    test_names = {item.get("name") for item in tests if isinstance(item, dict)}
    if "mcnemar_exact" not in test_names:
        blocking.append(finding("mcnemar_missing", "paired binary resolution needs McNemar exact test"))
    if "paired_bootstrap_ci" not in test_names:
        blocking.append(finding("bootstrap_ci_missing", "paired differences need a 95% paired bootstrap CI plan"))

    truth_guard = plan.get("truth_guard")
    if not isinstance(truth_guard, dict):
        blocking.append(finding("truth_guard_missing", "truth_guard must be declared"))
        truth_guard = {}
    if truth_guard.get("accepted_head_policy") != "predicate_only":
        blocking.append(finding("accepted_head_policy", "accepted_head policy must be predicate_only"))
    expected_forbidden = [
        "exit_code_0",
        "ci_green",
        "grok_self_report",
        "official_benchmark_result",
    ]
    if truth_guard.get("forbidden_acceptance_signals") != expected_forbidden:
        blocking.append(finding("forbidden_acceptance_signals", "truth guard must forbid non-predicate signals"))

    meta = plan.get("meta_ai")
    if not isinstance(meta, dict):
        blocking.append(finding("meta_ai_missing", "MetaAI provider contract must be declared"))
        meta = {}
    if meta.get("credential_material") != "env_only_not_serialized":
        blocking.append(finding("meta_ai_credential_material", "MetaAI credentials must be env-only and unserialized"))
    if meta.get("accepted_head_authority") is not False or meta.get("authority") != "none":
        blocking.append(finding("meta_ai_authority", "MetaAI must have no Micro authority"))

    worker_id = plan.get("worker_id")
    if not isinstance(worker_id, str) or not re.fullmatch(r"worker:sha256:[0-9a-f]{64}", worker_id):
        blocking.append(finding("worker_id", "worker_id must match worker:sha256:<64 lowercase hex>"))

    runs = plan.get("runs")
    if not isinstance(runs, list) or not runs:
        blocking.append(finding("runs_missing", "plan must contain benchmark runs"))
        runs = []

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        if not isinstance(run, dict):
            blocking.append(finding("run_shape", "each run must be an object"))
            continue
        task = run.get("task")
        if not isinstance(task, dict) or not task.get("instance_id"):
            blocking.append(finding("run_task", "each run needs a task.instance_id"))
            continue
        by_task[str(task["instance_id"])].append(run)

        command = run.get("grok_command")
        argv = command.get("argv") if isinstance(command, dict) else None
        if not isinstance(argv, list):
            blocking.append(finding("grok_argv", "each run needs a redacted Grok argv"))
            continue
        for flag in ["--always-approve", "--disable-web-search", "--no-plan", "--no-memory", "--no-subagents", "--verbatim"]:
            if flag not in argv:
                blocking.append(finding("grok_flag_missing", f"argv missing {flag}"))
        if not argv_has_pair(argv, "--reasoning-effort", "low"):
            blocking.append(finding("grok_reasoning_effort", "Grok reasoning effort must be low"))
        if not argv_has_pair(argv, "--effort", "low"):
            blocking.append(finding("grok_effort", "Grok effort must be low"))

    task_count = len(by_task)
    minimum_real_tasks = int(design.get("minimum_real_tasks", min_tasks) or min_tasks)
    required_task_count = min_tasks if allow_smoke else max(min_tasks, minimum_real_tasks)
    if task_count < required_task_count:
        blocking.append(
            finding(
                "sample_size_below_minimum",
                f"plan has {task_count} paired task(s), requires at least {required_task_count}",
            )
        )
    if allow_smoke and task_count < minimum_real_tasks:
        warnings.append(
            finding(
                "smoke_underpowered_by_design",
                "smoke audit checks runnability only; it is not statistically powered",
            )
        )

    for instance_id, task_runs in by_task.items():
        modes = sorted(run.get("mode") for run in task_runs)
        if modes != sorted(EXPECTED_ARMS):
            blocking.append(
                finding(
                    "paired_arms_missing",
                    f"task {instance_id} must have exactly one run for each benchmark arm",
                )
            )

    verdict = "FAIL" if blocking else "PASS"
    scientific_status = "SMOKE_ONLY_NOT_REAL_BENCHMARK" if allow_smoke else "READY_FOR_REAL_BENCHMARK"
    if verdict == "FAIL":
        scientific_status = "BLOCKED"

    return {
        "schema_id": "MiniSweBenchPlanAudit.v1",
        "verdict": verdict,
        "scientific_status": scientific_status,
        "task_count": task_count,
        "min_tasks_checked": required_task_count,
        "blocking_findings": blocking,
        "warnings": warnings,
        "auditor_independence": {
            "imports_benchmark_harness": False,
            "input_surface": "plan_json_only",
        },
    }


def write_json(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-tasks", type=int, default=50)
    parser.add_argument("--allow-smoke", action="store_true")
    args = parser.parse_args(argv)

    packet = audit_plan(load_json(Path(args.plan)), args.min_tasks, args.allow_smoke)
    write_json(Path(args.out), packet)
    return 0 if packet["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

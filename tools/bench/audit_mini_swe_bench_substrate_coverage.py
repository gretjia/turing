#!/usr/bin/env python3
"""Audit whether a Mini SWE-bench run exercised the TuringOS substrate.

This auditor is deliberately separate from the benchmark runner. It reads a
coverage JSON artifact and answers one narrow question: did the TuringOS arm
actually call the modules, processes, and Micro events required by the project
book? It does not score model quality.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_MODULES = [
    "M0_law_goal_harness",
    "M1_canonical_codec",
    "M2_micro_git_tape",
    "M3_event_registry",
    "M4_single_loop",
    "M5_goal_module_atom_capsule",
    "M6_worker_profiles",
    "M7_executor_broker",
    "M8_macro_observer",
    "M9_predicate_kernel",
    "M10_evidence_approval",
    "M11_failure_memory",
    "M12_market_substrate",
    "M13_marketrouter_shadow",
    "M14_pput_accounting",
    "M15_projection",
    "M16_integration_queue",
    "M17_e2e_handoff",
]

BASE_REQUIRED_PROCESSES = [
    "turingd",
    "turing-execd",
    "turing-mcp",
    "turing-marketd",
    "turing-pputd",
    "turing-viewd",
]

REAL_WORKER_PROCESSES = {"grok_cli"}

REQUIRED_EVENTS = [
    "GoalStateProposed",
    "WorkCapsuleBuilt",
    "MarketCreated",
    "BudgetAllocated",
    "WorkerReceiptImported",
    "MacroObservationImported",
    "PPUTAccounted",
    "PredicateEvaluated",
]


def finding(finding_id: str, message: str) -> dict[str, str]:
    return {"id": finding_id, "message": message}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("coverage root must be a JSON object")
    return data


def positive_count(mapping: Any, key: str) -> int:
    if not isinstance(mapping, dict):
        return 0
    value = mapping.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(value, 0)
    return 0


def aggregate_counts(runs: list[Any], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        values = run.get(field)
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if isinstance(value, bool):
                increment = int(value)
            elif isinstance(value, int):
                increment = max(value, 0)
            else:
                increment = 0
            counts[str(key)] = counts.get(str(key), 0) + increment
    return counts


def audit_coverage(
    coverage: dict[str, Any],
    min_sample_size: int,
    worker_process: str,
    meta_ai_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocking: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if coverage.get("schema_id") != "MiniSweBenchSubstrateCoverage.v1":
        blocking.append(finding("schema_id", "unexpected substrate coverage schema"))

    sample_size = coverage.get("sample_size")
    if not isinstance(sample_size, int) or sample_size < min_sample_size:
        blocking.append(
            finding(
                "sample_size_below_minimum",
                f"coverage sample_size must be at least {min_sample_size}",
            )
        )

    runs = coverage.get("turingos_arm_runs")
    if not isinstance(runs, list) or not runs:
        blocking.append(finding("turingos_arm_runs_missing", "coverage must contain TuringOS arm runs"))
        runs = []

    module_counts = aggregate_counts(runs, "module_calls")
    process_counts = aggregate_counts(runs, "process_calls")
    event_counts = aggregate_counts(runs, "event_calls")

    for module_id in REQUIRED_MODULES:
        if positive_count(module_counts, module_id) <= 0:
            blocking.append(
                finding(
                    f"missing_module_{module_id}",
                    f"TuringOS arm did not exercise required module {module_id}",
                )
            )

    required_processes = [*BASE_REQUIRED_PROCESSES, worker_process]
    for process in required_processes:
        if positive_count(process_counts, process) <= 0:
            blocking.append(
                finding(
                    f"missing_process_{process}",
                    f"TuringOS arm did not call required process {process}",
                )
            )

    for event in REQUIRED_EVENTS:
        if positive_count(event_counts, event) <= 0:
            blocking.append(
                finding(
                    f"missing_event_{event}",
                    f"TuringOS arm did not emit or import required event {event}",
                )
            )

    if (
        positive_count(event_counts, "CandidateAccepted") <= 0
        and positive_count(event_counts, "FailureNode") <= 0
    ):
        blocking.append(
            finding(
                "missing_event_CandidateAccepted_or_FailureNode",
                "TuringOS arm did not exercise candidate accept/reject truth gate",
            )
        )

    meta_ai_status: dict[str, Any] | None = None
    if meta_ai_review is not None:
        meta_ai_status = {
            "provider": meta_ai_review.get("provider"),
            "model": meta_ai_review.get("model"),
            "status": meta_ai_review.get("status"),
            "authority": meta_ai_review.get("authority"),
            "accepted_head_authority": meta_ai_review.get("accepted_head_authority"),
            "credential_material": meta_ai_review.get("credential_material"),
            "review_verdict": (
                meta_ai_review.get("review", {}).get("verdict")
                if isinstance(meta_ai_review.get("review"), dict)
                else None
            ),
        }
        if meta_ai_review.get("provider") != "deepseek":
            blocking.append(finding("meta_ai_provider", "MetaAI provider must be deepseek"))
        if meta_ai_review.get("model") != "deepseek-v4-pro":
            blocking.append(finding("meta_ai_model", "MetaAI model must be deepseek-v4-pro"))
        if meta_ai_review.get("status") != "PASS":
            blocking.append(finding("meta_ai_not_run", "MetaAI review must run successfully"))
        if meta_ai_review.get("authority") != "none" or meta_ai_review.get("accepted_head_authority") is not False:
            blocking.append(finding("meta_ai_authority", "MetaAI must have no Micro head authority"))
        if meta_ai_review.get("credential_material") != "env_only_not_serialized":
            blocking.append(finding("meta_ai_credentials", "MetaAI credentials must be env-only and unserialized"))
        if not isinstance(meta_ai_review.get("review"), dict):
            blocking.append(finding("meta_ai_review_missing", "MetaAI review object is required"))

    verdict = "FAIL" if blocking else "PASS"
    if verdict == "FAIL":
        status = "SUBSTRATE_COVERAGE_BLOCKED"
    elif meta_ai_review is not None and worker_process in REAL_WORKER_PROCESSES:
        status = "SUBSTRATE_COVERAGE_READY_WITH_META_AI"
    elif worker_process in REAL_WORKER_PROCESSES:
        status = "SUBSTRATE_COVERAGE_READY"
    else:
        status = "SUBSTRATE_INSTRUMENTATION_ONLY_NOT_REAL_WORKER"
    return {
        "schema_id": "MiniSweBenchSubstrateCoverageAudit.v1",
        "verdict": verdict,
        "scientific_status": status,
        "sample_size": sample_size,
        "min_sample_size_checked": min_sample_size,
        "module_counts": module_counts,
        "process_counts": process_counts,
        "event_counts": event_counts,
        "required_worker_process": worker_process,
        "meta_ai": meta_ai_status,
        "blocking_findings": blocking,
        "warnings": warnings,
        "auditor_independence": {
            "imports_benchmark_harness": False,
            "input_surface": "coverage_json_only",
        },
    }


def write_json(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-sample-size", type=int, default=50)
    parser.add_argument("--worker-process", default="grok_cli")
    parser.add_argument("--meta-ai-review")
    args = parser.parse_args(argv)

    meta_ai_review = load_json(Path(args.meta_ai_review)) if args.meta_ai_review else None
    packet = audit_coverage(
        load_json(Path(args.coverage)),
        args.min_sample_size,
        args.worker_process,
        meta_ai_review,
    )
    write_json(Path(args.out), packet)
    return 0 if packet["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

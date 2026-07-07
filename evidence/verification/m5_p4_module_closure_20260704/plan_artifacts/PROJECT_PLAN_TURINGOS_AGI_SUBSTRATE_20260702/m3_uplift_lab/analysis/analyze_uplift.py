#!/usr/bin/env python3
"""M3 uplift analysis.

Stdlib-only. Inputs are upstream SWE-bench harness evaluation_results.json files.
The dry-run fixture is synthetic and must never be cited as real performance.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


ALPHA_H1 = 0.025
ALPHA_H2 = 0.05
DEFAULT_REPS = 10_000
DEFAULT_SEED = 20_260_702


def exact_mcnemar_p(uplift_only: int, harm_only: int) -> float:
    discordant = uplift_only + harm_only
    if discordant == 0:
        return 1.0
    lower_tail = sum(math.comb(discordant, k) for k in range(0, min(uplift_only, harm_only) + 1))
    return min(1.0, 2.0 * lower_tail / (2 ** discordant))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_experiment(root: Path) -> tuple[list[str], list[str], dict[tuple[str, str], set[str]], dict]:
    manifest = load_json(root / "experiment_manifest.json")
    tasks = list(manifest["tasks"])
    workers = list(manifest["workers"])
    cells: dict[tuple[str, str], set[str]] = {}

    for worker in workers:
        for arm in ("A", "B", "C"):
            rel = manifest["scoring"][worker][arm]
            result_path = root / rel
            result = load_json(result_path)
            if result.get("schema_version") != 2:
                raise ValueError(f"{result_path} does not declare schema_version 2")
            forbidden_errors = result.get("error_ids", []) + result.get("incomplete_ids", [])
            if forbidden_errors:
                raise ValueError(f"{result_path} has error or incomplete ids; apply rerun/exclusion policy before analysis")
            resolved = set(result.get("resolved_ids", []))
            unknown = resolved.difference(tasks)
            if unknown:
                raise ValueError(f"{result_path} has resolved ids outside manifest: {sorted(unknown)}")
            cells[(worker, arm)] = resolved

    return tasks, workers, cells, manifest


def pooled_counts(cells: dict[tuple[str, str], set[str]], tasks: list[str], workers: list[str], arm1: str, arm2: str) -> dict:
    uplift_only = 0
    harm_only = 0
    both = 0
    neither = 0
    arm1_total = 0
    arm2_total = 0
    for worker in workers:
        res1 = cells[(worker, arm1)]
        res2 = cells[(worker, arm2)]
        for task in tasks:
            s1 = task in res1
            s2 = task in res2
            arm1_total += int(s1)
            arm2_total += int(s2)
            if s1 and s2:
                both += 1
            elif (not s1) and s2:
                uplift_only += 1
            elif s1 and not s2:
                harm_only += 1
            else:
                neither += 1
    total = len(tasks) * len(workers)
    return {
        "arm1": arm1,
        "arm2": arm2,
        "pairs": total,
        "arm1_resolved": arm1_total,
        "arm2_resolved": arm2_total,
        "both_resolved": both,
        "neither_resolved": neither,
        "uplift_only": uplift_only,
        "harm_only": harm_only,
        "delta": (arm2_total - arm1_total) / total if total else 0.0,
        "exact_mcnemar_two_sided_p": exact_mcnemar_p(uplift_only, harm_only),
    }


def cluster_bootstrap_delta(
    cells: dict[tuple[str, str], set[str]],
    tasks: list[str],
    workers: list[str],
    arm1: str,
    arm2: str,
    reps: int,
    seed: int,
) -> dict:
    rng = random.Random(seed)
    deltas: list[float] = []
    denominator = len(tasks) * len(workers)
    for _ in range(reps):
        sample = [tasks[rng.randrange(len(tasks))] for _ in tasks]
        n1 = 0
        n2 = 0
        for worker in workers:
            res1 = cells[(worker, arm1)]
            res2 = cells[(worker, arm2)]
            for task in sample:
                n1 += int(task in res1)
                n2 += int(task in res2)
        deltas.append((n2 - n1) / denominator)
    deltas.sort()
    lo_idx = int(0.025 * (reps - 1))
    hi_idx = int(0.975 * (reps - 1))
    return {
        "method": "cluster_by_task_percentile_bootstrap",
        "replicates": reps,
        "seed": seed,
        "ci95_low": deltas[lo_idx],
        "ci95_high": deltas[hi_idx],
    }


def per_worker(cells: dict[tuple[str, str], set[str]], tasks: list[str], workers: list[str], arm1: str, arm2: str) -> list[dict]:
    rows = []
    for worker in workers:
        rows.append(pooled_counts(cells, tasks, [worker], arm1, arm2) | {"worker": worker})
    return rows


def analyze(root: Path, out_dir: Path, reps: int, seed: int, fixture: bool) -> dict:
    tasks, workers, cells, manifest = load_experiment(root)
    h1 = pooled_counts(cells, tasks, workers, "A", "B")
    h2 = pooled_counts(cells, tasks, workers, "C", "B")
    h1["bootstrap_ci95"] = cluster_bootstrap_delta(cells, tasks, workers, "A", "B", reps, seed)
    h2["bootstrap_ci95"] = cluster_bootstrap_delta(cells, tasks, workers, "C", "B", reps, seed + 1)

    h1_reject = h1["exact_mcnemar_two_sided_p"] <= ALPHA_H1
    h2_reject = bool(h1_reject and h2["exact_mcnemar_two_sided_p"] <= ALPHA_H2)

    report = {
        "schema_id": "turingos.m3.uplift_report.v1",
        "evidence_class": "FIXTURE" if fixture else "REAL_HARNESS_OUTPUTS",
        "fixture": fixture,
        "source_root": str(root.resolve()),
        "tasks": len(tasks),
        "workers": workers,
        "analysis_inputs": "upstream_swebench_evaluation_results_json_only",
        "confirmatory_tests": {
            "H1_B_gt_A": h1 | {
                "holm_alpha": ALPHA_H1,
                "holm_reject": h1_reject,
                "positive_direction": h1["delta"] > 0,
            },
            "H2_B_gt_C": h2 | {
                "holm_alpha": ALPHA_H2 if h1_reject else None,
                "holm_reject": h2_reject,
                "positive_direction": h2["delta"] > 0,
                "blocked_by_h1": not h1_reject,
            },
        },
        "exploratory": {
            "per_worker_B_minus_A": per_worker(cells, tasks, workers, "A", "B"),
            "per_worker_B_minus_C": per_worker(cells, tasks, workers, "C", "B"),
        },
        "mde_statement": (
            "Pre-registered design is powered for large effects: one worker on 50 paired tasks has "
            "roughly 15-23 percentage point MDE depending on harm rate; pooling 2-3 workers targets "
            "roughly 6-14 percentage points before task-clustering inflation."
        ),
        "claim_boundary": {
            "full_score_claim_allowed": False,
            "absolute_rate_is_capability_claim": False,
            "turingos_improves_workers_claim_allowed": (not fixture) and h1_reject and h1["delta"] > 0,
            "fixture_outputs_are_not_performance_evidence": fixture,
        },
        "manifest": {
            "schema_id": manifest.get("schema_id"),
            "evidence_class": manifest.get("evidence_class"),
        },
    }

    write_json(out_dir / "UPLIFT_REPORT.json", report)
    write_markdown(out_dir / "UPLIFT_REPORT.md", report)
    return report


def write_markdown(path: Path, report: dict) -> None:
    h1 = report["confirmatory_tests"]["H1_B_gt_A"]
    h2 = report["confirmatory_tests"]["H2_B_gt_C"]
    lines = [
        "# M3 Uplift Analysis Report",
        "",
        f"- Evidence class: {report['evidence_class']}",
        f"- Fixture: {str(report['fixture']).lower()}",
        f"- Tasks: {report['tasks']}",
        f"- Workers: {', '.join(report['workers'])}",
        "",
        "## Confirmatory Tests",
        "",
        "| Test | Delta | p | CI low | CI high | Holm reject |",
        "|---|---:|---:|---:|---:|---|",
        (
            f"| H1 B>A | {h1['delta']:.6f} | {h1['exact_mcnemar_two_sided_p']:.6f} | "
            f"{h1['bootstrap_ci95']['ci95_low']:.6f} | {h1['bootstrap_ci95']['ci95_high']:.6f} | "
            f"{h1['holm_reject']} |"
        ),
        (
            f"| H2 B>C | {h2['delta']:.6f} | {h2['exact_mcnemar_two_sided_p']:.6f} | "
            f"{h2['bootstrap_ci95']['ci95_low']:.6f} | {h2['bootstrap_ci95']['ci95_high']:.6f} | "
            f"{h2['holm_reject']} |"
        ),
        "",
        "## MDE Statement",
        "",
        report["mde_statement"],
        "",
        "## Claim Boundary",
        "",
        "Absolute solve rates are not capability claims. Fixture outputs are not performance evidence.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze M3 uplift harness outputs.")
    parser.add_argument("--root", type=Path, help="Experiment root containing experiment_manifest.json")
    parser.add_argument("--fixture", type=Path, help="Synthetic dry-run fixture root")
    parser.add_argument("--out", type=Path, help="Output directory; defaults to <root>/out")
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.root) == bool(args.fixture):
        raise SystemExit("Provide exactly one of --root or --fixture")
    root = args.fixture or args.root
    out_dir = args.out or (root / "out")
    analyze(root, out_dir, args.reps, args.seed, fixture=bool(args.fixture))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

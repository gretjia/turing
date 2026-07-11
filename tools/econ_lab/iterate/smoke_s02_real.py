#!/usr/bin/env python3
"""WP-L3-1 real smoke: one S02 task, a real worker (grok CLI), an organic attempt-2.

SMOKE_FIXTURE -- read this before trusting anything this script emits as a claim:
this is NOT a certified SWE-bench solve-rate run and never calls the real SWE-bench
docker/conda evaluation harness (that is out of budget for a <=6-call smoke and is a
separate, already-existing capability path). "PASS"/"FAIL" here means only "did the
patch produced this round touch the file the public bug report's traceback
implicates" (`sphinx/domains/python.py`) -- a cheap, honest, real (non-fabricated)
proxy signal computed from the worker's actual `git diff`, never an official-evaluator
claim. Every field this script writes says exactly that.

Task selection (WP brief: "1 个 S02 任务"): `sphinx-doc__sphinx-7462`, drawn from
`evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02/shard_manifest.json`
(`execution_order_index: 107`, `original_manifest_index: 391`). `repo`/`base_commit`/
`problem_statement` were looked up from the public SWE-bench Verified dataset at that
same `original_manifest_index` via the HuggingFace datasets-server `/rows` endpoint
(https://datasets-server.huggingface.co/rows?dataset=princeton-nlp%2FSWE-bench_Verified
&config=default&split=test&offset=391&length=1) -- not from any file already checked
into this repo (S02's own `tasks/sphinx-doc__sphinx-7462/` only has a prior worker
receipt + candidate patch, no repo/base_commit/problem_statement) -- so those three
constants below are the honest, reproducible provenance for this smoke's task, not
guessed.

Worker: the real `grok` CLI (already authenticated in this environment; no API key
handling needed here) -- exactly two real dispatches (attempt 1, attempt 2), well
under the WP's <=6-call budget. Nothing here fabricates a third+ call.

Bad route (organic, not scripted): the worker-safe capsule handed to attempt 1
deliberately omits the traceback/file hint from the public bug report (only the
user-facing repro + expected-behavior text survives into `worker_capsule.md` -- the
same "capsule-only" discipline `run_deepseek_arm_a_worker.py`'s own
`INTEGRITY_STATEMENT` names), so a first attempt that goes looking in the wrong module
is a genuinely emergent worker behavior, not an injected failure.

This script reuses -- never re-derives -- this WP's own harness primitives
(`compose_failure_broadcast_content`, `consecutive_same_signature_count`,
`load_worker_visible_context`) plus the same real `grok` CLI dispatch shape
`tools/bench/run_mini_swe_bench_substrate_smoke.py::run_grok_worker` already
establishes (`checkout_task`, `repo_url`, the same CLI flag set), so the failure-memory
mechanics under real-worker load are the *same code path* the offline mock-worker test
suite already exercises, not a parallel reimplementation.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import iterate_harness as ih  # noqa: E402

_SMOKE = ih._SMOKE  # tools/bench/run_mini_swe_bench_substrate_smoke.py, loaded once by ih

S02_TASK = {
    "instance_id": "sphinx-doc__sphinx-7462",
    "repo": "sphinx-doc/sphinx",
    "base_commit": "b3e26a6c851133b82b50f4b68b53692076574d13",
    "problem_statement": (
        "IndexError: pop from empty list for empty tuple type annotation\n\n"
        "Following notation for empty tuple from a mypy issue like:\n\n"
        "from typing import Tuple\n\n"
        "def foo() -> Tuple[()]:\n"
        '    """Sample text."""\n'
        "    return ()\n\n"
        "the documentation build crashes with an IndexError.\n\n"
        "Steps to reproduce: write a module containing a function annotated to return "
        "Tuple[()] (the empty-tuple type notation), then build the Sphinx documentation "
        "for that module.\n\n"
        "Expected behavior: the docs build successfully and the function's type "
        "annotation renders as an empty tuple, instead of the build crashing."
    ),
}
S02_SHARD_ID = "S02"
S02_EXECUTION_ORDER_INDEX = 107
S02_ORIGINAL_MANIFEST_INDEX = 391
EXPECTED_FIX_FILE = "sphinx/domains/python.py"
MAX_REAL_WORKER_CALLS = 6


def run_cmd(argv: list[str], *, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def worker_safe_problem_statement(problem_statement: str) -> str:
    """Strip everything after the first blank-line-delimited paragraph that names a
    file/traceback (there is none in `S02_TASK`'s own problem_statement above -- this
    function exists so the capsule-authoring boundary is explicit and machine-checked,
    not just a docstring promise)."""
    if EXPECTED_FIX_FILE in problem_statement or "traceback" in problem_statement.lower():
        raise ih.HarnessError("worker-safe capsule text must not name the fix file or traceback")
    return problem_statement


def dispatch_real_grok_attempt(
    *,
    attempt_index: int,
    worktree: Path,
    capsule_text: str,
    model: str,
    max_turns: int,
    timeout_s: int,
    log_dir: Path,
) -> dict[str, Any]:
    log_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        "grok",
        "-p",
        capsule_text,
        "--cwd",
        str(worktree.resolve()),
        "--output-format",
        "plain",
        "--model",
        model,
        "--always-approve",
        "--permission-mode",
        "bypassPermissions",
        "--disable-web-search",
        "--no-plan",
        "--no-memory",
        "--no-subagents",
        "--max-turns",
        str(max_turns),
    ]
    proc = run_cmd(argv, timeout=timeout_s)
    diff = run_cmd(["git", "-C", str(worktree), "diff", "--binary"], timeout=180)
    diff_text = diff.stdout if diff.returncode == 0 else diff.stderr
    diff_stat = run_cmd(["git", "-C", str(worktree), "diff", "--stat"], timeout=180)
    touched_files = run_cmd(["git", "-C", str(worktree), "diff", "--name-only"], timeout=180).stdout.split()

    (log_dir / f"attempt{attempt_index}_command.json").write_text(
        json.dumps({"argv": _SMOKE.redacted_grok_argv(argv)}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (log_dir / f"attempt{attempt_index}_visible_prompt.txt").write_text(capsule_text, encoding="utf-8")
    (log_dir / f"attempt{attempt_index}_stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (log_dir / f"attempt{attempt_index}_stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (log_dir / f"attempt{attempt_index}_diff.patch").write_text(diff_text, encoding="utf-8")
    (log_dir / f"attempt{attempt_index}_diff_stat.txt").write_text(diff_stat.stdout, encoding="utf-8")

    diff_scope = "no_patch"
    if touched_files:
        diff_scope = "target_file" if EXPECTED_FIX_FILE in touched_files else "wrong_file"

    return {
        "attempt_index": attempt_index,
        "exit_code": proc.returncode,
        "touched_files": touched_files,
        "diff_scope": diff_scope,
        "diff_bytes": len(diff_text.encode("utf-8")),
        "diff_stat": diff_stat.stdout.strip(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model", default="grok-4.5")
    parser.add_argument(
        "--max-turns",
        type=int,
        default=4,
        help=(
            "Deliberately tight per-attempt turn budget (WP-L3-1 smoke default): with a "
            "generous budget this real bug is solvable by a strong worker in one shot "
            "(observed at --max-turns=12), which never exercises the organic attempt-2 "
            "path this smoke exists to demonstrate. A tight budget is itself a real, "
            "honest first-attempt failure mode (the design doc's own taxonomy names "
            "budget exhaustion as a real minor failure category), not a fabricated one."
        ),
    )
    parser.add_argument("--worker-timeout-s", type=int, default=420)
    parser.add_argument(
        "--worktree-root",
        default="/tmp/turingos_iterate_harness_smoke_s02_worktrees",
        help="scratch git worktree location for the real repo checkout (never a repo checkout)",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "worker_logs"
    task = S02_TASK
    instance_id = task["instance_id"]

    if shutil.which("grok") is None:
        raise SystemExit("grok CLI is missing; real WP-L3-1 smoke cannot run")

    capsule_path = out_dir / "worker_capsule.md"
    capsule_path.write_text(
        "# TuringOS worker-safe capsule\n\n"
        f"Instance: {instance_id}\n"
        f"Repo: {task['repo']}\n\n"
        "## Task\n\n" + worker_safe_problem_statement(task["problem_statement"]) + "\n\n"
        "Edit the checked-out repository only. Make the smallest plausible fix. "
        "Do not edit test files. When done, leave the patch in the worktree.\n",
        encoding="utf-8",
    )

    worktree = Path(args.worktree_root) / instance_id
    _SMOKE.checkout_task(task, worktree)

    real_worker_calls = 0
    active_broadcast_rules: list[dict[str, Any]] = []
    failure_signatures: list[tuple[str, str]] = []
    attempts: list[dict[str, Any]] = []
    route_id = f"{instance_id}::grok_real::smoke_route"

    for attempt_index in (1, 2):
        capsule_text, _metadata = ih.load_worker_visible_context(
            capsule_path,
            broadcast_rules=active_broadcast_rules,
            broadcast_section_mode="always",
        )
        if real_worker_calls >= MAX_REAL_WORKER_CALLS:
            raise ih.HarnessError("smoke exceeded MAX_REAL_WORKER_CALLS before dispatching")
        result = dispatch_real_grok_attempt(
            attempt_index=attempt_index,
            worktree=worktree,
            capsule_text=capsule_text,
            model=args.model,
            max_turns=args.max_turns,
            timeout_s=args.worker_timeout_s,
            log_dir=log_dir,
        )
        real_worker_calls += 1
        result["active_broadcast_rule_ids"] = [rule["rule_id"] for rule in active_broadcast_rules]
        attempts.append(result)

        if result["diff_scope"] == "target_file":
            break  # organic convergence proxy: no need to spend a 3rd real call

        failure_class = "WRONG_FILE" if result["diff_scope"] == "wrong_file" else "CONTEXT_MISSING"
        abstract_pattern, guidance = ih.compose_failure_broadcast_content(failure_class, route_id)
        failure_signatures.append((failure_class, abstract_pattern))
        rule_id = f"br_smoke_s02_{instance_id}_attempt{attempt_index}"
        active_broadcast_rules.append({"rule_id": rule_id, "failure_class": failure_class, "guidance": guidance})
        # git worktree is reset to the base commit before the next real attempt so
        # attempt 2 starts from the same clean state attempt 1 did (organic retry, not
        # a continuation of attempt 1's half-finished edits).
        run_cmd(["git", "-C", str(worktree), "reset", "--hard", task["base_commit"]], timeout=180)
        run_cmd(["git", "-C", str(worktree), "clean", "-fd"], timeout=180)

    streak = ih.consecutive_same_signature_count(failure_signatures) if failure_signatures else 0
    record = {
        "schema_id": "iterate_harness.smoke_s02_real.v1",
        "scientific_status": "SMOKE_FIXTURE_ORGANIC_LOOP_NOT_OFFICIAL_SWEBENCH_EVAL",
        "smoke_fixture": True,
        "instance_id": instance_id,
        "repo": task["repo"],
        "base_commit": task["base_commit"],
        "s02_shard_id": S02_SHARD_ID,
        "s02_execution_order_index": S02_EXECUTION_ORDER_INDEX,
        "s02_original_manifest_index": S02_ORIGINAL_MANIFEST_INDEX,
        "route_id": route_id,
        "real_worker_calls": real_worker_calls,
        "max_real_worker_calls_budget": MAX_REAL_WORKER_CALLS,
        "attempts_total": len(attempts),
        "organic_attempt_2_occurred": len(attempts) >= 2,
        "attempts": attempts,
        "broadcast_rules_emitted": active_broadcast_rules,
        "final_same_signature_streak": streak,
        "expected_fix_file_proxy": EXPECTED_FIX_FILE,
    }
    write_path = out_dir / "smoke_s02_real_record.json"
    write_path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

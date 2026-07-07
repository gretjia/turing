#!/usr/bin/env python3
"""Run direct Grok baseline on SWE-bench-shaped tasks.

This intentionally bypasses TuringOS. It exists only as the paired baseline arm
for small-scale smoke and benchmark ramps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


def digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_tasks(path: Path, limit: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            task = json.loads(line)
            for key in ("instance_id", "repo", "base_commit", "problem_statement"):
                if key not in task:
                    raise ValueError(f"task missing {key}")
            tasks.append(task)
            if len(tasks) >= limit:
                break
    if not tasks:
        raise ValueError("no tasks loaded")
    return tasks


def repo_url(repo: str) -> str:
    if repo.startswith(("http://", "https://", "git@")):
        return repo
    return f"https://github.com/{repo}.git"


def run_cmd(argv: list[str], *, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def run_cmd_timed(argv: list[str], *, timeout: int) -> tuple[subprocess.CompletedProcess[str], int]:
    start = time.monotonic()
    try:
        proc = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        proc = subprocess.CompletedProcess(argv, 124, stdout, stderr + "\nTIMEOUT")
    return proc, max(1, int((time.monotonic() - start) * 1000))


def direct_prompt(task: dict[str, Any]) -> str:
    return (
        "Fix this SWE-bench task in the checked-out repository.\n"
        "Make the smallest plausible code patch. Do not output private chain-of-thought.\n"
        "Edit the worktree and stop when a candidate patch exists.\n"
        f"Instance: {task['instance_id']}\n"
        f"Repo: {task['repo']}\n"
        f"Base commit: {task['base_commit']}\n"
        "Task:\n"
        f"{task['problem_statement']}\n"
    )


def redacted_argv(argv: list[str]) -> list[str]:
    result = list(argv)
    if "-p" in result:
        index = result.index("-p")
        if index + 1 < len(result):
            result[index + 1] = "<direct_baseline_prompt>"
    return result


def checkout_task(task: dict[str, Any], worktree: Path) -> None:
    if worktree.exists():
        shutil.rmtree(worktree)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    clone = run_cmd(
        ["git", "clone", "--filter=blob:none", "--no-checkout", repo_url(task["repo"]), str(worktree)],
        timeout=900,
    )
    if clone.returncode != 0:
        raise RuntimeError(f"git clone failed for {task['instance_id']}:\n{clone.stderr}")
    checkout = run_cmd(["git", "-C", str(worktree), "checkout", task["base_commit"]], timeout=900)
    if checkout.returncode != 0:
        raise RuntimeError(f"git checkout failed for {task['instance_id']}:\n{checkout.stderr}")


def run_task(
    task: dict[str, Any],
    out_dir: Path,
    worktree_root: Path,
    model: str,
    max_turns: int,
    timeout_s: int,
    dry_run: bool,
) -> dict[str, Any]:
    instance_id = task["instance_id"]
    instance_dir = out_dir / f"direct_baseline_{instance_id}"
    instance_dir.mkdir(parents=True, exist_ok=True)
    prompt = direct_prompt(task)
    worktree = worktree_root / hashlib.sha256(f"{instance_id}:{model}".encode("utf-8")).hexdigest()[:16]
    argv = [
        "grok",
        "-p",
        prompt,
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
        "--verbatim",
    ]
    (instance_dir / "command.json").write_text(
        json.dumps({"argv": redacted_argv(argv)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (instance_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    if dry_run:
        result = {
            "schema_id": "DirectGrokBaselineSmoke.v1",
            "instance_id": instance_id,
            "model": model,
            "max_turns": max_turns,
            "status": "DRY_RUN",
            "worktree": str(worktree.resolve()),
            "prompt_hash": digest_text(prompt),
        }
        (instance_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    checkout_task(task, worktree)
    proc, elapsed_ms = run_cmd_timed(argv, timeout=timeout_s)
    diff = run_cmd(["git", "-C", str(worktree), "diff", "--binary"], timeout=180)
    diff_text = diff.stdout if diff.returncode == 0 else diff.stderr
    (instance_dir / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (instance_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (instance_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    result = {
        "schema_id": "DirectGrokBaselineSmoke.v1",
        "instance_id": instance_id,
        "model": model,
        "max_turns": max_turns,
        "status": "RUN",
        "exit_code": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "patch_hash": digest_text(diff_text),
        "patch_nonempty": bool(diff_text.strip()),
        "worktree": str(worktree.resolve()),
    }
    (instance_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-jsonl", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--model", default="grok-build")
    parser.add_argument("--max-turns", type=int, default=50)
    parser.add_argument("--worker-timeout-s", type=int, default=1200)
    parser.add_argument("--worktree-root", default="/tmp/turingos_direct_grok_baseline")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    worktree_root = Path(args.worktree_root)
    tasks = read_tasks(Path(args.tasks_jsonl), args.limit)
    runs = [
        run_task(task, out_dir, worktree_root, args.model, args.max_turns, args.worker_timeout_s, args.dry_run)
        for task in tasks
    ]
    summary = {
        "schema_id": "DirectGrokBaselineSmokeSummary.v1",
        "sample_size": len(runs),
        "model": args.model,
        "max_turns": args.max_turns,
        "dry_run": args.dry_run,
        "runs": runs,
    }
    (out_dir / "direct_baseline_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

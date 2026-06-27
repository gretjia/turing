#!/usr/bin/env python3
"""Evaluate Django SWE-bench patches against task test_patch target tests."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def read_tasks(path: Path, limit: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            task = json.loads(line)
            tasks.append(task)
            if len(tasks) >= limit:
                break
    return tasks


def parse_fail_to_pass(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        loaded = json.loads(raw)
        if not isinstance(loaded, list):
            raise ValueError("FAIL_TO_PASS string must decode to list")
        return [str(item) for item in loaded]
    raise ValueError("FAIL_TO_PASS must be a list or JSON string list")


def django_test_labels(fail_to_pass: list[str]) -> list[str]:
    labels: list[str] = []
    for item in fail_to_pass:
        if " (" in item and item.endswith(")"):
            test_name, class_path = item[:-1].split(" (", 1)
            labels.append(f"{class_path}.{test_name}")
        else:
            labels.append(item)
    return labels


def run_cmd(argv: list[str], *, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def ensure_django_venv(venv: Path) -> Path:
    python = venv / "bin" / "python"
    if python.exists():
        return python
    create = run_cmd(["python3", "-m", "venv", str(venv)], timeout=180)
    if create.returncode != 0:
        raise RuntimeError(f"venv create failed:\n{create.stderr}")
    pip = run_cmd([str(python), "-m", "pip", "install", "-q", "--upgrade", "pip"], timeout=300)
    if pip.returncode != 0:
        raise RuntimeError(f"pip upgrade failed:\n{pip.stderr}")
    deps = run_cmd([str(python), "-m", "pip", "install", "-q", "asgiref", "pytz", "sqlparse"], timeout=300)
    if deps.returncode != 0:
        raise RuntimeError(f"django deps install failed:\n{deps.stderr}")
    return python


def patch_path_for_arm(task: dict[str, Any], arm: str, root: Path) -> Path:
    instance_id = task["instance_id"]
    if arm == "turingos":
        return root / "instances" / instance_id / "worker_logs" / "diff.patch"
    if arm == "direct":
        return root / f"direct_baseline_{instance_id}" / "diff.patch"
    raise ValueError(f"unknown arm {arm}")


def evaluate_patch(
    task: dict[str, Any],
    arm: str,
    root: Path,
    out_dir: Path,
    work_root: Path,
    python: Path,
) -> dict[str, Any]:
    instance_id = task["instance_id"]
    result_dir = out_dir / arm / instance_id
    result_dir.mkdir(parents=True, exist_ok=True)
    patch = patch_path_for_arm(task, arm, root)
    if task.get("repo") != "django/django":
        return {
            "instance_id": instance_id,
            "arm": arm,
            "result": "NOT_RUN",
            "reason": "only django/django target-test evaluation is supported by this smoke evaluator",
        }
    if not patch.exists() or not patch.read_text(encoding="utf-8", errors="replace").strip():
        return {"instance_id": instance_id, "arm": arm, "result": "FAIL", "reason": "missing_or_empty_patch"}

    eval_tree = work_root / f"{arm}_{instance_id}"
    if eval_tree.exists():
        shutil.rmtree(eval_tree)
    clone = run_cmd(
        ["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/django/django.git", str(eval_tree)],
        timeout=900,
    )
    if clone.returncode != 0:
        return {"instance_id": instance_id, "arm": arm, "result": "ERROR", "reason": "clone_failed", "stderr": clone.stderr[-2000:]}
    checkout = run_cmd(["git", "-C", str(eval_tree), "checkout", task["base_commit"]], timeout=900)
    if checkout.returncode != 0:
        return {"instance_id": instance_id, "arm": arm, "result": "ERROR", "reason": "checkout_failed", "stderr": checkout.stderr[-2000:]}
    apply_patch = run_cmd(["git", "-C", str(eval_tree), "apply", str(patch.resolve())], timeout=180)
    if apply_patch.returncode != 0:
        return {
            "instance_id": instance_id,
            "arm": arm,
            "result": "FAIL",
            "reason": "patch_apply_failed",
            "stderr": apply_patch.stderr[-2000:],
        }
    test_patch = result_dir / "test.patch"
    test_patch.write_text(str(task.get("test_patch", "")), encoding="utf-8")
    apply_tests = run_cmd(["git", "-C", str(eval_tree), "apply", str(test_patch.resolve())], timeout=180)
    if apply_tests.returncode != 0:
        return {
            "instance_id": instance_id,
            "arm": arm,
            "result": "FAIL",
            "reason": "test_patch_apply_failed_after_candidate_patch",
            "stderr": apply_tests.stderr[-2000:],
        }
    labels = django_test_labels(parse_fail_to_pass(task["FAIL_TO_PASS"]))
    command = [
        str(python),
        str(eval_tree / "tests" / "runtests.py"),
        *labels,
        "--verbosity",
        "2",
    ]
    env = {"PYTHONPATH": str(eval_tree)}
    proc = subprocess.run(command, text=True, capture_output=True, timeout=600, env=env)
    (result_dir / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (result_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    return {
        "instance_id": instance_id,
        "arm": arm,
        "result": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "target_tests": labels,
        "stdout": str(result_dir / "stdout.txt"),
        "stderr": str(result_dir / "stderr.txt"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-jsonl", required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--turingos-dir", required=True)
    parser.add_argument("--direct-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--work-root", default="/tmp/turingos_django_patch_eval")
    parser.add_argument("--venv", default="/tmp/turingos-django-swebench-venv")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    python = ensure_django_venv(Path(args.venv))
    tasks = read_tasks(Path(args.tasks_jsonl), args.limit)
    results = []
    for task in tasks:
        results.append(evaluate_patch(task, "turingos", Path(args.turingos_dir), out, Path(args.work_root), python))
        results.append(evaluate_patch(task, "direct", Path(args.direct_dir), out, Path(args.work_root), python))
    by_arm = {"turingos": {"pass": 0, "total": 0}, "direct": {"pass": 0, "total": 0}}
    for result in results:
        arm = result["arm"]
        by_arm[arm]["total"] += 1
        if result["result"] == "PASS":
            by_arm[arm]["pass"] += 1
    packet = {
        "schema_id": "DjangoSweBenchPatchEval.v1",
        "sample_size": len(tasks),
        "results": results,
        "by_arm": by_arm,
        "statistical_claim": "none_smoke_only",
    }
    (out / "patch_eval_summary.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if all(result["result"] in {"PASS", "FAIL", "NOT_RUN"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

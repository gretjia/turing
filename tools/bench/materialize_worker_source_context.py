#!/usr/bin/env python3
"""Build worker-visible source context from base commits and candidate paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def diff_paths(patch_text: str) -> list[str]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        match = re.match(r"diff --git a/(.+?) b/(.+)", line)
        if match:
            path = match.group(2)
            if path not in paths:
                paths.append(path)
    return paths


def safe_relative_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe source path: {path}")
    return candidate


def source_cache_path(source_cache_dir: Path, repo: str, commit: str, path: str) -> Path:
    return source_cache_dir / repo.replace("/", "__") / commit / safe_relative_path(path)


def fetch_github_raw(repo: str, commit: str, path: str, *, timeout_s: int) -> str:
    safe_relative_path(path)
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "turingos-m3-source-context"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return response.read().decode("utf-8")


def read_source(
    *,
    repo: str,
    commit: str,
    path: str,
    source_cache_dir: Path | None,
    timeout_s: int,
) -> tuple[str, str]:
    if source_cache_dir is not None:
        cache_path = source_cache_path(source_cache_dir, repo, commit, path)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8"), str(cache_path)
    return fetch_github_raw(repo, commit, path, timeout_s=timeout_s), "github_raw"


def worker_task_records(root: Path, shard: str, window: str) -> list[dict[str, Any]]:
    report = load_json(root / "shards" / shard / "ipqc" / window / "worker_safe_tasks" / "worker_safe_tasks_report.json")
    tasks = report.get("tasks")
    if report.get("status") != "PASS" or not isinstance(tasks, list):
        raise ValueError("worker-safe task report must be PASS and contain tasks")
    return [task for task in tasks if isinstance(task, dict)]


def context_markdown(
    *,
    instance_id: str,
    repo: str,
    commit: str,
    files: list[dict[str, str]],
) -> str:
    lines = [
        f"# Source Context for {instance_id}",
        "",
        f"Repository: {repo}",
        f"Base commit: {commit}",
        "Selection rule: worker-derived candidate diff paths only.",
        "Forbidden fields remain excluded: gold patch, test patch, FAIL_TO_PASS, PASS_TO_PASS, hints.",
        "",
    ]
    for file_row in files:
        lines.extend(
            [
                f"## {file_row['path']}",
                "",
                "````text",
                file_row["content"].rstrip(),
                "````",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def materialize(
    *,
    root: Path,
    shard: str,
    window: str,
    source_cache_dir: Path | None = None,
    context_name: str = "source_context.md",
    timeout_s: int = 30,
) -> dict[str, Any]:
    tasks = worker_task_records(root, shard, window)
    out_snapshot_root = root / "shards" / shard / "ipqc" / window / "source_snapshots"
    results: list[dict[str, Any]] = []
    problems: list[str] = []

    for task in tasks:
        instance_id = task.get("instance_id")
        capsule_path = task.get("worker_capsule_path")
        if not isinstance(instance_id, str) or not isinstance(capsule_path, str):
            problems.append("task row missing instance_id or worker_capsule_path")
            continue
        task_packet_path = root / "shards" / shard / "ipqc" / window / "worker_safe_tasks" / instance_id / "task_packet.json"
        candidate_path = root / "shards" / shard / "tasks" / instance_id / "candidate.patch"
        if not candidate_path.exists():
            problems.append(f"{instance_id}: candidate.patch missing")
            continue
        packet = load_json(task_packet_path)
        repo = packet.get("repo")
        commit = packet.get("base_commit")
        if not isinstance(repo, str) or not isinstance(commit, str):
            problems.append(f"{instance_id}: task packet missing repo/base_commit")
            continue
        paths = diff_paths(candidate_path.read_text(encoding="utf-8"))
        if not paths:
            problems.append(f"{instance_id}: candidate patch has no diff paths")
            continue

        file_rows: list[dict[str, str]] = []
        task_problems: list[str] = []
        for path in paths:
            try:
                content, source = read_source(
                    repo=repo,
                    commit=commit,
                    path=path,
                    source_cache_dir=source_cache_dir,
                    timeout_s=timeout_s,
                )
                snapshot_path = out_snapshot_root / instance_id / safe_relative_path(path)
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                snapshot_path.write_text(content, encoding="utf-8")
                file_rows.append(
                    {
                        "path": path,
                        "source": source,
                        "sha256": sha256_text(content),
                        "content": content,
                    }
                )
            except (OSError, ValueError, urllib.error.URLError) as error:
                task_problems.append(f"{path}: {type(error).__name__}: {error}")

        if task_problems:
            problems.extend(f"{instance_id}: {problem}" for problem in task_problems)
            status = "FAIL"
        else:
            status = "PASS"

        context_text = context_markdown(instance_id=instance_id, repo=repo, commit=commit, files=file_rows)
        context_path = (root / capsule_path).parent / context_name
        context_path.write_text(context_text, encoding="utf-8")
        results.append(
            {
                "instance_id": instance_id,
                "status": status,
                "repo": repo,
                "base_commit": commit,
                "candidate_patch_path": str(candidate_path.relative_to(root)),
                "source_context_path": str(context_path.relative_to(root)),
                "source_context_sha256": sha256_text(context_text),
                "source_snapshot_root": str((out_snapshot_root / instance_id).relative_to(root)),
                "paths": [
                    {"path": row["path"], "sha256": row["sha256"], "source": row["source"]}
                    for row in file_rows
                ],
                "problems": task_problems,
            }
        )

    report = {
        "schema_id": "turingos.swebench_worker_source_context.v1",
        "status": "PASS" if not problems else "FAIL",
        "shard_id": shard,
        "ipqc_window_id": window,
        "context_name": context_name,
        "selection_rule": "worker_derived_candidate_diff_paths_only",
        "task_count": len(tasks),
        "tasks": results,
        "problems": problems,
    }
    write_json(root / "shards" / shard / "ipqc" / window / "worker_source_context_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--source-cache-dir", type=Path)
    parser.add_argument("--context-name", default="source_context.md")
    parser.add_argument("--timeout-s", type=int, default=30)
    args = parser.parse_args()
    report = materialize(
        root=args.root,
        shard=args.shard,
        window=args.window,
        source_cache_dir=args.source_cache_dir,
        context_name=args.context_name,
        timeout_s=args.timeout_s,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

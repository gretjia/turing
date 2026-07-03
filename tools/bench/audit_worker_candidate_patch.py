#!/usr/bin/env python3
"""Audit one worker-derived candidate patch before it can enter predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REQUIRED_INTEGRITY_MARKERS = [
    "worker-safe",
    "dataset patches",
    "test patches",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "gold patches",
    "hidden evaluator labels",
]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def diff_paths(patch_text: str) -> list[str]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        match = re.match(r"diff --git a/(.+?) b/(.+)", line)
        if match:
            paths.append(match.group(2))
    return paths


def is_test_path(path: str) -> bool:
    parts = path.split("/")
    basename = parts[-1] if parts else path
    return (
        basename.startswith("test_")
        or basename.endswith("_test.py")
        or any(part in {"test", "tests", "testing"} for part in parts)
    )


def check_patch_applies(patch_path: Path, apply_root: Path) -> tuple[bool, str]:
    if not apply_root.exists():
        return False, f"apply root missing: {apply_root}"
    patch_text = patch_path.read_text(encoding="utf-8")
    missing_paths = [path for path in diff_paths(patch_text) if not (apply_root / path).exists()]
    if missing_paths:
        return False, "source snapshot missing diff path(s): " + ", ".join(missing_paths)
    with tempfile.TemporaryDirectory(prefix="turingos-patch-apply-") as tmp:
        worktree = Path(tmp) / "worktree"
        shutil.copytree(apply_root, worktree)
        subprocess.run(["git", "init", "-q"], cwd=worktree, check=True)
        subprocess.run(["git", "add", "."], cwd=worktree, check=True)
        result = subprocess.run(
            ["git", "apply", "--check", "--verbose", str(patch_path.resolve())],
            cwd=worktree,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    output = result.stdout.strip()
    if "Skipped patch" in output:
        return False, output
    return result.returncode == 0, output


def audit_candidate(root: Path, shard: str, instance_id: str, *, apply_root: Path | None = None) -> dict[str, Any]:
    task_dir = root / "shards" / shard / "tasks" / instance_id
    patch_path = task_dir / "candidate.patch"
    receipt_path = task_dir / "worker_receipt.json"
    problems: list[str] = []
    apply_check: dict[str, Any] | None = None

    if not patch_path.exists():
        problems.append("candidate.patch missing")
        patch_bytes = b""
        patch_text = ""
    else:
        patch_bytes = patch_path.read_bytes()
        patch_text = patch_bytes.decode("utf-8")
        if not patch_text.startswith("diff --git "):
            problems.append("candidate patch is not a unified diff")

    if not receipt_path.exists():
        problems.append("worker_receipt.json missing")
        receipt: dict[str, Any] = {}
    else:
        receipt = load_json(receipt_path)

    if receipt.get("status") != "COMPLETED":
        problems.append("worker receipt status is not COMPLETED")
    if receipt.get("instance_id") != instance_id:
        problems.append("worker receipt instance_id mismatch")
    if receipt.get("candidate_source") != "worker_derived":
        problems.append("candidate_source is not worker_derived")
    if receipt.get("submitted_patch_scope") != "source_only":
        problems.append("submitted_patch_scope is not source_only")

    source_capsule = receipt.get("source_capsule_path")
    if not isinstance(source_capsule, str) or "worker_safe_tasks" not in source_capsule:
        problems.append("source capsule is not a worker-safe capsule path")
    elif not (root / source_capsule).exists():
        problems.append("source capsule path missing")

    integrity_statement = receipt.get("integrity_statement")
    if not isinstance(integrity_statement, str) or not all(
        marker in integrity_statement for marker in REQUIRED_INTEGRITY_MARKERS
    ):
        problems.append("integrity statement does not deny hidden/gold fields")

    paths = diff_paths(patch_text)
    if not paths and patch_text:
        problems.append("candidate patch has no diff paths")
    for path in paths:
        if is_test_path(path):
            problems.append(f"candidate patch touches test path: {path}")

    if apply_root is not None and patch_path.exists() and patch_bytes:
        applies, output = check_patch_applies(patch_path, apply_root)
        apply_check = {
            "status": "PASS" if applies else "FAIL",
            "apply_root": str(apply_root),
            "output": output,
        }
        if not applies:
            problems.append(f"candidate patch does not apply to source snapshot: {output}")

    patch_sha = sha256_bytes(patch_bytes)
    if patch_bytes:
        (task_dir / "candidate.patch.sha256").write_text(patch_sha + "\n", encoding="utf-8")

    report = {
        "schema_id": "turingos.swebench_worker_candidate_audit.v1",
        "status": "PASS" if not problems else "FAIL",
        "shard_id": shard,
        "instance_id": instance_id,
        "candidate_source": receipt.get("candidate_source"),
        "submitted_patch_scope": receipt.get("submitted_patch_scope"),
        "candidate_patch_path": str(patch_path.relative_to(root)),
        "candidate_patch_sha256": patch_sha,
        "diff_paths": paths,
        "apply_check": apply_check,
        "problems": problems,
    }
    write_json(task_dir / "worker_candidate_audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--apply-root", type=Path)
    args = parser.parse_args()
    report = audit_candidate(args.root, args.shard, args.instance_id, apply_root=args.apply_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

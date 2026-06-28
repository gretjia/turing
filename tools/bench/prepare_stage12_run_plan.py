#!/usr/bin/env python3
"""Freeze Stage12-A02 runner inputs without running workers."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]


def load_validator():
    path = Path(__file__).resolve().with_name("validate_stage12_contract.py")
    spec = importlib.util.spec_from_file_location("stage12_contract_validator", path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load validator from {path}")
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL row: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: JSONL row must be an object")
            rows.append(row)
    return rows


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def fail_report(root: Path, problems: list[str]) -> dict[str, Any]:
    report = {
        "schema_id": "turingos.stage12.a02_report.v1",
        "stage": "Stage12",
        "atom": "Stage12-A02",
        "status": "FAIL",
        "root": str(root),
        "problems": problems,
        "a02_does_not_run_workers": True,
        "no_bundles_generated_by_a02": True,
    }
    write_json(root / "stage12_a02_report.json", report)
    return report


def stage12_a03_command(root: Path) -> list[str]:
    return [
        "python3",
        "tools/bench/run_mini_swe_bench_substrate_smoke.py",
        "--loop-until-pass",
        "--authorization-mode",
        "required",
        "--tasks-jsonl",
        relative_to_repo(root / "tasks_20.jsonl"),
        "--out-dir",
        relative_to_repo(root),
        "--limit",
        "20",
    ]


def strict_audit_command(root: Path) -> list[str]:
    return [
        "python3",
        "tools/bench/audit_micro_tape_decision_dag.py",
        "--strict-vpput",
        "--strict-terminal-market",
        "--require-authorization-head",
        "--coverage",
        relative_to_repo(root / "turingos" / "substrate_coverage.json"),
        "--out-dir",
        relative_to_repo(root / "micro_tape_audit_strict"),
    ]


def prepare_run_plan(root: Path | str, *, source_jsonl: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    validator = load_validator()
    contract_report = validator.validate_root(root)
    if contract_report.get("status") != "PASS":
        return fail_report(root, ["contract validation failed: " + "; ".join(contract_report.get("problems", []))])

    task = load_json(root / "task_manifest.json")
    loop = load_json(root / "loop_manifest.json")

    source = source_jsonl or Path(task["source_dataset_reference"])
    if not source.exists():
        return fail_report(root, [f"source dataset missing: {source}"])

    actual_digest = sha256_file(source)
    expected_digest = task["source_dataset_digest"]
    if actual_digest != expected_digest:
        return fail_report(
            root,
            [f"source dataset digest mismatch: expected {expected_digest}, got {actual_digest}"],
        )

    try:
        rows = load_jsonl(source)
    except ValueError as exc:
        return fail_report(root, [str(exc)])
    if len(rows) < 20:
        return fail_report(root, [f"source dataset must contain at least 20 rows, got {len(rows)}"])

    first20 = rows[:20]
    first20_ids = [row.get("instance_id") for row in first20]
    manifest_ids = task["instance_ids"]
    if first20_ids != manifest_ids:
        return fail_report(
            root,
            [
                "source first 20 instance_ids do not match task_manifest: "
                f"expected {manifest_ids}, got {first20_ids}"
            ],
        )

    tasks_path = root / "tasks_20.jsonl"
    tasks_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in first20),
        encoding="utf-8",
    )

    plan_path = root / "stage12_run_plan.json"
    plan = {
        "schema_id": "turingos.stage12.run_plan.v1",
        "stage": "Stage12",
        "atom": "Stage12-A02",
        "status": "READY_FOR_STAGE12_A03",
        "task_count": 20,
        "instance_ids": manifest_ids,
        "source_dataset_reference": str(source),
        "source_dataset_digest": actual_digest,
        "tasks_jsonl": relative_to_repo(tasks_path),
        "tasks_jsonl_sha256": sha256_file(tasks_path),
        "authorization_mode": loop["authorization_mode"],
        "worker_mode_default": "configured_worker",
        "claim_boundary": "20-task scale/protocol evidence only; no statistical superiority/full-score claim",
        "a02_does_not_run_workers": True,
        "no_bundles_generated_by_a02": True,
        "expected_bundle_count_after_a03": 20,
        "old_stage_evidence_immutable": task["old_stage_evidence_immutable"],
        "stage12_a03_command_template": stage12_a03_command(root),
        "strict_audit_command_template": strict_audit_command(root),
    }
    write_json(plan_path, plan)

    report = {
        "schema_id": "turingos.stage12.a02_report.v1",
        "stage": "Stage12",
        "atom": "Stage12-A02",
        "status": "PASS",
        "root": str(root),
        "task_count": 20,
        "source_dataset_reference": str(source),
        "source_dataset_digest": actual_digest,
        "tasks_jsonl": relative_to_repo(tasks_path),
        "stage12_run_plan": relative_to_repo(plan_path),
        "problems": [],
        "a02_does_not_run_workers": True,
        "no_bundles_generated_by_a02": True,
        "expected_bundle_count_after_a03": 20,
    }
    write_json(root / "stage12_a02_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--source-jsonl", type=Path)
    args = parser.parse_args()

    report = prepare_run_plan(args.root, source_jsonl=args.source_jsonl)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

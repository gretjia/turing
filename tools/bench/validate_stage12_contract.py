#!/usr/bin/env python3
"""Validate the Stage12-A01 frozen contract before any Stage12 run."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SECRET_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def credential_hits(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return [f"{path.name}: credential-shaped value {match.group(0)[:8]}..." for match in SECRET_PATTERN.finditer(text)]


def require_bool_false(value: Any, name: str, problems: list[str]) -> None:
    if value is not False:
        problems.append(f"{name} must be false")


def require_bool_true(value: Any, name: str, problems: list[str]) -> None:
    if value is not True:
        problems.append(f"{name} must be true")


def validate_task_manifest(task: dict[str, Any], problems: list[str]) -> None:
    required = [
        "schema_id",
        "stage",
        "created_at_utc",
        "base_commit_sha",
        "source_dataset",
        "source_dataset_reference",
        "source_dataset_digest",
        "official_harness_version",
        "official_harness_digest",
        "selection_policy",
        "selection_seed",
        "task_count",
        "instance_ids",
        "excluded_instances",
        "exclusion_reason",
        "task_order",
        "frozen_before_run",
        "old_stage_evidence_immutable",
    ]
    for key in required:
        if key not in task:
            problems.append(f"task_manifest missing {key}")

    if task.get("schema_id") != "turingos.stage12.task_manifest.v1":
        problems.append("task_manifest schema_id must be turingos.stage12.task_manifest.v1")
    if task.get("stage") != "Stage12":
        problems.append("task_manifest stage must be Stage12")
    if task.get("task_count") != 20:
        problems.append("task_count must be 20")

    instance_ids = task.get("instance_ids")
    if not isinstance(instance_ids, list):
        problems.append("instance_ids must be a list")
        instance_ids = []
    if len(instance_ids) != 20:
        problems.append("instance_ids length must be 20")
    if len(set(instance_ids)) != len(instance_ids):
        problems.append("duplicate instance_id in instance_ids")
    if task.get("task_order") != instance_ids:
        problems.append("task_order must equal instance_ids")

    require_bool_true(task.get("frozen_before_run"), "frozen_before_run", problems)
    require_bool_true(task.get("old_stage_evidence_immutable"), "old_stage_evidence_immutable", problems)

    digest = task.get("source_dataset_digest")
    if not isinstance(digest, str) or not HASH_PATTERN.match(digest):
        problems.append("source_dataset_digest must be sha256:<64 lowercase hex>")
    harness_digest = task.get("official_harness_digest")
    if not isinstance(harness_digest, str) or not HASH_PATTERN.match(harness_digest):
        problems.append("official_harness_digest must be sha256:<64 lowercase hex>")


def validate_loop_manifest(loop: dict[str, Any], problems: list[str]) -> None:
    if loop.get("schema_id") != "turingos.stage12.loop_manifest.v1":
        problems.append("loop_manifest schema_id must be turingos.stage12.loop_manifest.v1")
    if loop.get("stage") != "Stage12":
        problems.append("loop_manifest stage must be Stage12")
    if loop.get("authorization_mode") != "required":
        problems.append("authorization_mode must be required")

    require_bool_false(loop.get("human_interventions_allowed"), "human_interventions_allowed", problems)
    require_bool_false(loop.get("fallback_to_auto_authorization_allowed"), "fallback_to_auto_authorization_allowed", problems)
    if loop.get("manual_patch_count_allowed") != 0:
        problems.append("manual_patch_count_allowed must be 0")
    if loop.get("manual_rerun_selection_allowed") != 0:
        problems.append("manual_rerun_selection_allowed must be 0")

    budget = loop.get("budget_profile")
    if not isinstance(budget, dict):
        problems.append("budget_profile missing")
    else:
        for key in [
            "max_attempts_per_instance",
            "max_wall_seconds_per_instance",
            "max_tokens_per_instance",
            "max_total_wall_seconds",
            "max_total_tokens",
        ]:
            if not isinstance(budget.get(key), int) or budget[key] <= 0:
                problems.append(f"budget_profile.{key} must be a positive integer")

    retry = loop.get("retry_policy")
    if not isinstance(retry, dict):
        problems.append("retry_policy missing")
    elif not retry.get("allowed_retry_authorization_events"):
        problems.append("retry_policy.allowed_retry_authorization_events missing")

    vpput = loop.get("vpput_policy")
    if not isinstance(vpput, dict):
        problems.append("vpput_policy missing")
    else:
        if vpput.get("failed_progress") != 0:
            problems.append("vpput_policy.failed_progress must be 0")
        if vpput.get("solved_progress") != 1:
            problems.append("vpput_policy.solved_progress must be 1")
        require_bool_true(
            vpput.get("cost_includes_all_agents_branches_failed_proposals_tool_stdout_context_reranks_abandoned_routes_wall_time"),
            "vpput_policy.cost_includes_all_agents_branches_failed_proposals_tool_stdout_context_reranks_abandoned_routes_wall_time",
            problems,
        )

    release = loop.get("stage_release_policy")
    if not isinstance(release, dict):
        problems.append("stage_release_policy missing")
    else:
        require_bool_true(release.get("exact_20_bundles_required"), "exact_20_bundles_required", problems)
        require_bool_false(release.get("dry_run_can_release"), "dry_run_can_release", problems)
        require_bool_true(release.get("external_exact_sha_audit_required"), "external_exact_sha_audit_required", problems)
        require_bool_false(
            release.get("static_only_external_review_can_release"),
            "static_only_external_review_can_release",
            problems,
        )


def validate_claim_boundary(text: str, problems: list[str]) -> None:
    lowered = text.lower()
    required_phrases = [
        "20-task scale/protocol evidence only",
        "not statistically powered",
        "no product superiority claim",
        "no full swe-bench score claim",
        "does not upgrade external cli worker provenance to full",
        "exact-sha executable/fetching external audit",
    ]
    for phrase in required_phrases:
        if phrase not in lowered:
            problems.append(f"claim boundary missing required phrase: {phrase}")

    forbidden_patterns = [
        (r"proves\s+statistical\s+superiority", "statistical superiority claim is forbidden"),
        (r"statistically\s+significant\s+superiority", "statistical superiority claim is forbidden"),
        (r"significantly\s+beats\s+baseline", "statistical superiority claim is forbidden"),
        (r"proves\s+full\s+swe-bench\s+score", "full SWE-bench/full-score claim is forbidden"),
        (r"full[-\s]?score\s+claim\s+allowed", "full-score claim is forbidden"),
        (r"full\s+swe-bench\s+pass\s+achieved", "full SWE-bench/full-score claim is forbidden"),
    ]
    for pattern, message in forbidden_patterns:
        if re.search(pattern, lowered):
            problems.append(message)


def validate_root(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    problems: list[str] = []
    task_path = root / "task_manifest.json"
    loop_path = root / "loop_manifest.json"
    readme_path = root / "README.md"
    claim_path = root / "stage12_claim_boundary.md"
    commands_path = root / "stage12_acceptance_commands.md"

    try:
        task = load_json(task_path)
    except FileNotFoundError:
        task = {}
        problems.append("task_manifest.json missing")
    try:
        loop = load_json(loop_path)
    except FileNotFoundError:
        loop = {}
        problems.append("loop_manifest.json missing")

    validate_task_manifest(task, problems)
    validate_loop_manifest(loop, problems)

    if not readme_path.exists():
        problems.append("README.md missing")
    elif "validate_stage12_contract.py" not in readme_path.read_text(encoding="utf-8"):
        problems.append("README must include exact future validation commands")

    if not commands_path.exists():
        problems.append("stage12_acceptance_commands.md missing")
    elif "STAGE12_A01_CONTRACT_FROZEN" not in commands_path.read_text(encoding="utf-8"):
        problems.append("stage12_acceptance_commands.md must include final contract assertion")

    if not claim_path.exists():
        problems.append("stage12_claim_boundary.md missing")
    else:
        validate_claim_boundary(claim_path.read_text(encoding="utf-8"), problems)

    for path in [task_path, loop_path, readme_path, claim_path, commands_path]:
        problems.extend(credential_hits(path))

    return {
        "schema_id": "turingos.stage12.contract_validation.v1",
        "status": "FAIL" if problems else "PASS",
        "root": str(root),
        "task_count": task.get("task_count"),
        "instance_count": len(task.get("instance_ids", [])) if isinstance(task.get("instance_ids"), list) else 0,
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    report = validate_root(args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

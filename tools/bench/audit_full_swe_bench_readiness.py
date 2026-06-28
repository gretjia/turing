#!/usr/bin/env python3
"""Audit whether TuringOS is ready to start a full SWE-bench campaign.

This is a launch-readiness gate, not a benchmark result auditor. It prevents
Phase F blocker packets, shard fixtures, or structural repair-loop PASS from
being mistaken for permission to start a full sealed SWE-bench run.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_optional_json(path: Path) -> dict[str, Any]:
    return load_json(path) if path.exists() else {}


def _truthy(data: dict[str, Any], key: str) -> bool:
    return data.get(key) is True


def _false(data: dict[str, Any], key: str) -> bool:
    return data.get(key) is False


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.match(value) is not None


def audit_full_manifest(root: Path) -> tuple[str, list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    problems: list[str] = []
    details: dict[str, Any] = {"root": str(root)}
    required = ["task_manifest.json", "loop_manifest.json", "CLAIM_BOUNDARY.json", "full_campaign_acceptance_commands.md"]
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        blockers.append("full_dataset_manifest_freeze_required")
        details["missing_files"] = missing
        return "MISSING", blockers, problems, details

    task = load_json(root / "task_manifest.json")
    loop = load_json(root / "loop_manifest.json")
    claim = load_json(root / "CLAIM_BOUNDARY.json")
    commands = (root / "full_campaign_acceptance_commands.md").read_text(encoding="utf-8")

    ids = task.get("instance_ids")
    task_count = task.get("task_count")
    official_count = task.get("official_dataset_task_count")
    details.update(
        {
            "task_count": task_count,
            "official_dataset_task_count": official_count,
            "selection_policy": task.get("selection_policy"),
            "authorization_mode": loop.get("authorization_mode"),
        }
    )
    if task.get("selection_policy") != "ALL":
        problems.append("full task manifest must use selection_policy=ALL")
    if task.get("frozen_before_run") is not True:
        problems.append("full task manifest must be frozen_before_run=true")
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        problems.append("full task manifest instance_ids must be a string list")
    elif len(ids) != len(set(ids)):
        problems.append("full task manifest instance_ids must be unique")
    if not isinstance(task_count, int) or isinstance(task_count, bool) or task_count < 500:
        problems.append("full task manifest task_count must be at least the SWE-bench Verified 500-task dataset")
    if task_count != official_count:
        problems.append("task_count must equal official_dataset_task_count")
    if isinstance(ids, list) and task_count != len(ids):
        problems.append("task_count must equal len(instance_ids)")
    if task.get("excluded_instances") != []:
        problems.append("full task manifest must not exclude instances")
    if task.get("exclusion_reason") != {}:
        problems.append("full task manifest exclusion_reason must be empty")
    if not _sha256(task.get("source_dataset_digest")):
        problems.append("source_dataset_digest must be sha256-bound")
    if not _sha256(task.get("official_harness_digest")):
        problems.append("official_harness_digest must be sha256-bound")

    if loop.get("authorization_mode") != "required":
        problems.append("full campaign must use authorization_mode=required")
    if loop.get("fallback_to_auto_authorization_allowed") is not False:
        problems.append("fallback_to_auto_authorization_allowed must be false")
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
            value = budget.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                problems.append(f"budget_profile.{key} must be a positive integer")
    full_score_gate = loop.get("full_score_claim_gate")
    if not isinstance(full_score_gate, dict):
        problems.append("full_score_claim_gate missing")
    else:
        if full_score_gate.get("full_score_claim_allowed_before_run") is not False:
            problems.append("full_score_claim_before_run_forbidden")
        for key in [
            "requires_unsolved_count_zero",
            "requires_every_task_official_pass",
            "requires_final_pput_progress_one",
        ]:
            if full_score_gate.get(key) is not True:
                problems.append(f"full_score_claim_gate.{key} must be true")

    if claim.get("not_sampled_subset") is not True:
        problems.append("CLAIM_BOUNDARY.not_sampled_subset must be true")
    if claim.get("full_swe_bench_score_claim_allowed_before_run") is not False:
        problems.append("full_score_claim_before_run_forbidden")
    if claim.get("leaderboard_equivalence_claim_allowed_before_run") is not False:
        problems.append("leaderboard_equivalence_claim_before_run_forbidden")
    if "audit_micro_tape_decision_dag.py" not in commands or "--strict-vpput" not in commands:
        problems.append("acceptance commands must include strict MicroTape/VPPUT audit")

    return ("PASS" if not problems else "FAIL"), blockers, problems, details


def audit_full_swe_bench_readiness(
    *,
    phase_f_root: Path,
    repair_loop_root: Path,
    full_manifest_root: Path,
    stage16r_real_root: Path | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    problems: list[str] = []

    phase_f = load_optional_json(phase_f_root / "official_eval_replay_audit.json")
    repair = load_optional_json(repair_loop_root / "phase_f_repair_loop_audit.json")

    phase_f_status = phase_f.get("status")
    phase_f_replay = _truthy(phase_f, "official_evaluator_executable_replay")
    phase_f_release = _truthy(phase_f, "release_next_phase_g")
    if phase_f_status != "PASS" or not phase_f_replay or not phase_f_release:
        blockers.append("phase_f_evaluator_proof_pass_required")
    for key in [
        "full_swe_bench_score_claim_allowed",
        "full_dataset_claim_allowed",
        "leaderboard_equivalence_claim_allowed",
    ]:
        if phase_f.get(key) is True:
            problems.append(f"Phase F must not allow {key}")

    repair_status = repair.get("status")
    stage16r_real = (
        load_optional_json(stage16r_real_root / "stage16r_real_evaluator_summary.json")
        if stage16r_real_root is not None
        else {}
    )
    stage16r_real_count = stage16r_real.get("fresh_real_evaluator_bundle_count")
    stage16r_remaining = stage16r_real.get("remaining_repair_count")
    has_stage16r_real_bundles = isinstance(stage16r_real_count, int) and stage16r_real_count > 0
    if has_stage16r_real_bundles:
        if stage16r_remaining != 0:
            blockers.append("remaining_stage16r_real_repairs_required")
        if stage16r_real.get("status") != "PASS" and stage16r_remaining == 0:
            problems.append("completed Stage16R-real packet must report status=PASS")
        if stage16r_real.get("strict_microtape_status") != "PASS" and stage16r_remaining == 0:
            problems.append("completed Stage16R-real packet must report strict_microtape_status=PASS")
    elif repair_status == "BLOCKED" or repair.get("replayable_repair_bundle_count") == 0:
        blockers.append("fresh_stage16r_real_evaluator_bundles_required")
    if repair.get("release_next_phase_g") is True:
        problems.append("repair-loop structural check must not release Phase G")
    if repair_status == "PASS" and repair.get("required_next_action") != "rerun_phase_f_evaluator_proof":
        problems.append("repair-loop PASS must route to rerun_phase_f_evaluator_proof")
    if repair.get("phase_f_evaluator_proof_required") is False:
        problems.append("repair-loop must require Phase F evaluator proof")

    manifest_status, manifest_blockers, manifest_problems, manifest_details = audit_full_manifest(full_manifest_root)
    blockers.extend(manifest_blockers)
    problems.extend(manifest_problems)

    if problems:
        status = "FAIL"
    elif blockers:
        status = "BLOCKED"
    else:
        status = "READY"

    if "remaining_stage16r_real_repairs_required" in blockers:
        next_loop = "retry_remaining_stage16r_real_targets"
    elif "fresh_stage16r_real_evaluator_bundles_required" in blockers:
        next_loop = "stage16r_real_evaluator_bundle_loop"
    elif "phase_f_evaluator_proof_pass_required" in blockers:
        next_loop = "rerun_phase_f_evaluator_proof"
    elif "full_dataset_manifest_freeze_required" in blockers:
        next_loop = "phase_g_full_manifest_freeze"
    elif status == "READY":
        next_loop = "start_full_swe_bench_sharded_sealed_campaign"
    else:
        next_loop = "fix_readiness_audit_problems"

    return {
        "schema_id": "FullSweBenchReadinessAudit.v1",
        "status": status,
        "full_swe_bench_ready": status == "READY",
        "release_phase_g": status == "READY",
        "next_loop": next_loop,
        "phase_f": {
            "root": str(phase_f_root),
            "status": phase_f_status,
            "official_evaluator_executable_replay": phase_f_replay,
            "release_next_phase_g": phase_f_release,
        },
        "repair_loop": {
            "root": str(repair_loop_root),
            "status": repair_status,
            "replayable_repair_bundle_count": repair.get("replayable_repair_bundle_count"),
            "release_next_phase_g": repair.get("release_next_phase_g"),
            "phase_f_evaluator_proof_required": repair.get("phase_f_evaluator_proof_required"),
        },
        "stage16r_real": {
            "root": str(stage16r_real_root) if stage16r_real_root is not None else None,
            "status": stage16r_real.get("status"),
            "fresh_real_evaluator_bundle_count": stage16r_real_count,
            "official_pass_count": stage16r_real.get("official_pass_count"),
            "remaining_repair_count": stage16r_remaining,
            "strict_microtape_status": stage16r_real.get("strict_microtape_status"),
        },
        "full_manifest": {
            "root": str(full_manifest_root),
            "status": manifest_status,
            **manifest_details,
        },
        "blockers": sorted(set(blockers)),
        "problems": sorted(set(problems)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase-f-root", required=True)
    parser.add_argument("--repair-loop-root", required=True)
    parser.add_argument("--full-manifest-root", required=True)
    parser.add_argument("--stage16r-real-root")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = audit_full_swe_bench_readiness(
        phase_f_root=Path(args.phase_f_root),
        repair_loop_root=Path(args.repair_loop_root),
        full_manifest_root=Path(args.full_manifest_root),
        stage16r_real_root=Path(args.stage16r_real_root) if args.stage16r_real_root else None,
    )
    write_json(Path(args.out), report)
    return 0 if report["status"] in {"READY", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

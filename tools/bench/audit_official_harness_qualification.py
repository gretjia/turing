#!/usr/bin/env python3
"""Audit upstream SWE-bench Docker harness qualification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
from pathlib import Path
from typing import Any


FORBIDDEN_CANDIDATE_SOURCES = {
    "dataset_gold_patch",
    "dataset_patch",
    "official_solution_patch",
    "gold_patch",
    "test_patch_as_candidate",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def rel(root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def command_is_upstream(command: Any) -> bool:
    if not isinstance(command, str):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return "-m" in parts and "swebench.harness.run_evaluation" in parts


def check_existing_path(root: Path, data: dict[str, Any], key: str, problems: list[str]) -> None:
    value = data.get(key)
    if not isinstance(value, str):
        problems.append(f"{key} missing")
        return
    path = rel(root, value)
    if not path.exists():
        problems.append(f"{key} does not exist: {value}")


def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def audit_phase_f_results(
    root: Path,
    data: dict[str, Any],
    problems: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    expected = as_int(data.get("phase_f_expected_task_count"))
    summary = {
        "phase_f_expected_task_count": expected,
        "phase_f_submitted_count": None,
        "phase_f_completed_count": None,
        "phase_f_resolved_count": None,
        "phase_f_unresolved_count": None,
        "phase_f_unresolved_ids": [],
        "phase_f_error_count": None,
        "phase_f_error_ids": [],
    }
    value = data.get("evaluation_results_path")
    if expected is None or not isinstance(value, str):
        return summary
    path = rel(root, value)
    if not path.exists():
        return summary
    try:
        result = load_json(path)
    except (json.JSONDecodeError, ValueError) as exc:
        problems.append(f"evaluation_results_path is not readable JSON: {exc}")
        blockers.append("phase_f_evaluation_results_unreadable")
        return summary

    submitted = as_int(result.get("submitted_instances"))
    completed = as_int(result.get("completed_instances"))
    resolved = as_int(result.get("resolved_instances"))
    unresolved = as_int(result.get("unresolved_instances"))
    errors = as_int(result.get("error_instances"))
    unresolved_ids = as_str_list(result.get("unresolved_ids"))
    error_ids = as_str_list(result.get("error_ids"))

    summary.update(
        {
            "phase_f_submitted_count": submitted,
            "phase_f_completed_count": completed,
            "phase_f_resolved_count": resolved,
            "phase_f_unresolved_count": unresolved,
            "phase_f_unresolved_ids": unresolved_ids,
            "phase_f_error_count": errors,
            "phase_f_error_ids": error_ids,
        }
    )

    if submitted != expected:
        problems.append(f"Phase F official replay submitted count mismatch: expected {expected}, got {submitted}")
        blockers.append("phase_f_submitted_count")
    if completed != expected:
        problems.append(f"Phase F official replay completed count mismatch: expected {expected}, got {completed}")
        blockers.append("phase_f_completed_count")
    if errors not in {0, None} or error_ids:
        listed = ", ".join(error_ids) if error_ids else str(errors)
        problems.append(f"Phase F official replay error ids: {listed}")
        blockers.append("phase_f_errors")
    if data.get("phase_f_requires_all_resolved") is True:
        if unresolved_ids or unresolved not in {0, None} or resolved != expected:
            listed = ", ".join(unresolved_ids) if unresolved_ids else str(unresolved)
            problems.append(f"Phase F official replay unresolved ids: {listed}")
            blockers.append("phase_f_unresolved")

    return summary


def audit_predictions(root: Path, data: dict[str, Any], problems: list[str]) -> int:
    value = data.get("predictions_path")
    if not isinstance(value, str):
        problems.append("predictions_path missing")
        return 0
    path = rel(root, value)
    if not path.exists():
        problems.append(f"predictions_path does not exist: {value}")
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        count += 1
        row = json.loads(line)
        instance_id = row.get("instance_id", "<unknown>")
        if row.get("candidate_source") in FORBIDDEN_CANDIDATE_SOURCES:
            problems.append(f"prediction uses forbidden candidate source: {instance_id}")
        if not isinstance(row.get("model_patch"), str):
            problems.append(f"prediction missing model_patch: {instance_id}")
    return count


def audit_qualification(root: Path) -> dict[str, Any]:
    data = load_json(root / "official_harness_qualification.json")
    claim = load_json(root / "CLAIM_BOUNDARY.json") if (root / "CLAIM_BOUNDARY.json").exists() else {}
    problems: list[str] = []
    blockers: list[str] = []

    if data.get("official_harness_kind") != "upstream_swebench_docker":
        problems.append("official_harness_kind must be upstream_swebench_docker")
    if not command_is_upstream(data.get("command")):
        problems.append("command must invoke python -m swebench.harness.run_evaluation")
    if data.get("repo_local_evaluator_marked_official") is not False:
        problems.append("repo-local evaluator cannot be marked official")
    if data.get("dataset_name") not in {"princeton-nlp/SWE-bench_Verified", "SWE-bench/SWE-bench_Verified"}:
        problems.append("dataset_name must be SWE-bench Verified")
    blocking_keys = {
        "docker_environment_used",
        "swebench_package_present",
        "evaluation_results_present",
        "stdout_stderr_digests_present",
        "docker_build_or_cache_logs_present",
    }
    for key in [
        "docker_environment_used",
        "swebench_package_present",
        "evaluation_results_present",
        "stdout_stderr_digests_present",
        "docker_build_or_cache_logs_present",
        "fail_to_pass_checked",
        "pass_to_pass_checked",
    ]:
        if data.get(key) is not True:
            problems.append(f"{key} must be true")
            if key in blocking_keys:
                blockers.append(key)
    for key in [
        "predictions_path",
        "evaluation_results_path",
        "stdout_path",
        "stderr_path",
        "docker_build_or_cache_log_path",
    ]:
        check_existing_path(root, data, key, problems)
    prediction_count = audit_predictions(root, data, problems)
    phase_f_summary = audit_phase_f_results(root, data, problems, blockers)
    if claim.get("full_swe_bench_score_claim_allowed") is not False:
        problems.append("full SWE-bench score claim must remain forbidden")
    if claim.get("leaderboard_equivalence_claim_allowed") is not False:
        problems.append("leaderboard equivalence claim must remain forbidden")
    if claim.get("repo_local_evaluator_official_claim_allowed") is not False:
        problems.append("repo-local evaluator official claim must remain forbidden")

    if blockers:
        status = "BLOCKED"
    elif problems:
        status = "FAIL"
    else:
        status = "PASS"
    if status == "PASS":
        required_next_action = "regenerate_full_readiness_audit_with_official_harness_identity"
    elif "phase_f_unresolved" in blockers:
        required_next_action = "repair_unresolved_official_phase_f_target"
    else:
        required_next_action = "produce_upstream_swebench_docker_run_evaluation_evidence"
    report = {
        "schema_id": "turingos.official_swebench_harness_qualification_audit.v1",
        "status": status,
        "problems": problems,
        "blockers": sorted(set(blockers)),
        "official_harness_kind": data.get("official_harness_kind"),
        "prediction_count": prediction_count,
        "release_next_phase_g": status == "PASS" and data.get("release_next_phase_g") is True,
        "required_next_action": required_next_action,
    }
    report.update(phase_f_summary)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit_qualification(args.root)
    write_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

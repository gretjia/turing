#!/usr/bin/env python3
"""Audit Stage11 loop-until-PASS evidence from Micro Tape bundles."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"


def load_micro_tape_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("audit_micro_tape_decision_dag", MICRO_TAPE_AUDITOR)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {MICRO_TAPE_AUDITOR}")
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def payload(event: dict[str, Any] | None) -> dict[str, Any]:
    if event is None or not isinstance(event.get("payload"), dict):
        return {}
    return event["payload"]


def event_index(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {event["_event_id"]: event for event in events}


def seq(event: dict[str, Any] | None) -> int | None:
    if event is None:
        return None
    value = event.get("sequence")
    return value if isinstance(value, int) else None


def event_by_id(events_by_id: dict[str, dict[str, Any]], event_id: Any, expected_type: str, problems: list[str], key: str) -> dict[str, Any] | None:
    if not isinstance(event_id, str) or not event_id:
        problems.append(f"{key} missing")
        return None
    event = events_by_id.get(event_id)
    if event is None:
        problems.append(f"{key} does not resolve in Micro Tape: {event_id}")
        return None
    if event.get("event_type") != expected_type:
        problems.append(f"{key} expected {expected_type}, got {event.get('event_type')}")
    return event


def final_pput_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event_type") == "PPUTAccounted" and payload(event).get("accounting_stage") == "final"
    ]


def pput_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event.get("event_type") == "PPUTAccounted"]


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    loop = run.get("loop_until_pass")
    if not isinstance(loop, dict):
        loop = {}
        problems.append("loop_until_pass missing")

    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {"status": "FAIL", "instance_id": run.get("instance_id"), "problems": problems + ["micro_tape_bundle missing"]}

    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"run_{index}")
    events = auditor.read_event_chain(git_dir)
    by_id = event_index(events)

    for key in ["human_intervention_count", "manual_patch_count", "manual_approval_count", "manual_rerun_selection_count"]:
        if loop.get(key) != 0:
            problems.append(f"{key} must be 0")
    if loop.get("fallback_to_auto_authorization") is not False:
        problems.append("fallback_to_auto_authorization must be false")
    if loop.get("verified_from_micro_tape_bundle_only") is not True:
        problems.append("verified_from_micro_tape_bundle_only must be true")
    if loop.get("retry_decision_source") not in {"tape_reducer_or_policy", "tape_policy"}:
        problems.append("retry_decision_source must be tape_reducer_or_policy")

    first_failure = event_by_id(by_id, loop.get("first_failure_event_id"), "FailureNode", problems, "first_failure_event_id")
    certificate = event_by_id(
        by_id, loop.get("failure_certificate_event_id"), "FailureCertificate", problems, "failure_certificate_event_id"
    )
    broadcast = event_by_id(
        by_id,
        loop.get("broadcast_rule_activated_event_id"),
        "BroadcastRuleActivated",
        problems,
        "broadcast_rule_activated_event_id",
    )
    retry = event_by_id(by_id, loop.get("retry_policy_event_id"), "RetryAuthorized", problems, "retry_policy_event_id")
    second_capsule = event_by_id(
        by_id, loop.get("second_attempt_capsule_event_id"), "WorkCapsuleBuilt", problems, "second_attempt_capsule_event_id"
    )
    terminal_accept = event_by_id(
        by_id,
        loop.get("terminal_candidate_accepted_event_id"),
        "CandidateAccepted",
        problems,
        "terminal_candidate_accepted_event_id",
    )
    accepted_head = event_by_id(by_id, loop.get("accepted_head"), "CandidateAccepted", problems, "accepted_head")

    if loop.get("accepted_head") != loop.get("terminal_candidate_accepted_event_id"):
        problems.append("accepted_head must equal terminal_candidate_accepted_event_id")

    ordered = [seq(first_failure), seq(certificate), seq(broadcast), seq(retry), seq(second_capsule), seq(terminal_accept)]
    if any(value is None for value in ordered):
        problems.append("required loop event sequence is incomplete")
    elif ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
        problems.append("loop event order must be failure < certificate < broadcast < retry < second capsule < accept")

    if loop.get("attempts_total", 0) < 2:
        problems.append("attempts_total must be >= 2")
    if loop.get("failed_attempts_before_accept", 0) < 1:
        problems.append("failed_attempts_before_accept must be >= 1")
    if not isinstance(loop.get("accepted_attempt_index"), int) or not isinstance(loop.get("first_failed_attempt_index"), int):
        problems.append("attempt indexes missing")
    elif loop["accepted_attempt_index"] <= loop["first_failed_attempt_index"]:
        problems.append("accepted_attempt_index must be greater than first_failed_attempt_index")

    if loop.get("budget_exhausted") is True:
        problems.append("budget exhausted before CandidateAccepted")

    fail_official = [
        event
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported" and payload(event).get("result") == "FAIL"
    ]
    pass_official = [
        event
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported" and payload(event).get("result") == "PASS"
    ]
    if not fail_official:
        problems.append("no failed official evaluator evidence before accept")
    if not pass_official:
        problems.append("no passing official evaluator evidence before accept")
    if pass_official and terminal_accept and seq(pass_official[-1]) is not None and seq(terminal_accept) is not None:
        if seq(pass_official[-1]) > seq(terminal_accept):
            problems.append("official PASS must precede CandidateAccepted")

    pputs = pput_events(events)
    failed_progress_zero = any(
        payload(event).get("progress") == 0
        for event in pputs
        if seq(event)
        and first_failure
        and terminal_accept
        and seq(first_failure)
        and seq(terminal_accept)
        and seq(first_failure) < seq(event) < seq(terminal_accept)
    )
    terminal_progress_one = any(
        payload(event).get("progress") == 1
        and terminal_accept
        and payload(event).get("terminal_event_id") == terminal_accept["_event_id"]
        and seq(event)
        and seq(terminal_accept)
        and seq(event) > seq(terminal_accept)
        for event in pputs
    )
    if not failed_progress_zero:
        problems.append("failed attempt final/progress PPUT must have progress 0")
    if not terminal_progress_one:
        problems.append("terminal accepted attempt must have final PPUT progress 1")

    cost_total = sum(
        int(payload(event).get("total_tokens", 0))
        for event in events
        if event.get("event_type") == "CostEvent" and isinstance(payload(event).get("total_tokens"), int)
    )
    final_pput = next(
        (event for event in pputs if payload(event).get("accounting_stage") == "final" and payload(event).get("progress") == 1),
        None,
    )
    all_attempt_costs_counted = final_pput is not None and payload(final_pput).get("total_run_token_count") == cost_total
    if not all_attempt_costs_counted:
        problems.append("final PPUT total_run_token_count must equal sum of CostEvent total_tokens")

    if any(event.get("event_type") == "HumanSteerAuthorized" for event in events):
        problems.append("HumanSteerAuthorized event present")

    return {
        "status": "FAIL" if problems else "PASS",
        "instance_id": run.get("instance_id"),
        "problems": problems,
        "event_count": len(events),
        "attempts_total": loop.get("attempts_total"),
        "failed_attempts_before_accept": loop.get("failed_attempts_before_accept"),
        "first_failed_attempt_index": loop.get("first_failed_attempt_index"),
        "accepted_attempt_index": loop.get("accepted_attempt_index"),
        "human_intervention_count": loop.get("human_intervention_count"),
        "manual_patch_count": loop.get("manual_patch_count"),
        "manual_approval_count": loop.get("manual_approval_count"),
        "manual_rerun_selection_count": loop.get("manual_rerun_selection_count"),
        "fallback_to_auto_authorization": loop.get("fallback_to_auto_authorization"),
        "retry_decision_source": loop.get("retry_decision_source"),
        "retry_policy_event_id": loop.get("retry_policy_event_id"),
        "first_failure_event_id": loop.get("first_failure_event_id"),
        "failure_certificate_event_id": loop.get("failure_certificate_event_id"),
        "broadcast_rule_activated_event_id": loop.get("broadcast_rule_activated_event_id"),
        "second_attempt_capsule_event_id": loop.get("second_attempt_capsule_event_id"),
        "terminal_candidate_accepted_event_id": loop.get("terminal_candidate_accepted_event_id"),
        "accepted_head": loop.get("accepted_head"),
        "verified_from_micro_tape_bundle_only": loop.get("verified_from_micro_tape_bundle_only"),
        "failed_attempt_progress_zero": failed_progress_zero,
        "terminal_progress_one": terminal_progress_one,
        "all_attempt_costs_counted": all_attempt_costs_counted,
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    with tempfile.TemporaryDirectory(prefix="turingos-stage11-loop-audit-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), idx) for idx, run in enumerate(runs) if isinstance(run, dict)]

    problems = [problem for report in run_reports for problem in report.get("problems", [])]
    status = "PASS" if run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    first = run_reports[0] if run_reports else {}
    return {
        "schema_id": "Stage11LoopUntilPassAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundle_plus_coverage_refs",
        "run_count": len(run_reports),
        "problems": problems,
        "attempts_total": first.get("attempts_total"),
        "failed_attempts_before_accept": first.get("failed_attempts_before_accept"),
        "first_failed_attempt_index": first.get("first_failed_attempt_index"),
        "accepted_attempt_index": first.get("accepted_attempt_index"),
        "human_intervention_count": first.get("human_intervention_count"),
        "manual_patch_count": first.get("manual_patch_count"),
        "manual_approval_count": first.get("manual_approval_count"),
        "manual_rerun_selection_count": first.get("manual_rerun_selection_count"),
        "fallback_to_auto_authorization": first.get("fallback_to_auto_authorization"),
        "retry_decision_source": first.get("retry_decision_source"),
        "retry_policy_event_id": first.get("retry_policy_event_id"),
        "first_failure_event_id": first.get("first_failure_event_id"),
        "failure_certificate_event_id": first.get("failure_certificate_event_id"),
        "broadcast_rule_activated_event_id": first.get("broadcast_rule_activated_event_id"),
        "second_attempt_capsule_event_id": first.get("second_attempt_capsule_event_id"),
        "terminal_candidate_accepted_event_id": first.get("terminal_candidate_accepted_event_id"),
        "accepted_head": first.get("accepted_head"),
        "verified_from_micro_tape_bundle_only": first.get("verified_from_micro_tape_bundle_only"),
        "failed_attempt_progress_zero": all(report.get("failed_attempt_progress_zero") is True for report in run_reports),
        "terminal_progress_one": all(report.get("terminal_progress_one") is True for report in run_reports),
        "all_attempt_costs_counted": all(report.get("all_attempt_costs_counted") is True for report in run_reports),
        "runs": run_reports,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = audit_coverage(Path(args.coverage))
    write_json(Path(args.out), report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

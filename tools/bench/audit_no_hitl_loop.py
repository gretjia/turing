#!/usr/bin/env python3
"""Audit a Stage8 no-HITL retry loop from Micro Tape-backed coverage."""

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


def event_index(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {event["_event_id"]: event for event in events}


def event_type(events: dict[str, dict[str, Any]], event_id: str | None) -> str | None:
    if not event_id:
        return None
    event = events.get(event_id)
    if event is None:
        return None
    return str(event.get("event_type"))


def sequence(events: dict[str, dict[str, Any]], event_id: str | None) -> int | None:
    if not event_id or event_id not in events:
        return None
    value = events[event_id].get("sequence")
    return value if isinstance(value, int) else None


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    missing: list[str] = []
    problems: list[str] = []
    loop = run.get("no_hitl_loop")
    if not isinstance(loop, dict):
        loop = {}
        missing.append("no_hitl_loop")

    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {
            "status": "FAIL",
            "instance_id": run.get("instance_id"),
            "missing": missing + ["micro_tape_bundle"],
            "problems": problems,
        }

    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"run_{index}")
    events = auditor.read_event_chain(git_dir)
    events_by_id = event_index(events)

    required_zero = [
        "human_intervention_count",
        "manual_patch_count",
        "manual_approval_count",
        "manual_rerun_selection_count",
    ]
    for key in required_zero:
        if loop.get(key) != 0:
            problems.append(f"{key} must be 0")

    if loop.get("fallback_to_auto_authorization") is not False:
        problems.append("fallback_to_auto_authorization must be false")
    if loop.get("verified_from_micro_tape_bundle_only") is not True:
        problems.append("verified_from_micro_tape_bundle_only must be true")

    required_ids = {
        "retry_policy_event_id": "RetryAuthorized",
        "first_failure_event_id": "FailureNode",
        "broadcast_rule_event_id": "BroadcastRuleActivated",
        "second_attempt_capsule_event_id": "WorkCapsuleBuilt",
        "terminal_candidate_accepted_event_id": "CandidateAccepted",
        "accepted_head": "CandidateAccepted",
    }
    for key, expected_type in required_ids.items():
        value = loop.get(key)
        if not isinstance(value, str) or not value:
            missing.append(key)
            continue
        got_type = event_type(events_by_id, value)
        if got_type is None:
            problems.append(f"{key} does not resolve in Micro Tape: {value}")
        elif got_type != expected_type:
            problems.append(f"{key} expected {expected_type}, got {got_type}")

    accepted_head = loop.get("accepted_head")
    terminal_accept = loop.get("terminal_candidate_accepted_event_id")
    if accepted_head != terminal_accept:
        problems.append("accepted_head must equal terminal_candidate_accepted_event_id")

    order_keys = [
        "first_failure_event_id",
        "broadcast_rule_event_id",
        "retry_policy_event_id",
        "second_attempt_capsule_event_id",
        "terminal_candidate_accepted_event_id",
    ]
    ordered = [sequence(events_by_id, loop.get(key)) for key in order_keys]
    if any(value is None for value in ordered):
        problems.append("required loop event sequence is incomplete")
    elif ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
        problems.append("loop event order must be failure < broadcast < retry < second capsule < accept")

    if loop.get("retry_decision_source") not in {"tape_reducer_or_policy", "tape_policy"}:
        problems.append("retry_decision_source must be tape_reducer_or_policy")

    if any(event.get("event_type") == "HumanSteerAuthorized" for event in events):
        problems.append("HumanSteerAuthorized event present in no-HITL tape")

    return {
        "status": "FAIL" if missing or problems else "PASS",
        "instance_id": run.get("instance_id"),
        "missing": missing,
        "problems": problems,
        "event_count": len(events),
        "human_intervention_count": loop.get("human_intervention_count"),
        "manual_patch_count": loop.get("manual_patch_count"),
        "manual_approval_count": loop.get("manual_approval_count"),
        "manual_rerun_selection_count": loop.get("manual_rerun_selection_count"),
        "fallback_to_auto_authorization": loop.get("fallback_to_auto_authorization"),
        "verified_from_micro_tape_bundle_only": loop.get("verified_from_micro_tape_bundle_only"),
        "retry_decision_source": loop.get("retry_decision_source"),
        "retry_policy_event_id": loop.get("retry_policy_event_id"),
        "first_failure_event_id": loop.get("first_failure_event_id"),
        "broadcast_rule_event_id": loop.get("broadcast_rule_event_id"),
        "second_attempt_capsule_event_id": loop.get("second_attempt_capsule_event_id"),
        "terminal_candidate_accepted_event_id": loop.get("terminal_candidate_accepted_event_id"),
        "accepted_head": loop.get("accepted_head"),
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    with tempfile.TemporaryDirectory(prefix="turingos-no-hitl-audit-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), idx) for idx, run in enumerate(runs) if isinstance(run, dict)]

    missing = sorted({item for report in run_reports for item in report.get("missing", [])})
    problems = [item for report in run_reports for item in report.get("problems", [])]
    status = "PASS" if run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    first = run_reports[0] if run_reports else {}
    return {
        "schema_id": "NoHitlLoopAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundle_plus_coverage_refs",
        "run_count": len(run_reports),
        "missing": missing,
        "problems": problems,
        "human_intervention_count": first.get("human_intervention_count"),
        "manual_patch_count": first.get("manual_patch_count"),
        "manual_approval_count": first.get("manual_approval_count"),
        "manual_rerun_selection_count": first.get("manual_rerun_selection_count"),
        "fallback_to_auto_authorization": first.get("fallback_to_auto_authorization"),
        "verified_from_micro_tape_bundle_only": first.get("verified_from_micro_tape_bundle_only"),
        "retry_decision_source": first.get("retry_decision_source"),
        "retry_policy_event_id": first.get("retry_policy_event_id"),
        "first_failure_event_id": first.get("first_failure_event_id"),
        "broadcast_rule_event_id": first.get("broadcast_rule_event_id"),
        "second_attempt_capsule_event_id": first.get("second_attempt_capsule_event_id"),
        "terminal_candidate_accepted_event_id": first.get("terminal_candidate_accepted_event_id"),
        "accepted_head": first.get("accepted_head"),
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

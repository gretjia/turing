#!/usr/bin/env python3
"""Audit Stage12 20-task loop-until-PASS release evidence.

This is a release-scope auditor, not a solver. It checks that a Stage12 result
has exactly the frozen 20 runs, strict MicroTape replay PASS, no fixture
overclaim, no manual intervention, and per-run solved/unsolved VPPUT semantics.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"

STRICT_REQUIRED_PASS = [
    "overall",
    "replay_structural_integrity",
    "bundle_accessibility",
    "basic_ref_reconstruction",
    "git_topology",
    "canonical_payload_hash",
    "registry_head_effect",
    "accepted_head_authority",
    "authorization_head",
    "terminal_golden_path_anchors_to_accepted_head",
    "failed_progress_zero",
    "accepted_final_progress_one",
    "cost_conservation_all_branches",
    "vpput_accounting",
    "economic_timing",
    "market_accounting_correctness",
    "constitutional_protocol_audit",
]
ALLOWED_SCIENTIFIC_STATUS = "STAGE12_20TASK_SCALE_PROTOCOL_EVIDENCE_NOT_STATISTICAL_CLAIM"
FORBIDDEN_BUNDLE_PAYLOAD_MARKERS = {
    "fixture",
    "stage11",
    "deterministic_official_fixture",
    "swe_bench_shaped_loop_until_pass_fixture",
}


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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def payload(event: dict[str, Any] | None) -> dict[str, Any]:
    if event is None or not isinstance(event.get("payload"), dict):
        return {}
    return event["payload"]


def seq(event: dict[str, Any] | None) -> int | None:
    if event is None:
        return None
    value = event.get("sequence")
    return value if isinstance(value, int) else None


def event_index(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {event["_event_id"]: event for event in events}


def has_fixture_marker(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return "fixture" in lowered or lowered.startswith("stage11_")
    if isinstance(value, list):
        return any(has_fixture_marker(item) for item in value)
    if isinstance(value, dict):
        return any(has_fixture_marker(item) for item in value.values())
    return False


def strict_problems(strict_summary: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for key in STRICT_REQUIRED_PASS:
        if strict_summary.get(key) != "PASS":
            problems.append(f"strict audit {key} must be PASS")
    return problems


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(strings(item))
        return out
    return []


def forbidden_payload_markers(events: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for event in events:
        text = "\n".join(strings(payload(event))).lower()
        for marker in FORBIDDEN_BUNDLE_PAYLOAD_MARKERS:
            if marker in text:
                found.add(marker)
    return sorted(found)


def bundle_hashes_from_strict(strict_report: dict[str, Any]) -> list[str] | None:
    runs = strict_report.get("runs")
    if not isinstance(runs, list):
        return None
    hashes = []
    for run in runs:
        if not isinstance(run, dict) or not isinstance(run.get("bundle_hash"), str):
            return None
        hashes.append(run["bundle_hash"])
    return hashes


def final_pput_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event_type") == "PPUTAccounted" and payload(event).get("accounting_stage") == "final"
    ]


def cost_total(events: list[dict[str, Any]]) -> int:
    total = 0
    for event in events:
        if event.get("event_type") != "CostEvent":
            continue
        value = payload(event).get("total_tokens")
        if isinstance(value, int) and value > 0:
            total += value
    return total


def event_by_id(events_by_id: dict[str, dict[str, Any]], event_id: Any, expected_type: str) -> dict[str, Any] | None:
    if not isinstance(event_id, str):
        return None
    event = events_by_id.get(event_id)
    if event is None or event.get("event_type") != expected_type:
        return None
    return event


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    loop = run.get("loop_until_pass")
    if not isinstance(loop, dict):
        loop = {}
        problems.append("loop_until_pass missing")
    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {
            "status": "FAIL",
            "instance_id": run.get("instance_id"),
            "problems": problems + ["micro_tape_bundle missing"],
        }

    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"stage12_run_{index}")
    events = auditor.read_event_chain(git_dir)
    by_id = event_index(events)
    markers = forbidden_payload_markers(events)
    if markers:
        problems.append("bundle payload contains fixture markers: " + ", ".join(markers))
    official_failures = [
        event
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported" and payload(event).get("result") == "FAIL"
    ]
    official_passes = [
        event
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported" and payload(event).get("result") == "PASS"
    ]
    candidate_accepts = [event for event in events if event.get("event_type") == "CandidateAccepted"]
    terminal_accept = event_by_id(
        by_id, loop.get("terminal_candidate_accepted_event_id"), "CandidateAccepted"
    )
    accepted_head = event_by_id(by_id, loop.get("accepted_head"), "CandidateAccepted")
    solved = terminal_accept is not None and accepted_head is not None
    if terminal_accept is not None and accepted_head is not None and terminal_accept["_event_id"] != accepted_head["_event_id"]:
        problems.append("accepted_head must equal terminal_candidate_accepted_event_id")

    for key in ["human_intervention_count", "manual_patch_count", "manual_approval_count", "manual_rerun_selection_count"]:
        if loop.get(key) != 0:
            problems.append(f"{key} must be 0")
    if loop.get("fallback_to_auto_authorization") is not False:
        problems.append("fallback_to_auto_authorization must be false")
    if loop.get("verified_from_micro_tape_bundle_only") is not True:
        problems.append("verified_from_micro_tape_bundle_only must be true")
    if run.get("authorization_mode") != "required":
        problems.append("authorization_mode must be required")
    if not isinstance(run.get("authorization_head"), str) or not str(run.get("authorization_head")).startswith("mu:"):
        problems.append("authorization_head must be present")
    if run.get("basis") and has_fixture_marker(run.get("basis")):
        problems.append("fixture run basis cannot release Stage12")

    if loop.get("attempts_total", 0) < 2:
        problems.append("attempts_total must be >= 2")
    if loop.get("failed_attempts_before_accept", 0) < 1:
        problems.append("failed_attempts_before_accept must be >= 1")
    if not official_failures:
        problems.append("at least one official FAIL must precede terminal state")

    pputs = final_pput_events(events)
    final_progress_one = False
    terminal_progress_zero = False
    all_attempt_costs_counted = False
    if solved:
        if loop.get("budget_exhausted") is True:
            problems.append("solved run cannot be budget_exhausted")
        if not official_passes:
            problems.append("solved run requires official PASS evidence")
        if official_passes and seq(official_passes[-1]) is not None and seq(terminal_accept) is not None:
            if seq(official_passes[-1]) > seq(terminal_accept):
                problems.append("official PASS must precede CandidateAccepted")
        if loop.get("accepted_attempt_index", 0) <= loop.get("first_failed_attempt_index", 0):
            problems.append("accepted attempt must be after first failed attempt")
        final_progress_one = any(
            payload(event).get("progress") == 1
            and payload(event).get("terminal_event_id") == terminal_accept["_event_id"]
            and seq(event) is not None
            and seq(terminal_accept) is not None
            and seq(event) > seq(terminal_accept)
            for event in pputs
        )
        if not final_progress_one:
            problems.append("solved run must append final PPUT progress 1 after CandidateAccepted")
        counted = cost_total(events)
        all_attempt_costs_counted = any(
            payload(event).get("progress") == 1 and payload(event).get("total_run_token_count") == counted
            for event in pputs
        )
        if not all_attempt_costs_counted:
            problems.append("solved run final PPUT must count all CostEvent tokens")
    else:
        if candidate_accepts:
            problems.append("unsolved run must not contain CandidateAccepted")
        if loop.get("budget_exhausted") is not True:
            problems.append("unsolved run must be marked budget_exhausted")
        terminal_progress_zero = any(payload(event).get("progress") == 0 for event in pputs)
        if not terminal_progress_zero:
            problems.append("unsolved run must append terminal final PPUT progress 0")
        final_progress_one = False
        all_attempt_costs_counted = True

    return {
        "status": "FAIL" if problems else "PASS",
        "instance_id": run.get("instance_id"),
        "problems": problems,
        "event_count": len(events),
        "forbidden_payload_markers": markers,
        "solved": solved,
        "budget_exhausted": loop.get("budget_exhausted") is True,
        "attempts_total": loop.get("attempts_total"),
        "failed_attempts_before_accept": loop.get("failed_attempts_before_accept"),
        "accepted_attempt_index": loop.get("accepted_attempt_index"),
        "first_failed_attempt_index": loop.get("first_failed_attempt_index"),
        "terminal_progress_one": final_progress_one,
        "terminal_progress_zero": terminal_progress_zero,
        "all_attempt_costs_counted": all_attempt_costs_counted,
    }


def audit_stage12(*, root: Path, coverage_path: Path, strict_audit_path: Path) -> dict[str, Any]:
    problems: list[str] = []
    manifest = load_json(root / "task_manifest.json")
    coverage = load_json(coverage_path)
    supplied_strict = load_json(strict_audit_path)
    supplied_strict_summary = supplied_strict.get("status_summary", supplied_strict)
    if not isinstance(supplied_strict_summary, dict):
        supplied_strict_summary = {}
    problems.extend(strict_problems(supplied_strict_summary))

    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
        problems.append("turingos_arm_runs missing")
    expected_ids = manifest.get("instance_ids")
    if not isinstance(expected_ids, list):
        expected_ids = []
        problems.append("task_manifest.instance_ids missing")
    run_ids = [run.get("instance_id") for run in runs if isinstance(run, dict)]
    if len(runs) != 20:
        problems.append("Stage12 requires exactly 20 runs")
    if coverage.get("sample_size") != 20:
        problems.append("coverage sample_size must be 20")
    if manifest.get("task_count") != 20:
        problems.append("task_manifest task_count must be 20")
    if run_ids != expected_ids:
        problems.append("run instance order must match frozen task_manifest.instance_ids")
    scientific_status = str(coverage.get("scientific_status") or "")
    if "FIXTURE" in scientific_status.upper():
        problems.append("fixture coverage cannot release Stage12")
    if scientific_status != ALLOWED_SCIENTIFIC_STATUS:
        problems.append(f"scientific_status must be {ALLOWED_SCIENTIFIC_STATUS}")

    auditor = load_micro_tape_auditor()
    bundles = [Path(run.get("micro_tape_bundle")) for run in runs if isinstance(run, dict) and isinstance(run.get("micro_tape_bundle"), str)]
    with tempfile.TemporaryDirectory(prefix="turingos-stage12-strict-recompute-") as temp:
        recomputed_strict = auditor.audit_bundles(
            bundles,
            Path(temp),
            strict_vpput=True,
            strict_terminal_market=True,
            require_authorization_head=True,
        )
    recomputed_summary = recomputed_strict.get("status_summary", {})
    if not isinstance(recomputed_summary, dict):
        recomputed_summary = {}
    for problem in strict_problems(recomputed_summary):
        problems.append("recomputed " + problem)
    supplied_hashes = bundle_hashes_from_strict(supplied_strict)
    recomputed_hashes = bundle_hashes_from_strict(recomputed_strict)
    if supplied_hashes is None:
        problems.append("supplied strict audit must include per-run bundle_hash values")
    elif supplied_hashes != recomputed_hashes:
        problems.append("supplied strict audit bundle_hashes do not match coverage bundles")
    supplied_count = supplied_strict.get("aggregate", {}).get("bundle_count") if isinstance(supplied_strict.get("aggregate"), dict) else None
    if supplied_count != len(bundles):
        problems.append("supplied strict audit aggregate.bundle_count must match coverage bundle count")
    for key in STRICT_REQUIRED_PASS:
        if supplied_strict_summary.get(key) != recomputed_summary.get(key):
            problems.append(f"supplied strict audit {key} does not match recomputed strict audit")

    with tempfile.TemporaryDirectory(prefix="turingos-stage12-release-audit-") as temp:
        run_reports = [
            audit_run(run, auditor, Path(temp), idx)
            for idx, run in enumerate(runs)
            if isinstance(run, dict)
        ]
    problems.extend(problem for report in run_reports for problem in report.get("problems", []))
    solved_count = sum(1 for report in run_reports if report.get("solved") is True)
    unsolved_count = sum(1 for report in run_reports if report.get("solved") is not True)
    status = "PASS" if not problems and run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    return {
        "schema_id": "Stage12ReleaseAudit.v1",
        "status": status,
        "local_release_candidate": status == "PASS",
        "external_exact_sha_audit_required": True,
        "truth_source": "micro_tape_bundles_plus_stage12_manifest_and_strict_audit",
        "run_count": len(run_reports),
        "solved_count": solved_count,
        "unsolved_count": unsolved_count,
        "problems": problems,
        "strict_status_summary": recomputed_summary,
        "supplied_strict_status_summary": supplied_strict_summary,
        "runs": run_reports,
        "claim_boundary": "Stage12 scale/protocol evidence only; no statistical superiority or full-score claim.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--strict-audit", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = audit_stage12(root=Path(args.root), coverage_path=Path(args.coverage), strict_audit_path=Path(args.strict_audit))
    write_json(Path(args.out), report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit Stage10 SWE-bench failure taxonomy fixtures from Micro Tape."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
EXPECTED_CLASSES = {
    "INSTALL_FAIL",
    "TEST_TIMEOUT",
    "WRONG_FILE",
    "NO_REPRO",
    "OVERBROAD_PATCH",
    "SEMANTIC_FAIL",
    "FLAKY_ORACLE",
    "DEPENDENCY_GAP",
    "CONTEXT_MISSING",
    "PATCH_APPLIES_BUT_WRONG",
}
FORBIDDEN_BROADCAST_MARKERS = {
    "traceback",
    "stack trace",
    "raw stdout",
    "raw stderr",
    "hidden predicate",
    "hidden_predicate",
    "private_micro_contract",
    "pput formula",
    "vpput formula",
    "heldout",
    "official_solution",
    "gold patch",
    "auth.json",
    "signing_key_hex",
    "private key",
    "sk-",
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


def payload(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("payload")
    return data if isinstance(data, dict) else {}


def candidate_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(candidate_strings(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(candidate_strings(item))
        return result
    return []


def broadcast_candidate_has_forbidden_content(candidate: dict[str, Any]) -> bool:
    text = "\n".join(candidate_strings(candidate)).lower()
    return any(marker in text for marker in FORBIDDEN_BROADCAST_MARKERS)


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {"status": "FAIL", "instance_id": run.get("instance_id"), "problems": ["micro_tape_bundle missing"]}
    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"run_{index}")
    events = auditor.read_event_chain(git_dir)
    by_id = {event["_event_id"]: event for event in events}

    failures = [event for event in events if event.get("event_type") == "FailureNode"]
    certificates = [event for event in events if event.get("event_type") == "FailureCertificate"]
    activated = [event for event in events if event.get("event_type") == "BroadcastRuleActivated"]
    accepts = [event for event in events if event.get("event_type") == "CandidateAccepted"]

    if accepts:
        problems.append("taxonomy fixture must not contain CandidateAccepted")
    if activated:
        problems.append("taxonomy fixture must not activate BroadcastRule")
    if not failures:
        problems.append("FailureNode missing")
    if not certificates:
        problems.append("FailureCertificate missing")

    failure_class = None
    failure_event_id = None
    if failures:
        failure_payload = payload(failures[-1])
        failure_class = failure_payload.get("failure_class")
        failure_event_id = failures[-1]["_event_id"]
        if failure_class not in EXPECTED_CLASSES:
            problems.append(f"unknown failure_class {failure_class!r}")

    candidate_ok = False
    raw_logs_not_broadcast = True
    for certificate in certificates:
        certificate_payload = payload(certificate)
        if certificate_payload.get("source_failure_node_id") not in by_id:
            problems.append("FailureCertificate source_failure_node_id unresolved")
        candidate = certificate_payload.get("broadcast_rule_candidate")
        if isinstance(candidate, dict):
            if candidate.get("candidate_only") is True and candidate.get("activation_event_id") is None:
                candidate_ok = True
            if candidate.get("raw_log_text_absent") is not True:
                raw_logs_not_broadcast = False
            if candidate.get("hidden_predicates_absent") is not True:
                raw_logs_not_broadcast = False
            if broadcast_candidate_has_forbidden_content(candidate):
                raw_logs_not_broadcast = False
        else:
            problems.append("FailureCertificate missing broadcast_rule_candidate")

    pput_progress = [
        payload(event).get("progress")
        for event in events
        if event.get("event_type") == "PPUTAccounted" and payload(event).get("accounting_stage") == "final"
    ]
    if not pput_progress or any(value != 0 for value in pput_progress):
        problems.append("failed taxonomy fixture must have final PPUT progress 0")

    if not candidate_ok:
        problems.append("preserve-only broadcast rule candidate missing")
    if not raw_logs_not_broadcast:
        problems.append("raw logs or hidden predicates exposed in broadcast candidate")

    return {
        "status": "FAIL" if problems else "PASS",
        "instance_id": run.get("instance_id"),
        "failure_class": failure_class,
        "failure_event_id": failure_event_id,
        "problems": problems,
        "has_failure_node": bool(failures),
        "has_broadcast_rule_candidate": candidate_ok,
        "broadcast_candidate_preserve_only": candidate_ok and not activated,
        "raw_logs_not_broadcast": raw_logs_not_broadcast,
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    with tempfile.TemporaryDirectory(prefix="turingos-failure-taxonomy-audit-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), index) for index, run in enumerate(runs) if isinstance(run, dict)]

    classes_seen = sorted({report.get("failure_class") for report in run_reports if isinstance(report.get("failure_class"), str)})
    problems = [problem for report in run_reports for problem in report.get("problems", [])]
    if set(classes_seen) != EXPECTED_CLASSES:
        problems.append("taxonomy coverage incomplete")
    status = "PASS" if run_reports and not problems and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    return {
        "schema_id": "FailureTaxonomyAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundle_plus_coverage_refs",
        "expected_classes": sorted(EXPECTED_CLASSES),
        "classes_seen": classes_seen,
        "run_count": len(run_reports),
        "problems": problems,
        "all_failures_have_failure_node": all(report.get("has_failure_node") is True for report in run_reports),
        "all_failures_have_broadcast_rule_candidate": all(
            report.get("has_broadcast_rule_candidate") is True for report in run_reports
        ),
        "broadcast_candidates_preserve_only": all(
            report.get("broadcast_candidate_preserve_only") is True for report in run_reports
        ),
        "raw_logs_not_broadcast": all(report.get("raw_logs_not_broadcast") is True for report in run_reports),
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

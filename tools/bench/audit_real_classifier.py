#!/usr/bin/env python3
"""Audit Stage11 observer-derived failure classification."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
ALLOWED_CLASSIFIER_INPUTS = {
    "exit_code",
    "timeout_kind",
    "official_evaluator_result",
    "diff_scope",
    "receipt_schema_status",
    "command_result",
    "macro_observation_kind",
    "test_log_digest",
}
FORBIDDEN_CLASSIFIER_INPUTS = {
    "scenario_label",
    "fixture_name",
    "instance_id_label",
    "problem_title",
    "expected_failure_class",
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


def payload(event: dict[str, Any] | None) -> dict[str, Any]:
    if event is None or not isinstance(event.get("payload"), dict):
        return {}
    return event["payload"]


def classify_from_inputs(inputs: dict[str, Any]) -> str | None:
    if inputs.get("diff_scope") == "wrong_file":
        return "WRONG_FILE"
    if inputs.get("timeout_kind") == "context_starved" or inputs.get("receipt_schema_status") == "context_missing":
        return "CONTEXT_MISSING"
    if inputs.get("official_evaluator_result") == "FAIL" and inputs.get("command_result") == "semantic_mismatch":
        return "SEMANTIC_FAIL"
    return None


def validate_classifier_decision(decision: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    inputs = decision.get("classifier_inputs")
    if not isinstance(inputs, dict) or not inputs:
        return ["classifier_inputs missing"]
    for key in inputs:
        if key in FORBIDDEN_CLASSIFIER_INPUTS:
            problems.append(f"forbidden classifier input {key}")
        if key not in ALLOWED_CLASSIFIER_INPUTS:
            problems.append(f"unsupported classifier input {key}")
    if decision.get("observer_derived_failure_class") is not True:
        problems.append("observer_derived_failure_class must be true")
    expected = classify_from_inputs(inputs)
    if expected is None:
        problems.append("classifier_inputs do not imply a known failure class")
    elif decision.get("failure_class") != expected:
        problems.append(f"failure_class {decision.get('failure_class')!r} does not match observer-derived {expected!r}")
    return problems


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {"status": "FAIL", "instance_id": run.get("instance_id"), "problems": ["micro_tape_bundle missing"]}

    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"run_{index}")
    events = auditor.read_event_chain(git_dir)
    failures = [event for event in events if event.get("event_type") == "FailureNode"]
    if not failures:
        problems.append("FailureNode missing")
        decision = {}
    else:
        failure_payload = payload(failures[0])
        decision = failure_payload.get("classifier_decision")
        if not isinstance(decision, dict):
            decision = {}
            problems.append("classifier_decision missing")
        else:
            problems.extend(validate_classifier_decision(decision))

    return {
        "status": "FAIL" if problems else "PASS",
        "instance_id": run.get("instance_id"),
        "problems": problems,
        "failure_class": decision.get("failure_class"),
        "classifier_inputs": decision.get("classifier_inputs"),
        "observer_derived_failure_class": decision.get("observer_derived_failure_class"),
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    with tempfile.TemporaryDirectory(prefix="turingos-stage11-classifier-audit-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), idx) for idx, run in enumerate(runs) if isinstance(run, dict)]

    problems = [problem for report in run_reports for problem in report.get("problems", [])]
    status = "PASS" if run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    return {
        "schema_id": "Stage11RealClassifierAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundle_only",
        "run_count": len(run_reports),
        "problems": problems,
        "classes_seen": sorted({report.get("failure_class") for report in run_reports if isinstance(report.get("failure_class"), str)}),
        "classifier_inputs_allowed_only": sorted(ALLOWED_CLASSIFIER_INPUTS),
        "forbidden_classifier_inputs_absent": sorted(FORBIDDEN_CLASSIFIER_INPUTS),
        "observer_derived_failure_class": all(report.get("observer_derived_failure_class") is True for report in run_reports),
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

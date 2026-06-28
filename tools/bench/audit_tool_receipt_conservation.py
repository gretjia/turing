#!/usr/bin/env python3
"""Audit Native API Worker tool-call receipt and cost conservation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
REQUIRED_NEGATIVE_CONTROLS = {
    "GREP_NO_MATCH",
    "APPLY_PATCH_CONFLICT",
    "RUN_COMMAND_NONZERO",
    "RUN_COMMAND_TIMEOUT",
    "FORBIDDEN_PATH_MUTATION",
}
TOKEN_FIELDS = ["prompt_tokens", "completion_tokens", "tool_tokens", "tool_stdout_tokens"]


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


def payload(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("payload")
    return value if isinstance(value, dict) else {}


def receipt_tokens(receipts: list[dict[str, Any]]) -> dict[str, int]:
    totals = {field: 0 for field in TOKEN_FIELDS}
    for receipt in receipts:
        for field in TOKEN_FIELDS:
            value = receipt.get(field)
            if isinstance(value, int) and value >= 0:
                totals[field] += value
    return totals


def cost_event_tokens(events: list[dict[str, Any]]) -> dict[str, int] | None:
    costs = [payload(event) for event in events if event.get("event_type") == "CostEvent"]
    if not costs:
        return None
    totals = {field: 0 for field in TOKEN_FIELDS}
    for cost in costs:
        for field in TOKEN_FIELDS:
            value = cost.get(field)
            if not isinstance(value, int) or value < 0:
                return None
            totals[field] += value
    return totals


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    native = run.get("native_api_worker")
    if not isinstance(native, dict):
        native = {}
        problems.append("native_api_worker metadata missing")

    attempted = native.get("expected_attempted_actions")
    if not isinstance(attempted, list) or not attempted:
        attempted = []
        problems.append("expected_attempted_actions missing")

    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {
            "status": "FAIL",
            "instance_id": run.get("instance_id"),
            "problems": problems + ["micro_tape_bundle missing"],
        }

    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"stage13_run_{index}")
    events = auditor.read_event_chain(git_dir)
    receipt_events = [event for event in events if event.get("event_type") == "ToolReceiptAppended"]
    receipt_payloads = [payload(event) | {"event_id": event["_event_id"]} for event in receipt_events]
    receipts_by_attempt = {
        receipt.get("attempt_id"): receipt for receipt in receipt_payloads if isinstance(receipt.get("attempt_id"), str)
    }
    receipt_ids = {receipt["event_id"] for receipt in receipt_payloads}

    for action in attempted:
        if not isinstance(action, dict):
            problems.append("expected_attempted_actions entry must be object")
            continue
        attempt_id = action.get("attempt_id")
        tool = action.get("tool")
        if not isinstance(attempt_id, str):
            problems.append("attempted action missing attempt_id")
            continue
        receipt = receipts_by_attempt.get(attempt_id)
        if receipt is None:
            problems.append(f"missing receipt for attempted action {attempt_id}")
            continue
        if receipt.get("tool") != tool:
            problems.append(f"tool mismatch for attempted action {attempt_id}")
        expected_status = action.get("expected_status")
        if isinstance(expected_status, str) and receipt.get("status") != expected_status:
            problems.append(f"status mismatch for attempted action {attempt_id}")
        for field in TOKEN_FIELDS:
            if not isinstance(receipt.get(field), int) or receipt[field] < 0:
                problems.append(f"receipt {attempt_id} missing nonnegative {field}")
        if receipt.get("counted_in_cost") is not True:
            problems.append(f"receipt {attempt_id} missing counted_in_cost true")

    negative_controls_seen = {
        receipt.get("negative_control")
        for receipt in receipt_payloads
        if isinstance(receipt.get("negative_control"), str)
    }

    failed_receipts = [
        receipt
        for receipt in receipt_payloads
        if receipt.get("status") in {"FAILED", "DENIED", "TIMEOUT"}
    ]
    if run.get("expected_result") == "FAIL" and not failed_receipts:
        problems.append("no failed, denied, or timeout tool receipts found")

    worker_payloads = [payload(event) for event in events if event.get("event_type") == "WorkerReceiptImported"]
    if not worker_payloads:
        problems.append("WorkerReceiptImported missing")
    for worker_payload in worker_payloads:
        ids = worker_payload.get("tool_receipt_event_ids")
        if not isinstance(ids, list) or not ids:
            problems.append("WorkerReceiptImported missing tool_receipt_event_ids")
            continue
        if set(ids) != receipt_ids:
            problems.append("WorkerReceiptImported must reference exactly all tool receipt ids")
        if worker_payload.get("assembled_from_tool_receipts") is not True:
            problems.append("WorkerReceiptImported missing assembled_from_tool_receipts true")

    cost_tokens = cost_event_tokens(events)
    receipt_totals = receipt_tokens(receipt_payloads)
    if cost_tokens is None:
        problems.append("CostEvent missing or invalid token fields")
    elif cost_tokens != receipt_totals:
        problems.append(f"CostEvent tool token totals must equal receipt totals: expected {receipt_totals}, got {cost_tokens}")

    final_pput = [
        payload(event)
        for event in events
        if event.get("event_type") == "PPUTAccounted" and payload(event).get("accounting_stage") == "final"
    ]
    if not final_pput:
        problems.append("final PPUTAccounted missing")
    elif not any(pput.get("tool_receipt_event_ids") == sorted(receipt_ids) for pput in final_pput):
        problems.append("final PPUTAccounted must include sorted tool_receipt_event_ids")

    return {
        "status": "FAIL" if problems else "PASS",
        "instance_id": run.get("instance_id"),
        "expected_result": run.get("expected_result"),
        "problems": problems,
        "attempted_action_count": len(attempted),
        "tool_receipt_count": len(receipt_payloads),
        "failed_tool_receipt_count": len(failed_receipts),
        "negative_controls_seen": sorted(x for x in negative_controls_seen if isinstance(x, str)),
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    auditor = load_micro_tape_auditor()
    with tempfile.TemporaryDirectory(prefix="turingos-tool-conservation-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), idx) for idx, run in enumerate(runs) if isinstance(run, dict)]

    problems = [problem for report in run_reports for problem in report.get("problems", [])]
    negative_seen = {
        item
        for report in run_reports
        for item in report.get("negative_controls_seen", [])
        if isinstance(item, str)
    }
    missing_controls = sorted(REQUIRED_NEGATIVE_CONTROLS - negative_seen)
    if missing_controls:
        problems.append("missing negative controls: " + ", ".join(missing_controls))
    status = "PASS" if run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    if missing_controls:
        status = "FAIL"
    failed_reports = [report for report in run_reports if report.get("expected_result") == "FAIL"]
    return {
        "schema_id": "ToolReceiptConservationAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundle_plus_coverage_expected_actions",
        "run_count": len(run_reports),
        "problems": problems,
        "all_attempted_actions_receipted": bool(run_reports)
        and all("missing receipt for attempted action" not in "\n".join(report.get("problems", [])) for report in run_reports),
        "failed_actions_receipted": bool(failed_reports)
        and all(report.get("failed_tool_receipt_count", 0) > 0 for report in failed_reports),
        "worker_receipts_trace_to_tool_receipts": bool(run_reports)
        and all(
            not any("WorkerReceiptImported" in problem for problem in report.get("problems", []))
            for report in run_reports
        ),
        "tool_cost_conservation": bool(run_reports)
        and all(
            not any("CostEvent" in problem or "final PPUTAccounted" in problem for problem in report.get("problems", []))
            for report in run_reports
        ),
        "negative_controls_covered": REQUIRED_NEGATIVE_CONTROLS.issubset(negative_seen),
        "negative_controls_seen": sorted(negative_seen),
        "runs": run_reports,
    }


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

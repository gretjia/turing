#!/usr/bin/env python3
"""Audit Stage9 Native API Worker tool receipts from Micro Tape bundles."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
REQUIRED_TOOLS = ["read_file", "list_dir", "grep", "apply_patch", "write_file", "run_command"]
SUCCESS_STATUSES = {"SUCCESS", "OK"}
FAILED_STATUSES = {"FAILED", "ERROR", "DENIED", "TIMEOUT"}


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


def event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def event_id(event: dict[str, Any]) -> str:
    return str(event["_event_id"])


def worker_receipts_are_assembled(worker_receipt_payloads: list[dict[str, Any]], tool_receipt_ids: set[str]) -> bool:
    if not worker_receipt_payloads:
        return False
    for payload in worker_receipt_payloads:
        if payload.get("assembled_from_tool_receipts") is not True:
            return False
        ids = payload.get("tool_receipt_event_ids")
        if not isinstance(ids, list) or not ids:
            return False
        if not set(ids).issubset(tool_receipt_ids):
            return False
    return True


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    native = run.get("native_api_worker")
    if not isinstance(native, dict):
        native = {}
        problems.append("native_api_worker metadata missing")

    expected_tools = native.get("expected_tools")
    if not isinstance(expected_tools, list):
        expected_tools = []
        problems.append("expected_tools missing")
    if set(expected_tools) != set(REQUIRED_TOOLS):
        problems.append("expected_tools must include all required native API tools")

    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {
            "status": "FAIL",
            "instance_id": run.get("instance_id"),
            "problems": problems + ["micro_tape_bundle missing"],
        }

    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"run_{index}")
    events = auditor.read_event_chain(git_dir)
    tool_events = [event for event in events if event.get("event_type") == "ToolReceiptAppended"]
    tool_payloads = [event_payload(event) | {"event_id": event_id(event)} for event in tool_events]
    tools_seen = {payload.get("tool") for payload in tool_payloads if isinstance(payload.get("tool"), str)}
    statuses_by_tool: dict[str, set[str]] = {}
    for payload in tool_payloads:
        tool = payload.get("tool")
        status = payload.get("status")
        if isinstance(tool, str) and isinstance(status, str):
            statuses_by_tool.setdefault(tool, set()).add(status)

    expected_result = str(run.get("expected_result") or "")
    is_accepted = any(event.get("event_type") == "CandidateAccepted" for event in events)
    is_failed = any(event.get("event_type") == "FailureNode" for event in events) and not is_accepted

    if expected_result == "PASS" and not is_accepted:
        problems.append("accepted fixture has no CandidateAccepted")
    if expected_result == "FAIL" and not is_failed:
        problems.append("failed fixture has no terminal FailureNode")

    if expected_result == "PASS":
        for tool in REQUIRED_TOOLS:
            if tool not in tools_seen:
                problems.append(f"missing tool receipt for {tool}")
            elif not (statuses_by_tool.get(tool, set()) & SUCCESS_STATUSES):
                problems.append(f"accepted run has no successful receipt for {tool}")

    failed_tool_receipts = [
        payload
        for payload in tool_payloads
        if isinstance(payload.get("status"), str) and payload["status"] in FAILED_STATUSES
    ]
    if expected_result == "FAIL" and not failed_tool_receipts:
        problems.append("failed run has no failed or denied tool receipt")

    tool_receipt_ids = {payload["event_id"] for payload in tool_payloads}
    worker_receipts = [event for event in events if event.get("event_type") == "WorkerReceiptImported"]
    worker_receipt_payloads = [event_payload(receipt) for receipt in worker_receipts]
    for payload in worker_receipt_payloads:
        ids = payload.get("tool_receipt_event_ids")
        if not isinstance(ids, list) or not ids:
            problems.append("WorkerReceiptImported missing tool_receipt_event_ids")
        elif not set(ids).issubset(tool_receipt_ids):
            problems.append("WorkerReceiptImported references unresolved tool receipt")
        if payload.get("assembled_from_tool_receipts") is not True:
            problems.append("WorkerReceiptImported missing assembled_from_tool_receipts true")
    if not worker_receipts_are_assembled(worker_receipt_payloads, tool_receipt_ids):
        problems.append("WorkerReceiptImported not assembled from resolved tool receipts")

    cost_events = [event_payload(event) for event in events if event.get("event_type") == "CostEvent"]
    if not cost_events:
        problems.append("CostEvent missing")
    elif not all(int(payload.get("tool_tokens") or 0) >= 0 and int(payload.get("tool_stdout_tokens") or 0) >= 0 for payload in cost_events):
        problems.append("CostEvent tool costs missing")

    return {
        "status": "FAIL" if problems else "PASS",
        "instance_id": run.get("instance_id"),
        "expected_result": expected_result,
        "problems": problems,
        "tools_seen": sorted(tool for tool in tools_seen if isinstance(tool, str)),
        "tool_receipt_count": len(tool_events),
        "failed_tool_receipt_count": len(failed_tool_receipts),
        "accepted": is_accepted,
        "failed": is_failed,
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    with tempfile.TemporaryDirectory(prefix="turingos-native-api-audit-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), idx) for idx, run in enumerate(runs) if isinstance(run, dict)]

    problems = [problem for report in run_reports for problem in report.get("problems", [])]
    accepted_reports = [report for report in run_reports if report.get("expected_result") == "PASS"]
    failed_reports = [report for report in run_reports if report.get("expected_result") == "FAIL"]
    accepted_complete = bool(accepted_reports) and all(
        set(report.get("tools_seen", [])) >= set(REQUIRED_TOOLS) and report["status"] == "PASS"
        for report in accepted_reports
    )
    failed_has_failed_tool = bool(failed_reports) and all(report.get("failed_tool_receipt_count", 0) > 0 for report in failed_reports)
    worker_assembled = all(
        "WorkerReceiptImported not assembled from resolved tool receipts" not in report.get("problems", [])
        and "WorkerReceiptImported missing tool_receipt_event_ids" not in report.get("problems", [])
        and "WorkerReceiptImported references unresolved tool receipt" not in report.get("problems", [])
        and "WorkerReceiptImported missing assembled_from_tool_receipts true" not in report.get("problems", [])
        for report in run_reports
    )
    tool_costs_counted = all("CostEvent missing" not in report.get("problems", []) for report in run_reports)
    status = "PASS" if run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    return {
        "schema_id": "NativeApiWorkerAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundle_plus_coverage_refs",
        "required_tools": REQUIRED_TOOLS,
        "run_count": len(run_reports),
        "problems": problems,
        "accepted_run_tool_receipts_complete": accepted_complete,
        "failed_run_has_failed_tool_receipt": failed_has_failed_tool,
        "worker_receipts_assembled_from_tool_receipts": worker_assembled,
        "tool_costs_counted": tool_costs_counted,
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

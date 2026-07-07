#!/usr/bin/env python3
"""Audit Stage8 failure-memory compression and capsule injection."""

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


def payload(event: dict[str, Any] | None) -> dict[str, Any]:
    if event is None or not isinstance(event.get("payload"), dict):
        return {}
    return event["payload"]


def string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            output.extend(string_values(item))
        return output
    if isinstance(value, dict):
        output: list[str] = []
        for item in value.values():
            output.extend(string_values(item))
        return output
    return []


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    missing: list[str] = []
    problems: list[str] = []
    fm = run.get("failure_memory")
    if not isinstance(fm, dict):
        fm = {}
        missing.append("failure_memory")

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
    by_id = event_index(events)

    source_failure_nodes = fm.get("source_failure_nodes")
    if not isinstance(source_failure_nodes, list) or not source_failure_nodes:
        missing.append("source_failure_nodes")
        source_failure_nodes = []
    for event_id in source_failure_nodes:
        event = by_id.get(event_id)
        if event is None:
            problems.append(f"source FailureNode not found: {event_id}")
        elif event.get("event_type") != "FailureNode":
            problems.append(f"source_failure_nodes item is not FailureNode: {event_id}")

    broadcast_id = fm.get("broadcast_rule_event_id")
    broadcast = by_id.get(broadcast_id) if isinstance(broadcast_id, str) else None
    if broadcast is None:
        missing.append("broadcast_rule_event_id")
    elif broadcast.get("event_type") != "BroadcastRuleActivated":
        problems.append("broadcast_rule_event_id must reference BroadcastRuleActivated")
    broadcast_payload = payload(broadcast)
    broadcast_sources = broadcast_payload.get("source_failure_nodes")
    if isinstance(broadcast_sources, list) and source_failure_nodes:
        if sorted(broadcast_sources) != sorted(source_failure_nodes):
            problems.append("BroadcastRuleActivated source_failure_nodes mismatch")
    else:
        problems.append("BroadcastRuleActivated must carry source_failure_nodes")

    injected_capsule_id = fm.get("injected_into_capsule_id")
    if not isinstance(injected_capsule_id, str) or not injected_capsule_id:
        missing.append("injected_into_capsule_id")
    capsule = None
    for event in events:
        event_payload = payload(event)
        if event.get("event_type") == "WorkCapsuleBuilt" and event_payload.get("capsule_id") == injected_capsule_id:
            capsule = event
    if capsule is None and isinstance(injected_capsule_id, str):
        problems.append(f"injected capsule not found: {injected_capsule_id}")
    capsule_payload = payload(capsule)
    rule_ids = capsule_payload.get("injected_broadcast_rule_ids")
    rule_id = broadcast_payload.get("rule_id")
    if not isinstance(rule_ids, list) or rule_id not in rule_ids:
        problems.append("later WorkCapsuleBuilt did not consume the broadcast rule")

    for key in [
        "raw_log_refs_present_only_as_private_evidence",
        "raw_log_text_absent_from_visible_capsule",
        "hidden_predicates_absent_from_visible_capsule",
        "broadcast_rule_reduced_from_tape",
    ]:
        if fm.get(key) is not True:
            problems.append(f"{key} must be true")

    forbidden_markers = ["traceback", "hidden predicate", "pput formula", "raw log text"]
    visible_text = "\n".join(string_values(capsule_payload)).lower()
    for marker in forbidden_markers:
        if marker in visible_text:
            problems.append(f"visible capsule contains forbidden marker {marker!r}")

    return {
        "status": "FAIL" if missing or problems else "PASS",
        "instance_id": run.get("instance_id"),
        "missing": missing,
        "problems": problems,
        "source_failure_nodes": source_failure_nodes,
        "failure_class": fm.get("failure_class"),
        "abstract_pattern": fm.get("abstract_pattern"),
        "broadcast_rule_event_id": broadcast_id,
        "injected_into_capsule_id": injected_capsule_id,
        "raw_log_refs_present_only_as_private_evidence": fm.get("raw_log_refs_present_only_as_private_evidence"),
        "raw_log_text_absent_from_visible_capsule": fm.get("raw_log_text_absent_from_visible_capsule"),
        "hidden_predicates_absent_from_visible_capsule": fm.get("hidden_predicates_absent_from_visible_capsule"),
        "broadcast_rule_reduced_from_tape": fm.get("broadcast_rule_reduced_from_tape"),
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    with tempfile.TemporaryDirectory(prefix="turingos-failure-memory-audit-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), idx) for idx, run in enumerate(runs) if isinstance(run, dict)]

    missing = sorted({item for report in run_reports for item in report.get("missing", [])})
    problems = [item for report in run_reports for item in report.get("problems", [])]
    status = "PASS" if run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    first = run_reports[0] if run_reports else {}
    return {
        "schema_id": "FailureMemoryAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundle_plus_coverage_refs",
        "run_count": len(run_reports),
        "missing": missing,
        "problems": problems,
        "source_failure_nodes": first.get("source_failure_nodes", []),
        "failure_class": first.get("failure_class"),
        "abstract_pattern": first.get("abstract_pattern"),
        "broadcast_rule_event_id": first.get("broadcast_rule_event_id"),
        "injected_into_capsule_id": first.get("injected_into_capsule_id"),
        "raw_log_refs_present_only_as_private_evidence": first.get("raw_log_refs_present_only_as_private_evidence"),
        "raw_log_text_absent_from_visible_capsule": first.get("raw_log_text_absent_from_visible_capsule"),
        "hidden_predicates_absent_from_visible_capsule": first.get("hidden_predicates_absent_from_visible_capsule"),
        "broadcast_rule_reduced_from_tape": first.get("broadcast_rule_reduced_from_tape"),
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

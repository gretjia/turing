#!/usr/bin/env python3
"""Audit Stage11 failure-memory activation and later capsule consumption."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
FORBIDDEN_VISIBLE_MARKERS = {
    "traceback",
    "stack trace",
    "raw stdout",
    "raw stderr",
    "raw log text",
    "hidden predicate",
    "private_micro_contract",
    "pput formula",
    "vpput formula",
    "heldout",
    "official solution",
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


def payload(event: dict[str, Any] | None) -> dict[str, Any]:
    if event is None or not isinstance(event.get("payload"), dict):
        return {}
    return event["payload"]


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


def contains_forbidden_visible_content(value: Any) -> bool:
    text = "\n".join(strings(value)).lower()
    return any(marker in text for marker in FORBIDDEN_VISIBLE_MARKERS)


def event_index(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {event["_event_id"]: event for event in events}


def find_capsule(events: list[dict[str, Any]], capsule_id: str | None) -> dict[str, Any] | None:
    for event in events:
        event_payload = payload(event)
        if event.get("event_type") == "WorkCapsuleBuilt" and event_payload.get("capsule_id") == capsule_id:
            return event
    return None


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    fm = run.get("failure_memory_activation")
    if not isinstance(fm, dict):
        fm = {}
        problems.append("failure_memory_activation missing")

    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {"status": "FAIL", "instance_id": run.get("instance_id"), "problems": problems + ["micro_tape_bundle missing"]}

    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"run_{index}")
    events = auditor.read_event_chain(git_dir)
    by_id = event_index(events)

    source_failure_nodes = fm.get("source_failure_nodes")
    if not isinstance(source_failure_nodes, list) or not source_failure_nodes:
        problems.append("source_failure_nodes missing")
        source_failure_nodes = []
    for event_id in source_failure_nodes:
        event = by_id.get(event_id)
        if event is None or event.get("event_type") != "FailureNode":
            problems.append(f"source failure node unresolved: {event_id}")

    broadcast = by_id.get(fm.get("activated_rule_event_id"))
    if broadcast is None:
        problems.append("activated_rule_event_id unresolved")
        broadcast_payload: dict[str, Any] = {}
    elif broadcast.get("event_type") != "BroadcastRuleActivated":
        problems.append("activated_rule_event_id must reference BroadcastRuleActivated")
        broadcast_payload = payload(broadcast)
    else:
        broadcast_payload = payload(broadcast)

    if broadcast_payload.get("source_failure_nodes") != source_failure_nodes:
        problems.append("BroadcastRuleActivated source_failure_nodes mismatch")
    for key in ["hidden_details_removed", "raw_log_text_absent", "hidden_predicates_absent", "pput_or_heldout_details_absent"]:
        if broadcast_payload.get(key) is not True:
            problems.append(f"BroadcastRuleActivated {key} must be true")
    if contains_forbidden_visible_content(broadcast_payload):
        problems.append("BroadcastRuleActivated contains forbidden visible content")

    capsule = find_capsule(events, fm.get("injected_into_capsule_id"))
    if capsule is None:
        problems.append("injected capsule not found")
        capsule_payload: dict[str, Any] = {}
    else:
        capsule_payload = payload(capsule)

    rule_id = broadcast_payload.get("rule_id")
    consumed_ids = capsule_payload.get("consumed_broadcast_rule_ids")
    injected_ids = capsule_payload.get("injected_broadcast_rule_ids")
    later_consumed = (
        isinstance(consumed_ids, list)
        and rule_id in consumed_ids
        and isinstance(injected_ids, list)
        and rule_id in injected_ids
    )
    if not later_consumed:
        problems.append("later WorkCapsuleBuilt did not consume the broadcast rule")
    if capsule_payload.get("source_failure_nodes") != source_failure_nodes:
        problems.append("later WorkCapsuleBuilt source_failure_nodes mismatch")

    for key in [
        "raw_log_refs_private_only",
        "raw_log_text_absent_from_visible_capsule",
        "hidden_predicates_absent_from_visible_capsule",
        "pput_or_heldout_details_absent_from_visible_capsule",
        "broadcast_rule_reduced_from_tape",
    ]:
        if fm.get(key) is not True:
            problems.append(f"{key} must be true")
    if contains_forbidden_visible_content(capsule_payload):
        problems.append("visible capsule contains forbidden marker")

    return {
        "status": "FAIL" if problems else "PASS",
        "instance_id": run.get("instance_id"),
        "problems": problems,
        "source_failure_nodes": source_failure_nodes,
        "failure_class": fm.get("failure_class"),
        "abstract_pattern": fm.get("abstract_pattern"),
        "activated_rule_event_id": fm.get("activated_rule_event_id"),
        "injected_into_capsule_id": fm.get("injected_into_capsule_id"),
        "later_capsule_consumed_rule": later_consumed,
        "raw_log_refs_private_only": fm.get("raw_log_refs_private_only"),
        "raw_log_text_absent_from_visible_capsule": fm.get("raw_log_text_absent_from_visible_capsule"),
        "hidden_predicates_absent_from_visible_capsule": fm.get("hidden_predicates_absent_from_visible_capsule"),
        "pput_or_heldout_details_absent_from_visible_capsule": fm.get("pput_or_heldout_details_absent_from_visible_capsule"),
        "broadcast_rule_reduced_from_tape": fm.get("broadcast_rule_reduced_from_tape"),
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    with tempfile.TemporaryDirectory(prefix="turingos-stage11-fm-audit-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), idx) for idx, run in enumerate(runs) if isinstance(run, dict)]

    problems = [problem for report in run_reports for problem in report.get("problems", [])]
    status = "PASS" if run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL"
    first = run_reports[0] if run_reports else {}
    return {
        "schema_id": "Stage11FailureMemoryActivationAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundle_plus_coverage_refs",
        "run_count": len(run_reports),
        "problems": problems,
        "source_failure_nodes": first.get("source_failure_nodes", []),
        "failure_class": first.get("failure_class"),
        "abstract_pattern": first.get("abstract_pattern"),
        "activated_rule_event_id": first.get("activated_rule_event_id"),
        "injected_into_capsule_id": first.get("injected_into_capsule_id"),
        "later_capsule_consumed_rule": all(report.get("later_capsule_consumed_rule") is True for report in run_reports),
        "raw_log_refs_private_only": all(report.get("raw_log_refs_private_only") is True for report in run_reports),
        "raw_log_text_absent_from_visible_capsule": all(
            report.get("raw_log_text_absent_from_visible_capsule") is True for report in run_reports
        ),
        "hidden_predicates_absent_from_visible_capsule": all(
            report.get("hidden_predicates_absent_from_visible_capsule") is True for report in run_reports
        ),
        "pput_or_heldout_details_absent_from_visible_capsule": all(
            report.get("pput_or_heldout_details_absent_from_visible_capsule") is True for report in run_reports
        ),
        "broadcast_rule_reduced_from_tape": all(report.get("broadcast_rule_reduced_from_tape") is True for report in run_reports),
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

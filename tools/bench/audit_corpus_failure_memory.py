#!/usr/bin/env python3
"""Audit Stage14 corpus-level failure memory from MicroTape bundles."""

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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def payload(event: dict[str, Any] | None) -> dict[str, Any]:
    if event is None or not isinstance(event.get("payload"), dict):
        return {}
    return event["payload"]


def fetch_all_events(coverage: dict[str, Any], auditor: Any, work_root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    for index, run in enumerate(coverage.get("turingos_arm_runs", [])):
        if not isinstance(run, dict) or not isinstance(run.get("micro_tape_bundle"), str):
            continue
        git_dir, _ = auditor.fetch_bundle(Path(run["micro_tape_bundle"]), work_root / f"stage14_run_{index}")
        for event in auditor.read_event_chain(git_dir):
            event["_bundle_instance_id"] = run.get("instance_id")
            events.append(event)
    return events, {event["_event_id"]: event for event in events}


def find_capsule(events: list[dict[str, Any]], capsule_id: str | None) -> dict[str, Any] | None:
    for event in events:
        event_payload = payload(event)
        if event.get("event_type") == "WorkCapsuleBuilt" and event_payload.get("capsule_id") == capsule_id:
            return event
    return None


def audit_from_events(coverage: dict[str, Any], events: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    problems: list[str] = []
    meta = coverage.get("corpus_failure_memory")
    if not isinstance(meta, dict):
        meta = {}
        problems.append("corpus_failure_memory metadata missing")

    source_failure_nodes = meta.get("source_failure_nodes")
    if not isinstance(source_failure_nodes, list) or not source_failure_nodes:
        source_failure_nodes = []
        problems.append("source_failure_nodes missing")

    failure_class = meta.get("failure_class")
    min_source_failures = meta.get("min_source_failures", 3)
    if not isinstance(min_source_failures, int) or min_source_failures < 1:
        problems.append("min_source_failures must be positive")
        min_source_failures = 3

    source_events: list[dict[str, Any]] = []
    for event_id in source_failure_nodes:
        event = by_id.get(event_id)
        if event is None:
            problems.append(f"source failure node unresolved: {event_id}")
            continue
        if event.get("event_type") != "FailureNode":
            problems.append(f"source failure node is not FailureNode: {event_id}")
            continue
        source_events.append(event)
        if payload(event).get("failure_class") != failure_class:
            problems.append(f"source failure class mismatch: {event_id}")
    if len(source_events) < min_source_failures:
        problems.append(f"source failure count {len(source_events)} below threshold {min_source_failures}")

    activation = by_id.get(meta.get("activated_rule_event_id"))
    if activation is None:
        problems.append("activated_rule_event_id unresolved")
        activation_payload: dict[str, Any] = {}
    elif activation.get("event_type") != "BroadcastRuleActivated":
        problems.append("activated_rule_event_id must reference BroadcastRuleActivated")
        activation_payload = payload(activation)
    else:
        activation_payload = payload(activation)

    if activation_payload.get("source_failure_nodes") != source_failure_nodes:
        problems.append("BroadcastRuleActivated source_failure_nodes mismatch")
    if activation_payload.get("failure_class") != failure_class:
        problems.append("BroadcastRuleActivated failure_class mismatch")
    if activation_payload.get("activation_threshold_met") is not True:
        problems.append("BroadcastRuleActivated activation_threshold_met must be true")
    for key in ["hidden_details_removed", "raw_log_text_absent", "hidden_predicates_absent", "pput_or_heldout_details_absent"]:
        if activation_payload.get(key) is not True:
            problems.append(f"BroadcastRuleActivated {key} must be true")
    if contains_forbidden_visible_content(activation_payload):
        problems.append("BroadcastRuleActivated contains forbidden visible content")

    capsule = find_capsule(events, meta.get("consumer_capsule_id"))
    capsule_payload = payload(capsule)
    if capsule is None:
        problems.append("consumer capsule not found")
    rule_id = activation_payload.get("rule_id")
    if not (
        isinstance(capsule_payload.get("consumed_broadcast_rule_ids"), list)
        and rule_id in capsule_payload.get("consumed_broadcast_rule_ids")
    ):
        problems.append("consumer capsule did not consume activated rule")
    if capsule_payload.get("source_failure_nodes") != source_failure_nodes:
        problems.append("consumer capsule source_failure_nodes mismatch")
    if contains_forbidden_visible_content(capsule_payload):
        problems.append("consumer capsule contains forbidden visible content")

    efficacy = meta.get("efficacy")
    if not isinstance(efficacy, dict):
        efficacy = {}
        problems.append("efficacy metadata missing")
    if efficacy.get("pre_activation_failures") != len(source_events):
        problems.append("efficacy.pre_activation_failures must equal resolved source failure count")
    if not isinstance(efficacy.get("sample_size"), int) or efficacy.get("sample_size", 0) < len(source_events):
        problems.append("efficacy.sample_size must cover source failures")
    if efficacy.get("causal_claim_allowed") is not False:
        problems.append("efficacy causal_claim_allowed must be false without controlled comparison")
    if "caused" in str(efficacy.get("claim", "")).lower():
        problems.append("efficacy claim must not state causality")

    cluster_report = {
        "status": "PASS" if not any("source" in problem or "threshold" in problem for problem in problems) else "FAIL",
        "truth_source": "micro_tape_bundles",
        "failure_class": failure_class,
        "source_failure_count": len(source_events),
        "min_source_failures": min_source_failures,
        "source_failure_nodes": source_failure_nodes,
    }
    visibility_report = {
        "status": "FAIL" if any("visible content" in problem or "raw_log" in problem or "hidden" in problem for problem in problems) else "PASS",
        "truth_source": "micro_tape_bundles",
        "activated_rule_event_id": meta.get("activated_rule_event_id"),
        "consumer_capsule_id": meta.get("consumer_capsule_id"),
        "raw_logs_private": activation_payload.get("raw_log_refs_private_only") is True,
    }
    efficacy_report = {
        "status": "PASS"
        if not any("efficacy" in problem or "caus" in problem.lower() for problem in problems)
        else "FAIL",
        "truth_source": "micro_tape_bundles_plus_stage14_metadata",
        "pre_activation_failures": efficacy.get("pre_activation_failures"),
        "post_activation_failures": efficacy.get("post_activation_failures"),
        "consumed_rule_attempts": efficacy.get("consumed_rule_attempts"),
        "non_consumed_comparable_attempts": efficacy.get("non_consumed_comparable_attempts"),
        "sample_size": efficacy.get("sample_size"),
        "causal_claim_allowed": efficacy.get("causal_claim_allowed"),
        "claim": efficacy.get("claim"),
    }
    status = "PASS" if not problems else "FAIL"
    return {
        "schema_id": "Stage14CorpusFailureMemoryAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundles_plus_coverage_refs",
        "problems": problems,
        "failure_cluster": cluster_report,
        "broadcast_visibility": visibility_report,
        "efficacy": efficacy_report,
        "source_failure_nodes": source_failure_nodes,
        "activated_rule_event_id": meta.get("activated_rule_event_id"),
        "consumer_capsule_id": meta.get("consumer_capsule_id"),
        "later_capsule_consumed_rule": "consumer capsule did not consume activated rule" not in problems,
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    with tempfile.TemporaryDirectory(prefix="turingos-corpus-memory-") as temp:
        events, by_id = fetch_all_events(coverage, auditor, Path(temp))
        return audit_from_events(coverage, events, by_id)


def write_lineage(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Stage14 Cross-Task Memory Lineage",
        "",
        f"Failure class: `{report['failure_cluster'].get('failure_class')}`",
        f"Source failure count: `{report['failure_cluster'].get('source_failure_count')}`",
        f"Activated rule: `{report.get('activated_rule_event_id')}`",
        f"Consumer capsule: `{report.get('consumer_capsule_id')}`",
        "",
        "## Source Failure Nodes",
        "",
    ]
    for event_id in report.get("source_failure_nodes", []):
        lines.append(f"- `{event_id}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    report = audit_coverage(Path(args.coverage))
    out_dir = Path(args.out_dir)
    write_json(out_dir / "corpus_failure_memory_audit.json", report)
    write_json(out_dir / "failure_cluster_audit.json", report["failure_cluster"])
    write_json(out_dir / "broadcast_rule_efficacy_audit.json", report["efficacy"])
    write_json(out_dir / "broadcast_rule_visibility_audit.json", report["broadcast_visibility"])
    write_lineage(out_dir / "cross_task_memory_lineage.md", report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

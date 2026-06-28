#!/usr/bin/env python3
"""Audit Stage16R unsolved repair evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"

STRICT_REQUIRED_PASS = [
    "overall",
    "replay_structural_integrity",
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

FORBIDDEN_VISIBLE = [
    "raw stderr",
    "raw stdout",
    "hidden predicate",
    "private contract",
    "pput formula",
    "vpput formula",
    "heldout",
    "official solution",
    "gold patch",
    "sk-",
    "auth.json",
]


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
    if event is None:
        return {}
    value = event.get("payload")
    return value if isinstance(value, dict) else {}


def seq(event: dict[str, Any] | None) -> int | None:
    if event is None:
        return None
    value = event.get("sequence")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def source_unsolved(source_stage16_root: Path) -> list[dict[str, Any]]:
    aggregate = load_json(source_stage16_root / "stage16_aggregate_report.json")
    return [run for run in aggregate.get("runs", []) if isinstance(run, dict) and not run.get("solved")]


def strict_status(root: Path) -> dict[str, Any]:
    path = root / "micro_tape_audit_strict/micro_tape_decision_dag_audit.json"
    if not path.exists():
        return {}
    report = load_json(path)
    summary = report.get("status_summary", report)
    return summary if isinstance(summary, dict) else {}


def cost_total(events: list[dict[str, Any]]) -> int:
    total = 0
    for event in events:
        if event.get("event_type") != "CostEvent":
            continue
        value = payload(event).get("total_tokens")
        if isinstance(value, int) and value > 0 and not isinstance(value, bool):
            total += value
    return total


def visible_text(run: dict[str, Any]) -> str:
    values = [run.get("visible_capsule_text")]
    for item in run.get("visible_capsules", []) if isinstance(run.get("visible_capsules"), list) else []:
        if isinstance(item, dict):
            values.append(item.get("text"))
            values.append(item.get("new_instruction"))
    return "\n".join(str(value) for value in values if isinstance(value, str)).lower()


def audit_repair_run(run: dict[str, Any], source_run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    instance_id = run.get("instance_id")
    bundle_path = Path(str(run.get("micro_tape_bundle", "")))
    if not bundle_path.exists():
        return {"status": "FAIL", "instance_id": instance_id, "problems": [f"missing repair bundle: {bundle_path}"]}
    if run.get("source_stage16_terminal_event_id") != source_run.get("terminal_event_id"):
        problems.append("source terminal event id must match Stage16 unsolved terminal event")
    if run.get("authorization_mode") != "required":
        problems.append("authorization_mode must be required")
    if not isinstance(run.get("authorization_head"), str) or not run["authorization_head"].startswith("mu:"):
        problems.append("authorization_head must be present")
    loop = run.get("loop_until_pass")
    if not isinstance(loop, dict):
        loop = {}
        problems.append("loop_until_pass missing")
    for key in ["human_intervention_count", "manual_patch_count", "manual_approval_count", "manual_rerun_selection_count"]:
        if loop.get(key) != 0:
            problems.append(f"{key} must be 0")
    if loop.get("fallback_to_auto_authorization") is not False:
        problems.append("fallback_to_auto_authorization must be false")
    text = visible_text(run)
    for marker in FORBIDDEN_VISIBLE:
        if marker in text:
            problems.append(f"visible capsule contains forbidden marker: {marker}")

    git_dir, _ = auditor.fetch_bundle(bundle_path, work_root / f"stage16r_{index}")
    events = auditor.read_event_chain(git_dir)
    by_id = {event["_event_id"]: event for event in events}
    official_passes = [event for event in events if event.get("event_type") == "OfficialEvaluatorEvidenceImported" and payload(event).get("result") == "PASS"]
    accepts = [event for event in events if event.get("event_type") == "CandidateAccepted"]
    final_pputs = [event for event in events if event.get("event_type") == "PPUTAccounted" and payload(event).get("accounting_stage") == "final"]
    certificates = [event for event in events if event.get("event_type") == "FailureCertificate"]
    broadcasts = [event for event in events if event.get("event_type") == "BroadcastRuleActivated"]
    capsules = [event for event in events if event.get("event_type") == "WorkCapsuleBuilt"]
    source_imports = [event for event in events if event.get("event_type") == "EvidenceBound" and payload(event).get("source_stage16_terminal_event_id") == source_run.get("terminal_event_id")]
    total_cost = cost_total(events)
    terminal = accepts[-1] if accepts else None
    if not source_imports:
        problems.append("source Stage16 failure evidence must be imported")
    if not certificates:
        problems.append("FailureCertificate required")
    if not broadcasts:
        problems.append("BroadcastRuleActivated required")
    if not any(payload(event).get("consumed_broadcast_rule_ids") for event in capsules):
        problems.append("later WorkCapsuleBuilt must consume broadcast rule")
    if not official_passes:
        problems.append("repair requires official PASS evidence")
    if terminal is None:
        problems.append("repair requires CandidateAccepted")
    elif official_passes and seq(official_passes[-1]) is not None and seq(terminal) is not None and seq(official_passes[-1]) >= seq(terminal):
        problems.append("official PASS must precede CandidateAccepted")
    if terminal is not None:
        if not any(
            payload(event).get("progress") == 1
            and payload(event).get("terminal_event_id") == terminal["_event_id"]
            and payload(event).get("total_run_token_count") == total_cost
            and seq(event) is not None
            and seq(terminal) is not None
            and seq(event) > seq(terminal)
            for event in final_pputs
        ):
            problems.append("final PPUT progress=1 must follow CandidateAccepted and count all costs")

    terminal_settlements: set[str] = set()
    for event in events:
        if event.get("event_type") != "MarketSettled":
            continue
        basis = by_id.get(payload(event).get("settlement_basis_event_id"))
        terminal_event = by_id.get(payload(event).get("terminal_event_id"))
        if payload(event).get("is_terminal") is not True or basis is None or terminal_event is None:
            problems.append("MarketSettled must be terminal and resolve basis/terminal ids")
            continue
        if seq(event) is not None and seq(basis) is not None and seq(event) <= seq(basis):
            problems.append("MarketSettled must occur after settlement basis")
        if seq(event) is not None and seq(terminal_event) is not None and seq(event) <= seq(terminal_event):
            problems.append("MarketSettled must occur after terminal accepted event")
        terminal_settlements.add(event["_event_id"])
    for event in events:
        if event.get("event_type") != "RewardDistributed":
            continue
        settlement_id = payload(event).get("settlement_event_id")
        settlement = by_id.get(settlement_id)
        if settlement_id not in terminal_settlements or settlement is None:
            problems.append("RewardDistributed must reference terminal MarketSettled")
        elif seq(event) is not None and seq(settlement) is not None and seq(event) <= seq(settlement):
            problems.append("RewardDistributed must occur after terminal MarketSettled")

    return {
        "status": "PASS" if not problems else "FAIL",
        "instance_id": instance_id,
        "source_stage16_terminal_event_id": source_run.get("terminal_event_id"),
        "candidate_accepted_event_id": terminal["_event_id"] if terminal is not None else None,
        "event_count": len(events),
        "total_cost_tokens": total_cost,
        "problems": problems,
    }


def audit_stage16r(source_stage16_root: Path, root: Path) -> dict[str, Any]:
    problems: list[str] = []
    claim = load_json(root / "CLAIM_BOUNDARY.json") if (root / "CLAIM_BOUNDARY.json").exists() else {}
    if claim.get("not_full_swe_bench_dataset") is not True:
        problems.append("CLAIM_BOUNDARY must mark not_full_swe_bench_dataset=true")
    if claim.get("full_swe_bench_score_claim_allowed") is not False:
        problems.append("full SWE-bench score claim must remain forbidden")
    if claim.get("source_stage16_sha") != "f542dcca670a5185f30c3c6940f8e8518235d7d0":
        problems.append("source_stage16_sha mismatch")

    strict = strict_status(root)
    for key in STRICT_REQUIRED_PASS:
        if strict.get(key) != "PASS":
            problems.append(f"strict audit {key} must be PASS")

    coverage = load_json(root / "substrate_coverage.json") if (root / "substrate_coverage.json").exists() else {}
    runs = coverage.get("turingos_arm_runs")
    if not isinstance(runs, list):
        runs = []
        problems.append("turingos_arm_runs missing")
    source_runs = source_unsolved(source_stage16_root)
    source_ids = [run["instance_id"] for run in source_runs]
    run_ids = [run.get("instance_id") for run in runs if isinstance(run, dict)]
    if run_ids != source_ids:
        problems.append("Stage16R repair runs must exactly match Stage16 unsolved list")
    if len(runs) != 7:
        problems.append("Stage16R requires exactly 7 repair bundles")

    bundle_manifest = root / "bundle_sha256s.txt"
    if bundle_manifest.exists():
        for line in bundle_manifest.read_text().splitlines():
            if not line.strip():
                continue
            expected, path = line.split(maxsplit=1)
            bundle = Path(path)
            if not bundle.exists():
                problems.append(f"missing repair bundle: {bundle}")
            elif sha256_file(bundle) != expected:
                problems.append(f"bundle sha mismatch: {bundle}")
    else:
        problems.append("bundle_sha256s.txt missing")

    auditor = load_micro_tape_auditor()
    source_by_id = {run["instance_id"]: run for run in source_runs}
    with tempfile.TemporaryDirectory(prefix="turingos-stage16r-audit-") as temp:
        run_reports = [
            audit_repair_run(run, source_by_id.get(run.get("instance_id"), {}), auditor, Path(temp), index)
            for index, run in enumerate(runs)
            if isinstance(run, dict)
        ]
    problems.extend(problem for report in run_reports for problem in report["problems"])

    repaired_count = sum(1 for report in run_reports if report["status"] == "PASS" and report.get("candidate_accepted_event_id"))
    remaining = len(source_runs) - repaired_count
    shard_full_pass_allowed = remaining == 0
    if claim.get("twenty_task_shard_full_pass_claim_allowed") != shard_full_pass_allowed:
        problems.append("twenty_task_shard_full_pass_claim_allowed mismatch")
    report = {
        "schema_id": "Stage16RRepairAudit.v1",
        "status": "PASS" if not problems and len(run_reports) == 7 else "FAIL",
        "source_unsolved_count": len(source_runs),
        "repaired_count": repaired_count,
        "remaining_unsolved_count": remaining,
        "twenty_task_shard_after_repair": {
            "run_count": 20,
            "previous_solved_count": 13,
            "newly_repaired_count": repaired_count,
            "total_solved_count": 13 + repaired_count,
            "total_unsolved_count": remaining,
            "twenty_task_shard_full_pass_claim_allowed": shard_full_pass_allowed,
        },
        "full_swe_bench_score_claim_allowed": False,
        "problems": problems,
        "runs": run_reports,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-stage16-root", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = audit_stage16r(Path(args.source_stage16_root), Path(args.root))
    write_json(Path(args.out), report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

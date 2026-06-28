#!/usr/bin/env python3
"""Audit Stage16 sealed campaign evidence.

Stage16 separates two claims:
- sealed replay campaign PASS: every bundle is present, replayable, and honest;
- full-pass claim: allowed only when unsolved_count == 0.
"""

from __future__ import annotations

import argparse
import hashlib
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

STAGE16_CLAIM_BOUNDARY = {
    "stage16_artifact_kind": "STAGE16_SHARD_SEALED_REPLAY",
    "dataset_scope": "frozen_stage12_20_task_verified_mini_shard",
    "not_full_swe_bench_dataset": True,
    "full_score_claim_allowed": False,
    "full_swe_bench_campaign_not_run": True,
    "next_required_stage": "Stage16R",
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
    if event is None:
        return {}
    value = event.get("payload")
    return value if isinstance(value, dict) else {}


def sequence(event: dict[str, Any] | None) -> int | None:
    if event is None:
        return None
    value = event.get("sequence")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def event_id(event: dict[str, Any] | None) -> str | None:
    if event is None:
        return None
    value = event.get("_event_id")
    return value if isinstance(value, str) else None


def cost_total(events: list[dict[str, Any]]) -> int:
    total = 0
    for event in events:
        if event.get("event_type") != "CostEvent":
            continue
        value = payload(event).get("total_tokens")
        if isinstance(value, int) and value > 0 and not isinstance(value, bool):
            total += value
    return total


def cost_sources(events: list[dict[str, Any]]) -> dict[str, Any]:
    kinds: set[str] = set()
    provider_reported = False
    for event in events:
        if event.get("event_type") != "CostEvent":
            continue
        event_payload = payload(event)
        kind = event_payload.get("cost_source_kind")
        if isinstance(kind, str):
            kinds.add(kind)
        if event_payload.get("provider_reported") is True:
            provider_reported = True
    return {
        "cost_source_kind": sorted(kinds) or ["unspecified"],
        "provider_reported": provider_reported,
        "vpput_cost_completeness": "provider_reported" if provider_reported else "tape_conserved_estimated_tokens",
    }


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def final_pput_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event_type") == "PPUTAccounted" and payload(event).get("accounting_stage") == "final"
    ]


def strict_problems(strict_summary: dict[str, Any]) -> list[str]:
    return [f"strict audit {key} must be PASS" for key in STRICT_REQUIRED_PASS if strict_summary.get(key) != "PASS"]


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    instance_id = run.get("instance_id")
    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {"status": "FAIL", "instance_id": instance_id, "problems": ["missing bundle path"]}
    bundle_path = Path(bundle_value)
    if not bundle_path.exists():
        return {"status": "FAIL", "instance_id": instance_id, "problems": [f"missing bundle: {bundle_path}"]}

    bundle_hash = sha256_file(bundle_path)
    git_dir, _ = auditor.fetch_bundle(bundle_path, work_root / f"stage16_run_{index}")
    events = auditor.read_event_chain(git_dir)
    by_id = {event["_event_id"]: event for event in events}
    official_passes = [
        event
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported" and payload(event).get("result") == "PASS"
    ]
    official_failures = [
        event
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported" and payload(event).get("result") == "FAIL"
    ]
    accepts = [event for event in events if event.get("event_type") == "CandidateAccepted"]
    final_pputs = final_pput_events(events)
    final_pput_ids = [event["_event_id"] for event in final_pputs]
    total_cost = cost_total(events)
    cost_source = cost_sources(events)
    solved = bool(accepts)
    terminal_accept = accepts[-1] if accepts else None
    terminal_event = terminal_accept

    if run.get("authorization_mode") != "required":
        problems.append("authorization_mode must be required")
    if not isinstance(run.get("authorization_head"), str) or not str(run.get("authorization_head")).startswith("mu:"):
        problems.append("authorization_head must be present")
    loop = run.get("loop_until_pass")
    if not isinstance(loop, dict):
        loop = {}
        problems.append("loop_until_pass metadata missing")
    for key in ["human_intervention_count", "manual_patch_count", "manual_approval_count", "manual_rerun_selection_count"]:
        if loop.get(key) != 0:
            problems.append(f"{key} must be 0")
    if loop.get("fallback_to_auto_authorization") is not False:
        problems.append("fallback_to_auto_authorization must be false")
    if loop.get("verified_from_micro_tape_bundle_only") is not True:
        problems.append("verified_from_micro_tape_bundle_only must be true")

    if solved:
        if not official_passes:
            problems.append("solved instance requires official PASS")
        elif sequence(official_passes[-1]) is not None and sequence(terminal_accept) is not None:
            if sequence(official_passes[-1]) >= sequence(terminal_accept):
                problems.append("official PASS must precede CandidateAccepted")
        pput_ok = any(
            payload(event).get("progress") == 1
            and payload(event).get("terminal_event_id") == event_id(terminal_accept)
            and payload(event).get("total_run_token_count") == total_cost
            and sequence(event) is not None
            and sequence(terminal_accept) is not None
            and sequence(event) > sequence(terminal_accept)
            for event in final_pputs
        )
        if not pput_ok:
            problems.append("solved instance requires post-accept final PPUT progress 1 with all costs")
    else:
        if not official_failures:
            problems.append("unsolved instance requires official FAIL evidence")
        terminal_failures = [event for event in events if event.get("event_type") in {"FailureNode", "BudgetExhausted"}]
        terminal_event = terminal_failures[-1] if terminal_failures else None
        if terminal_event is None:
            problems.append("unsolved instance requires terminal failure/budget event")
        pput_ok = any(
            payload(event).get("progress") == 0
            and payload(event).get("total_run_token_count") == total_cost
            and sequence(event) is not None
            and (terminal_event is None or sequence(terminal_event) is None or sequence(event) > sequence(terminal_event))
            for event in final_pputs
        )
        if not pput_ok:
            problems.append("unsolved instance requires terminal final PPUT progress 0 with all costs")

    market_ok = True
    terminal_settlements: set[str] = set()
    market_settled_event_ids: list[str] = []
    reward_event_ids: list[str] = []
    for event in events:
        if event.get("event_type") != "MarketSettled":
            continue
        event_payload = payload(event)
        basis = by_id.get(event_payload.get("settlement_basis_event_id"))
        terminal = by_id.get(event_payload.get("terminal_event_id"))
        if event_payload.get("is_terminal") is not True or basis is None or terminal is None:
            problems.append("MarketSettled must be terminal and reference tape-resolved basis/terminal events")
            market_ok = False
            continue
        if sequence(event) is not None and sequence(basis) is not None and sequence(event) <= sequence(basis):
            problems.append("MarketSettled must occur after settlement basis")
            market_ok = False
        if sequence(event) is not None and sequence(terminal) is not None and sequence(event) <= sequence(terminal):
            problems.append("MarketSettled must occur after terminal accept/failure")
            market_ok = False
        terminal_settlements.add(event["_event_id"])
        market_settled_event_ids.append(event["_event_id"])
    for event in events:
        if event.get("event_type") != "RewardDistributed":
            continue
        reward_event_ids.append(event["_event_id"])
        settlement_id = payload(event).get("settlement_event_id")
        settlement = by_id.get(settlement_id)
        if settlement_id not in terminal_settlements or settlement is None:
            problems.append("RewardDistributed must reference terminal MarketSettled")
            market_ok = False
        elif sequence(event) is not None and sequence(settlement) is not None and sequence(event) <= sequence(settlement):
            problems.append("RewardDistributed must occur after terminal MarketSettled")
            market_ok = False

    failure_certificate_event_ids = [
        event["_event_id"] for event in events if event.get("event_type") == "FailureCertificate"
    ]
    failure_memory_ok = bool(failure_certificate_event_ids)
    if not failure_memory_ok:
        problems.append("FailureCertificate lineage required")

    return {
        "status": "PASS" if not problems else "FAIL",
        "instance_id": instance_id,
        "bundle_hash": bundle_hash,
        "event_count": len(events),
        "solved": solved,
        "official_pass_count": len(official_passes),
        "official_fail_count": len(official_failures),
        "candidate_accepted_event_id": event_id(terminal_accept),
        "terminal_event_id": event_id(terminal_event),
        "total_cost_tokens": total_cost,
        "cost_source_kind": cost_source["cost_source_kind"],
        "provider_reported_cost": cost_source["provider_reported"],
        "vpput_cost_completeness": cost_source["vpput_cost_completeness"],
        "final_pput_count": len(final_pputs),
        "final_pput_event_ids": final_pput_ids,
        "market_settled_event_ids": market_settled_event_ids,
        "reward_event_ids": reward_event_ids,
        "failure_certificate_event_ids": failure_certificate_event_ids,
        "market_terminal_ordering": market_ok,
        "failure_memory_lineage": failure_memory_ok,
        "no_hitl": not any(problem.endswith("must be 0") or "fallback_to_auto" in problem for problem in problems),
        "problems": problems,
    }


def compare_existing_aggregate(root: Path, computed: dict[str, Any]) -> list[str]:
    path = root / "stage16_aggregate_report.json"
    if not path.exists():
        return []
    existing = load_json(path)
    problems: list[str] = []
    for key in [
        "run_count",
        "solved_count",
        "unsolved_count",
        "stage16_replay_campaign_pass",
        "stage16_full_pass_claim_allowed",
    ]:
        if existing.get(key) != computed.get(key):
            problems.append(f"stage16 aggregate {key} mismatch existing={existing.get(key)!r} recomputed={computed.get(key)!r}")
    if existing.get("stage16_full_pass_claim_allowed") is True and computed.get("unsolved_count", 0) > 0:
        problems.append("full-pass claim forbidden when unsolved_count > 0")
    return problems


def audit_stage16(root: Path) -> dict[str, Any]:
    coverage = load_json(root / "substrate_coverage.json")
    task_manifest = load_json(root / "task_manifest.json")
    strict_path = root / "micro_tape_audit_strict/micro_tape_decision_dag_audit.json"
    strict = load_json(strict_path) if strict_path.exists() else {}
    strict_summary = strict.get("status_summary", strict)
    if not isinstance(strict_summary, dict):
        strict_summary = {}
    problems = strict_problems(strict_summary)
    claim_path = root / "CLAIM_BOUNDARY.json"
    if claim_path.exists():
        claim = load_json(claim_path)
        for key, value in STAGE16_CLAIM_BOUNDARY.items():
            if claim.get(key) != value:
                problems.append(f"CLAIM_BOUNDARY {key} must be {value!r}")
    else:
        problems.append("CLAIM_BOUNDARY.json missing")

    runs = coverage.get("turingos_arm_runs")
    if not isinstance(runs, list):
        runs = []
        problems.append("turingos_arm_runs missing")
    expected_ids = task_manifest.get("instance_ids")
    if isinstance(expected_ids, list) and [run.get("instance_id") for run in runs] != expected_ids:
        problems.append("run order must match task_manifest.instance_ids")

    auditor = load_micro_tape_auditor()
    with tempfile.TemporaryDirectory(prefix="turingos-stage16-audit-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), index) for index, run in enumerate(runs) if isinstance(run, dict)]
    problems.extend(problem for report in run_reports for problem in report.get("problems", []))

    solved_count = sum(1 for report in run_reports if report.get("solved") is True)
    unsolved_count = len(run_reports) - solved_count
    stage16_replay_campaign_pass = bool(run_reports) and not problems and all(report["status"] == "PASS" for report in run_reports)
    full_pass_allowed = stage16_replay_campaign_pass and unsolved_count == 0
    claim_boundary = (
        "sealed replay campaign with full-score claim allowed"
        if full_pass_allowed
        else "sealed replay campaign; no full-score claim because unsolved_count > 0"
    )
    computed = {
        "schema_id": "Stage16SealedCampaignAudit.v1",
        "status": "PASS" if stage16_replay_campaign_pass else "FAIL",
        "stage16_replay_campaign_pass": stage16_replay_campaign_pass,
        "stage16_full_pass_claim_allowed": full_pass_allowed,
        "claim_boundary": claim_boundary,
        "run_count": len(run_reports),
        "solved_count": solved_count,
        "unsolved_count": unsolved_count,
        "strict_status_summary": strict_summary,
        "runs": run_reports,
        "problems": list(problems),
        "full_score_claim_gate": {
            "status": "PASS" if (full_pass_allowed or unsolved_count > 0) else "FAIL",
            "unsolved_count": unsolved_count,
            "full_pass_claim_allowed": full_pass_allowed,
        },
    }
    computed["problems"].extend(compare_existing_aggregate(root, computed))
    if computed["problems"]:
        computed["status"] = "FAIL"
        computed["stage16_replay_campaign_pass"] = False
    return computed


def write_stage16_reports(root: Path, report: dict[str, Any]) -> None:
    write_json(root / "CLAIM_BOUNDARY.json", STAGE16_CLAIM_BOUNDARY)
    write_json(root / "stage16_aggregate_report.json", report)
    write_json(
        root / "stage16_vpput_report.json",
        {
            "schema_id": "Stage16VPPUTReport.v1",
            "status": "PASS" if report["status"] == "PASS" else "FAIL",
            "solved_count": report["solved_count"],
            "unsolved_count": report["unsolved_count"],
            "runs": [
                {
                    "instance_id": run["instance_id"],
                    "solved": run["solved"],
                    "total_cost_tokens": run["total_cost_tokens"],
                    "progress": 1 if run["solved"] else 0,
                    "cost_source_kind": run["cost_source_kind"],
                    "provider_reported_cost": run["provider_reported_cost"],
                    "vpput_cost_completeness": run["vpput_cost_completeness"],
                    "final_pput_event_ids": run["final_pput_event_ids"],
                }
                for run in report["runs"]
            ],
        },
    )
    write_json(
        root / "stage16_replay_audit.json",
        {
            "schema_id": "Stage16ReplayAudit.v1",
            "status": "PASS" if report["status"] == "PASS" else "FAIL",
            "strict_status_summary": report["strict_status_summary"],
            "bundle_count": report["run_count"],
        },
    )
    write_json(
        root / "stage16_market_audit.json",
        {
            "schema_id": "Stage16MarketAudit.v1",
            "status": "PASS" if all(run["market_terminal_ordering"] for run in report["runs"]) else "FAIL",
            "terminal_ordering_checked": True,
            "per_instance": [
                {
                    "instance_id": run["instance_id"],
                    "terminal_event_id": run["terminal_event_id"],
                    "market_settled_event_ids": run["market_settled_event_ids"],
                    "reward_event_ids": run["reward_event_ids"],
                    "final_pput_event_ids": run["final_pput_event_ids"],
                }
                for run in report["runs"]
            ],
        },
    )
    write_json(
        root / "stage16_failure_memory_audit.json",
        {
            "schema_id": "Stage16FailureMemoryAudit.v1",
            "status": "PASS" if all(run["failure_memory_lineage"] for run in report["runs"]) else "FAIL",
            "lineage_checked_from_bundles": True,
            "per_instance": [
                {
                    "instance_id": run["instance_id"],
                    "terminal_event_id": run["terminal_event_id"],
                    "failure_certificate_event_ids": run["failure_certificate_event_ids"],
                }
                for run in report["runs"]
            ],
        },
    )
    write_json(
        root / "stage16_no_hitl_audit.json",
        {
            "schema_id": "Stage16NoHITLAudit.v1",
            "status": "PASS" if all(run["no_hitl"] for run in report["runs"]) else "FAIL",
            "human_intervention_count": 0,
            "manual_patch_count": 0,
            "manual_approval_count": 0,
            "fallback_to_auto_authorization": False,
            "per_instance": [
                {
                    "instance_id": run["instance_id"],
                    "no_hitl": run["no_hitl"],
                    "terminal_event_id": run["terminal_event_id"],
                }
                for run in report["runs"]
            ],
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root)
    report = audit_stage16(root)
    write_stage16_reports(Path(args.out_dir), report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit Stage15 multi-agent MarketRouter evidence."""

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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def payload(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("payload")
    return value if isinstance(value, dict) else {}


def fetch_events(coverage: dict[str, Any], auditor: Any, work_root: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, run in enumerate(coverage.get("turingos_arm_runs", [])):
        if not isinstance(run, dict) or not isinstance(run.get("micro_tape_bundle"), str):
            continue
        git_dir, _ = auditor.fetch_bundle(Path(run["micro_tape_bundle"]), work_root / f"stage15_run_{index}")
        events.extend(auditor.read_event_chain(git_dir))
    return events


def event_id(event: dict[str, Any]) -> str:
    value = event.get("_event_id") or event.get("event_id")
    return value if isinstance(value, str) else ""


def positive_int(value: Any) -> int:
    return value if isinstance(value, int) and value >= 0 and not isinstance(value, bool) else 0


def sequence(event: dict[str, Any]) -> int | None:
    value = event.get("sequence")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def route_suggestions_from_price_events(price_broadcasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for event in price_broadcasts:
        for suggestion in payload(event).get("route_suggestions", []):
            if isinstance(suggestion, dict):
                item = dict(suggestion)
                item["price_event_id"] = event_id(event)
                item["price_event_sequence"] = sequence(event)
                item["basis_event_ids"] = payload(event).get("basis_event_ids", [])
                item["stats_source"] = payload(event).get("stats_source")
                item["authority"] = payload(event).get("authority")
                item["price_not_truth_ack"] = payload(event).get("price_not_truth_ack")
                suggestions.append(item)
    return suggestions


def audit_market_router_evidence(coverage: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    meta = coverage.get("market_router")
    problems: list[str] = []
    if not isinstance(meta, dict):
        meta = {}
        problems.append("market_router metadata missing")

    by_id = {event_id(event): event for event in events if event_id(event)}
    price_broadcasts = [event for event in events if event.get("event_type") == "MarketPriceBroadcast"]
    route_suggestions = route_suggestions_from_price_events(price_broadcasts)
    budget_events = [event for event in events if event.get("event_type") == "BudgetAllocated"]
    dispatch_events = [event for event in events if event.get("event_type") == "WorkerDispatchAuthorized"]
    receipt_events = [event for event in events if event.get("event_type") == "WorkerReceiptImported"]
    route_types = sorted(
        {
            route
            for route in (
                [suggestion.get("route_type") for suggestion in route_suggestions]
                + [payload(event).get("route_type") for event in budget_events]
                + [payload(event).get("route_type") for event in dispatch_events]
                + [payload(event).get("route_type") for event in receipt_events]
            )
            if isinstance(route, str) and route
        }
    )
    route_types_count = len(set(route_types))
    if route_types_count < 2:
        problems.append("at least two route types required")

    policy = meta.get("route_diversity_policy")
    if not isinstance(policy, dict):
        policy = {}
        problems.append("route_diversity_policy missing")
    min_routes = positive_int(policy.get("min_route_types_per_batch")) or 2
    max_share = policy.get("max_budget_share_per_route")
    exploration_floor = policy.get("exploration_budget_floor")
    if route_types_count < min_routes:
        problems.append("route diversity floor not met")
    if not isinstance(max_share, (int, float)) or max_share <= 0 or max_share >= 1:
        problems.append("max_budget_share_per_route must be between 0 and 1")
    if not isinstance(exploration_floor, (int, float)) or exploration_floor <= 0 or exploration_floor >= 1:
        problems.append("exploration_budget_floor must be between 0 and 1")

    price_by_id = {event_id(event): event for event in price_broadcasts}
    suggested_routes = {
        (suggestion.get("price_event_id"), suggestion.get("route_type"))
        for suggestion in route_suggestions
        if isinstance(suggestion.get("route_type"), str)
    }
    decisions: list[dict[str, Any]] = []
    for event in budget_events:
        event_payload = payload(event)
        route_type = event_payload.get("route_type")
        price_event_id = event_payload.get("market_router_suggestion_event_id")
        price_event = price_by_id.get(price_event_id)
        allocation_reason = event_payload.get("allocation_reason")
        if not isinstance(allocation_reason, dict):
            allocation_reason = {}
        decision = {
            "route_type": route_type,
            "stats_source": payload(price_event).get("stats_source") if isinstance(price_event, dict) else allocation_reason.get("stats_source"),
            "basis_event_ids": payload(price_event).get("basis_event_ids") if isinstance(price_event, dict) else [],
            "authority": payload(price_event).get("authority") if isinstance(price_event, dict) else None,
            "affects": "budget_dispatch_suggestion_only",
            "price_event_id": price_event_id,
            "budget_event_id": event_id(event),
        }
        decisions.append(decision)
        if price_event is None:
            problems.append("route decision price event must resolve from tape")
        elif (price_event_id, route_type) not in suggested_routes:
            problems.append("BudgetAllocated route must be present in MarketPriceBroadcast suggestions")
    if not decisions:
        problems.append("route decisions missing from tape BudgetAllocated events")
    selected_routes = [decision.get("route_type") for decision in decisions if isinstance(decision, dict)]
    if len(set(selected_routes)) < min_routes:
        problems.append("route diversity floor not met")
    for decision in decisions:
        if not isinstance(decision, dict):
            problems.append("route_decision must be object")
            continue
        if decision.get("stats_source") != "micro_tape_terminal_history":
            problems.append("route decision must derive from tape historical stats")
        if decision.get("authority") is not False:
            problems.append("MarketRouter route decision must have no authority")
        if decision.get("affects") != "budget_dispatch_suggestion_only":
            problems.append("route choice must affect budget/dispatch suggestion only")
        if not isinstance(decision.get("basis_event_ids"), list) or not decision["basis_event_ids"]:
            problems.append("route decision missing basis_event_ids")
        for basis_event_id in decision.get("basis_event_ids", []):
            basis_event = by_id.get(basis_event_id)
            price_event = by_id.get(decision.get("price_event_id"))
            if basis_event is None:
                problems.append("route decision basis_event_id must resolve from tape")
                continue
            if price_event is not None and sequence(basis_event) is not None and sequence(price_event) is not None:
                if sequence(basis_event) >= sequence(price_event):
                    problems.append("route decision basis event must precede MarketPriceBroadcast")

    budget_by_route: dict[str, int] = {}
    for event in budget_events:
        route_type = payload(event).get("route_type")
        if isinstance(route_type, str):
            budget_by_route[route_type] = budget_by_route.get(route_type, 0) + positive_int(payload(event).get("max_tokens"))
    if not budget_by_route:
        problems.append("budget_by_route missing from tape BudgetAllocated events")
    total_budget = sum(positive_int(value) for value in budget_by_route.values())
    if total_budget <= 0:
        problems.append("total route budget must be positive")
    elif isinstance(max_share, (int, float)):
        for route, budget in budget_by_route.items():
            if positive_int(budget) / total_budget > max_share:
                problems.append(f"budget share for {route} exceeds diversity cap")

    terminal_settlements: dict[str, dict[str, Any]] = {}
    reputation_updates: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") == "RewardDistributed":
            event_payload = payload(event)
            reputation_updates.append(
                {
                    "agent_id": event_payload.get("agent_id"),
                    "route_type": event_payload.get("route_type"),
                    "basis_kind": "terminal_vpput" if event_payload.get("reason") == "TERMINAL_VPPUT_REPUTATION" else event_payload.get("reason"),
                    "terminal_event_id": payload(by_id.get(event_payload.get("settlement_event_id"), {})).get("terminal_event_id"),
                    "reward_event_id": event_id(event),
                }
            )
    if not reputation_updates:
        problems.append("reputation_updates missing from tape RewardDistributed events")
    for update in reputation_updates:
        if not isinstance(update, dict):
            problems.append("reputation update must be object")
            continue
        if update.get("basis_kind") != "terminal_vpput":
            problems.append("reputation must consume terminal VPPUT only")
        if update.get("terminal_event_id") is None:
            problems.append("reputation update missing terminal_event_id")

    if not price_broadcasts:
        problems.append("MarketPriceBroadcast missing")
    for event in price_broadcasts:
        event_payload = payload(event)
        if event.get("head_effect") != "PRESERVE":
            problems.append("MarketPriceBroadcast must preserve heads")
        if event_payload.get("price_not_truth_ack") is not True:
            problems.append("MarketPriceBroadcast must acknowledge price_not_truth")
        if event_payload.get("authority") is not False:
            problems.append("MarketPriceBroadcast must have no authority")
        basis_ids = event_payload.get("basis_event_ids")
        if not isinstance(basis_ids, list) or not basis_ids:
            problems.append("MarketPriceBroadcast missing tape basis_event_ids")
        for basis_event_id in basis_ids if isinstance(basis_ids, list) else []:
            basis_event = by_id.get(basis_event_id)
            if basis_event is None:
                problems.append("MarketPriceBroadcast basis_event_id must resolve from tape")
                continue
            if sequence(basis_event) is not None and sequence(event) is not None and sequence(basis_event) >= sequence(event):
                problems.append("MarketPriceBroadcast basis event must precede price broadcast")

    market_moved_accepted_head = any(
        event.get("event_type") in {"MarketPriceBroadcast", "MarketSettled", "RewardDistributed", "BudgetAllocated"}
        and event.get("head_effect") != "PRESERVE"
        for event in events
    )
    if market_moved_accepted_head:
        problems.append("market event moved accepted_head")

    for event in events:
        if event.get("event_type") != "MarketSettled":
            continue
        event_payload = payload(event)
        if event_payload.get("is_terminal") is not True:
            problems.append("MarketSettled must be terminal")
        basis = event_payload.get("settlement_basis_event_id")
        terminal = event_payload.get("terminal_event_id")
        if basis not in by_id or terminal not in by_id:
            problems.append("MarketSettled basis/terminal ids must resolve")
        else:
            basis_seq = sequence(by_id[basis])
            terminal_seq = sequence(by_id[terminal])
            settlement_seq = sequence(event)
            if basis_seq is not None and settlement_seq is not None and settlement_seq <= basis_seq:
                problems.append("MarketSettled must occur after settlement basis event")
            if terminal_seq is not None and settlement_seq is not None and settlement_seq <= terminal_seq:
                problems.append("MarketSettled must occur after terminal accept/failure event")
            terminal_settlements[event_id(event)] = event
    for event in events:
        if event.get("event_type") != "RewardDistributed":
            continue
        settlement_event = terminal_settlements.get(payload(event).get("settlement_event_id"))
        if settlement_event is None:
            problems.append("RewardDistributed must reference terminal MarketSettled")
        elif sequence(event) is not None and sequence(settlement_event) is not None and sequence(event) <= sequence(settlement_event):
            problems.append("RewardDistributed must occur after terminal MarketSettled")

    cost_events = [payload(event) for event in events if event.get("event_type") == "CostEvent"]
    final_pputs = [
        payload(event)
        for event in events
        if event.get("event_type") == "PPUTAccounted" and payload(event).get("accounting_stage") == "final"
    ]
    if not cost_events or not final_pputs:
        problems.append("CostEvent and final PPUTAccounted required")
    else:
        total_cost = sum(positive_int(event.get("total_tokens")) for event in cost_events)
        if not any(pput.get("total_run_token_count") == total_cost for pput in final_pputs):
            problems.append("all route/abandoned branch costs must count in final VPPUT")

    market_router_status = "FAIL" if any("route decision" in problem or "MarketRouter" in problem for problem in problems) else "PASS"
    route_diversity_status = "FAIL" if any("diversity" in problem or "budget share" in problem for problem in problems) else "PASS"
    reputation_status = "FAIL" if any("reputation" in problem for problem in problems) else "PASS"
    price_not_truth_status = "FAIL" if any("price" in problem.lower() or "market event moved" in problem for problem in problems) else "PASS"
    cost_status = "FAIL" if any("cost" in problem.lower() or "vpput" in problem.lower() for problem in problems) else "PASS"
    status = "PASS" if not problems else "FAIL"
    return {
        "schema_id": "Stage15MarketRouterAudit.v1",
        "status": status,
        "truth_source": "micro_tape_bundles_replayed_events",
        "problems": problems,
        "route_types_count": route_types_count,
        "market_moved_accepted_head": market_moved_accepted_head,
        "market_router": {
            "status": market_router_status,
            "route_decisions": decisions,
        },
        "route_diversity": {
            "status": route_diversity_status,
            "route_types": route_types,
            "route_diversity_policy": policy,
            "budget_by_route": budget_by_route,
        },
        "agent_reputation": {
            "status": reputation_status,
            "reputation_updates": reputation_updates,
        },
        "price_not_truth": {
            "status": price_not_truth_status,
            "price_broadcast_count": len(price_broadcasts),
            "market_moved_accepted_head": market_moved_accepted_head,
        },
        "branch_cost_conservation": {
            "status": cost_status,
            "cost_event_count": len(cost_events),
            "final_pput_count": len(final_pputs),
        },
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    auditor = load_micro_tape_auditor()
    with tempfile.TemporaryDirectory(prefix="turingos-market-router-") as temp:
        events = fetch_events(coverage, auditor, Path(temp))
    return audit_market_router_evidence(coverage, events)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    report = audit_coverage(Path(args.coverage))
    out_dir = Path(args.out_dir)
    write_json(out_dir / "market_router_audit.json", report)
    write_json(out_dir / "route_diversity_audit.json", report["route_diversity"])
    write_json(out_dir / "agent_reputation_audit.json", report["agent_reputation"])
    write_json(out_dir / "price_not_truth_audit.json", report["price_not_truth"])
    write_json(out_dir / "branch_cost_conservation_audit.json", report["branch_cost_conservation"])
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

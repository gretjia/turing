#!/usr/bin/env python3
"""Compute M4 H-VPPUT from receipts, outcomes, and a held-out registry."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any


BILLING_KINDS = {"provider_receipt_inline", "provider_usage_api_reconciled"}
BOUNDED_KIND = "bounded_estimate"
ENUM_KINDS = BILLING_KINDS | {BOUNDED_KIND, "fixture"}
REQUIRED_INLINE_FIELDS = (
    "usage",
    "usage_schema",
    "provider",
    "model_reported",
    "provider_request_id",
    "request_sha256",
    "response_sha256",
    "price_table_digest",
    "computed_cost_microusd",
    "wall_clock_ms",
)
USAGE_SCHEMA_FIELDS = {
    "openai_chat_v1": ("prompt_tokens", "completion_tokens", "total_tokens"),
    "xai_openai_compat_v1": ("prompt_tokens", "completion_tokens", "total_tokens"),
    "anthropic_messages_v1": (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ),
    "deepseek_chat_v1": (
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "output_tokens",
    ),
}


class MetricError(Exception):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"


def require_int(value: Any, field: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise MetricError(f"invalid_integer:{field}")
    return value


def require_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise MetricError(f"invalid_sha256:{field}")
    return value


def read_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]:
    if args.fixture:
        fixture = Path(args.fixture)
        return (
            load_json(fixture / "registry.json"),
            load_json(fixture / "receipts.json"),
            load_json(fixture / "results.json"),
            load_json(fixture / "price_table.json"),
            "FIXTURE",
        )
    missing = [
        name
        for name in ("registry", "receipts", "results", "price_table")
        if getattr(args, name) is None
    ]
    if missing:
        raise MetricError(f"missing_inputs:{','.join(missing)}")
    return (
        load_json(Path(args.registry)),
        load_json(Path(args.receipts)),
        load_json(Path(args.results)),
        load_json(Path(args.price_table)),
        args.run_kind,
    )


def registry_ids(registry: dict[str, Any]) -> set[str]:
    ids = registry.get("instance_ids")
    if not isinstance(ids, list) or not all(isinstance(item, str) and item for item in ids):
        raise MetricError("invalid_registry:instance_ids")
    return set(ids)


def resolved_ids(results: dict[str, Any]) -> set[str]:
    resolved = results.get("resolved_tasks", [])
    if not isinstance(resolved, list) or not all(isinstance(item, str) for item in resolved):
        raise MetricError("invalid_results:resolved_tasks")
    return set(resolved)


def price_index(price_table: dict[str, Any]) -> tuple[str, dict[tuple[str, str, str], int]]:
    digest = require_sha(price_table.get("price_table_digest"), "price_table_digest")
    rows = price_table.get("prices")
    if not isinstance(rows, list):
        raise MetricError("invalid_price_table:prices")
    indexed: dict[tuple[str, str, str], int] = {}
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise MetricError(f"invalid_price_row:{idx}")
        key = (
            str(row.get("provider")),
            str(row.get("model")),
            str(row.get("token_class")),
        )
        indexed[key] = require_int(row.get("microusd_per_mtok"), f"price_row[{idx}].microusd_per_mtok")
    return digest, indexed


def ceiling_cost_microusd(tokens: int, microusd_per_mtok: int) -> int:
    numerator = tokens * microusd_per_mtok
    return (numerator + 1_000_000 - 1) // 1_000_000


def verify_inline_receipt(event: dict[str, Any], table_digest: str, prices: dict[tuple[str, str, str], int]) -> None:
    event_ref = str(event.get("event_ref", event.get("receipt_id", "<unknown>")))
    for field in REQUIRED_INLINE_FIELDS:
        if field not in event:
            raise MetricError(f"provider_receipt_inline_missing_field:{event_ref}:{field}")
    for field in ("model_reported", "provider_request_id"):
        if not isinstance(event.get(field), str) or not event[field]:
            raise MetricError(f"provider_receipt_inline_missing_field:{event_ref}:{field}")
    require_sha(event["request_sha256"], "request_sha256")
    require_sha(event["response_sha256"], "response_sha256")
    if event["price_table_digest"] != table_digest:
        raise MetricError(f"price_table_digest_mismatch:{event_ref}")
    usage = event["usage"]
    if not isinstance(usage, dict):
        raise MetricError(f"provider_receipt_inline_missing_field:{event_ref}:usage")
    usage_schema = event["usage_schema"]
    if usage_schema not in USAGE_SCHEMA_FIELDS:
        raise MetricError(f"unknown_usage_schema:{event_ref}:{usage_schema}")
    for field in USAGE_SCHEMA_FIELDS[usage_schema]:
        require_int(usage.get(field), f"{event_ref}.usage.{field}")
    provider = str(event["provider"])
    model = str(event["model_reported"])
    cost_numerator = 0
    for field in USAGE_SCHEMA_FIELDS[usage_schema]:
        key = (provider, model, field)
        if key not in prices:
            raise MetricError(f"missing_price:{event_ref}:{provider}:{model}:{field}")
        cost_numerator += int(usage[field]) * prices[key]
    recomputed = (cost_numerator + 1_000_000 - 1) // 1_000_000
    if recomputed != require_int(event.get("computed_cost_microusd"), f"{event_ref}.computed_cost_microusd"):
        raise MetricError(f"cost_recompute_mismatch:{event_ref}:expected_{recomputed}")


def event_kind(event: dict[str, Any]) -> str | None:
    value = event.get("cost_source_kind")
    return value if isinstance(value, str) else None


def exclusion_reason(kind: str | None, run_kind: str) -> str:
    if kind is None:
        return "cost_source_kind=<absent> (missing)"
    if kind == "fixture" and run_kind == "REAL":
        return "cost_source_kind=fixture (fixture-in-real)"
    if kind not in ENUM_KINDS:
        return f"cost_source_kind={kind} (non-enum)"
    return f"cost_source_kind={kind} (inadmissible)"


def classify_task(
    task: str,
    events: list[dict[str, Any]],
    run_kind: str,
    table_digest: str,
    prices: dict[tuple[str, str, str], int],
) -> tuple[str, str | None, int, int]:
    has_bounded = False
    total_cost = 0
    total_wall = 0
    for event in events:
        kind = event_kind(event)
        if kind not in ENUM_KINDS or kind == "fixture" or kind is None:
            if kind == "fixture" and run_kind == "FIXTURE":
                return "INADMISSIBLE", "cost_source_kind=fixture (fixture-only event)", 0, 0
            return "INADMISSIBLE", exclusion_reason(kind, run_kind), 0, 0
        if kind in BILLING_KINDS:
            if kind == "provider_receipt_inline":
                verify_inline_receipt(event, table_digest, prices)
            total_cost += require_int(event.get("computed_cost_microusd"), f"{task}.computed_cost_microusd")
            total_wall += require_int(event.get("wall_clock_ms"), f"{task}.wall_clock_ms")
            continue
        if kind == BOUNDED_KIND:
            bound_kind = event.get("bound_kind")
            if not isinstance(bound_kind, str) or not bound_kind:
                raise MetricError(f"bounded_estimate_missing_bound_kind:{task}")
            has_bounded = True
            total_cost += require_int(event.get("computed_cost_microusd"), f"{task}.computed_cost_microusd")
            total_wall += require_int(event.get("wall_clock_ms"), f"{task}.wall_clock_ms")
    return ("BOUNDED" if has_bounded else "BILLING_COMPLETE"), None, total_cost, total_wall


def hvpput_m_str(solves: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000000000"
    scaled = (solves * 1_000_000 * 1_000_000_000) // denominator
    return f"{scaled // 1_000_000_000}.{scaled % 1_000_000_000:09d}"


def task_groups(receipts: dict[str, Any], ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    events = receipts.get("events")
    if not isinstance(events, list):
        raise MetricError("invalid_receipts:events")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            raise MetricError(f"invalid_event:{idx}")
        task = event.get("task") or event.get("problem_id")
        if not isinstance(task, str) or not task:
            raise MetricError(f"invalid_event_task:{idx}")
        if task not in ids:
            raise MetricError(f"out_of_registry:{task}")
        grouped.setdefault(task, []).append(event)
    return grouped


def compute_report(
    registry: dict[str, Any],
    receipts: dict[str, Any],
    results: dict[str, Any],
    price_table: dict[str, Any],
    run_kind: str,
) -> dict[str, Any]:
    ids = registry_ids(registry)
    resolved = resolved_ids(results)
    table_digest, prices = price_index(price_table)
    grouped = task_groups(receipts, ids)
    complete = {"solves": 0, "cost": 0, "wall": 0, "n": 0}
    bounded = {"solves": 0, "cost": 0, "wall": 0, "n": 0}
    exclusions: list[dict[str, str]] = []
    for task in sorted(grouped):
        task_class, reason, cost, wall = classify_task(task, grouped[task], run_kind, table_digest, prices)
        if task_class == "INADMISSIBLE":
            exclusions.append({"reason": str(reason), "task": task})
            continue
        target = bounded if task_class == "BOUNDED" else complete
        target["n"] += 1
        target["solves"] += 1 if task in resolved else 0
        target["cost"] += cost
        target["wall"] += wall
    complete_den = complete["cost"] * complete["wall"]
    bounded_den = bounded["cost"] * bounded["wall"]
    return {
        "billing_complete_portfolio": {
            "hvpput_m_str": hvpput_m_str(complete["solves"], complete_den),
            "hvpput_pair": {
                "denominator_microusd_ms": complete_den,
                "numerator_solves": complete["solves"],
            },
            "solves_per_dollar_e6_str": str((complete["solves"] * 10**12) // max(1, complete["cost"])),
            "total_cost_microusd": complete["cost"],
            "total_solves": complete["solves"],
            "total_wall_ms": complete["wall"],
        },
        "bounded_portfolio": {
            "hvpput_bound_kind": "lower_bound_via_cost_upper_bound",
            "hvpput_pair": {
                "denominator_microusd_ms": bounded_den,
                "numerator_solves": bounded["solves"],
            },
            "total_cost_microusd_upper_bound": bounded["cost"],
            "total_solves": bounded["solves"],
            "total_wall_ms": bounded["wall"],
        },
        "class_breakdown": {
            "n_billing_complete": complete["n"],
            "n_bounded": bounded["n"],
            "n_excluded": len(exclusions),
        },
        "exclusions": exclusions,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", help="fixture directory containing registry/receipts/results/price_table JSON")
    parser.add_argument("--registry")
    parser.add_argument("--receipts")
    parser.add_argument("--results")
    parser.add_argument("--price-table")
    parser.add_argument("--run-kind", choices=("REAL", "FIXTURE"), default="REAL")
    parser.add_argument("--out")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = compute_report(*read_inputs(args))
        text = dump_json(report)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    except (OSError, json.JSONDecodeError, KeyError, MetricError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

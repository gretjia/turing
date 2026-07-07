"""CostEvent.v2 helpers at the WorkerAdapter seam.

CostEvent.v2 is a supervisor-side tape payload. It binds an adapter receipt to
provider identity, usage provenance, a pinned price table digest, and integer
micro-USD cost. Worker-safe prompts must not include these details.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import codec, schemas

COST_EVENT_SCHEMA_ID = schemas.COST_EVENT_V2_SCHEMA_ID
PRICE_TABLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "pack"
    / "04_registries"
    / "price_table_m1c_20260702.json"
)

_FORBIDDEN_SECRET_PARTS = ("authorization", "api_key", "api-key", "x-api-key", "password")


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_price_table(path: Path = PRICE_TABLE_PATH) -> dict[str, Any]:
    table = _load_json(path)
    if table.get("schema_id") != "turingos.price_table.v1":
        raise ValueError("price table schema_id must be turingos.price_table.v1")
    prices = table.get("prices")
    if not isinstance(prices, list) or not prices:
        raise ValueError("price table must contain at least one price row")
    seen = set()
    for idx, row in enumerate(prices):
        if not isinstance(row, dict):
            raise ValueError(f"price row {idx} must be an object")
        key = (row.get("provider"), row.get("model"), row.get("token_class"))
        if not all(isinstance(item, str) and item for item in key):
            raise ValueError(f"price row {idx} must key provider/model/token_class")
        if key in seen:
            raise ValueError(f"duplicate price key {key!r}")
        seen.add(key)
        unit = row.get("unit_microusd_per_mtok")
        if isinstance(unit, bool) or not isinstance(unit, int) or unit < 0:
            raise ValueError(f"price row {idx} unit_microusd_per_mtok must be nonnegative integer")
    codec.canonical_bytes(table)
    return table


def price_table_digest(table: dict[str, Any] | None = None) -> str:
    return codec.content_digest(table if table is not None else load_price_table())


PRICE_TABLE_DIGEST = price_table_digest()


def upper_bound_tokens_from_utf8_bytes(text: str, *, bytes_per_token_floor: int = 2) -> int:
    if bytes_per_token_floor <= 0:
        raise ValueError("bytes_per_token_floor must be positive")
    byte_len = len(text.encode("utf-8"))
    return (byte_len + bytes_per_token_floor - 1) // bytes_per_token_floor


def _reject_secretish_material(value: Any, *, where: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_l = str(key).lower()
            if any(part in key_l for part in _FORBIDDEN_SECRET_PARTS):
                raise ValueError(f"{where}: secret-bearing key is forbidden: {key!r}")
            _reject_secretish_material(child, where=f"{where}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            _reject_secretish_material(child, where=f"{where}[{idx}]")
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise ValueError(f"{where}: bearer credential value is forbidden")


def cost_event_from_receipt(
    receipt: dict[str, Any],
    *,
    run_id: str,
    problem_id: str,
    split: str,
    agent_id: str,
    branch_id: str,
    adapter_kind: str,
    provider: str,
    model_id_requested: str,
    model_id_resolved: str,
    endpoint: str,
    request_id: str,
    response_sha256: str,
    usage: dict[str, Any],
    cost_source_kind: str,
    cost_microusd: int,
    wall_time_ms: int,
    provider_usage_raw: dict[str, Any] | None = None,
    price_table_digest_value: str = PRICE_TABLE_DIGEST,
    bound_kind: str | None = None,
) -> dict[str, Any]:
    """Build and validate a CostEvent.v2 payload from a worker receipt."""
    schemas.validate_receipt(receipt)
    usage_raw = provider_usage_raw if provider_usage_raw is not None else usage
    _reject_secretish_material(usage_raw, where="provider_usage_raw")

    usage_payload = dict(usage)
    usage_payload["provider_usage_raw_sha256"] = codec.content_digest(usage_raw)

    payload: dict[str, Any] = {
        "schema_id": COST_EVENT_SCHEMA_ID,
        "run_id": run_id,
        "problem_id": problem_id,
        "split": split,
        "agent_id": agent_id,
        "branch_id": branch_id,
        "capsule_id": receipt["capsule_id"],
        "receipt_id": receipt["receipt_id"],
        "worker": {
            "adapter_kind": adapter_kind,
            "provider": provider,
            "model_id_requested": model_id_requested,
            "model_id_resolved": model_id_resolved,
            "endpoint": endpoint,
            "request_id": request_id,
            "response_sha256": response_sha256,
        },
        "usage": usage_payload,
        "cost": {
            "cost_source_kind": cost_source_kind,
            "cost_microusd": cost_microusd,
            "price_table_digest": price_table_digest_value,
            "bound_kind": bound_kind,
        },
        "wall_time_ms": wall_time_ms,
    }
    schemas.validate_cost_event_v2(payload)
    return payload

#!/usr/bin/env python3
"""Run a sanitized DeepSeek provider canary for M3.P4.

The canary records provider-reported model and usage, then emits a
CostEvent.v2-compatible receipt without serializing API keys, Authorization
headers, raw response content, or raw reasoning content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
PLAN_ROOT = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
DEFAULT_PRICE_TABLE = PLAN_ROOT / "m3_uplift_lab" / "PRICE_TABLE.json"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_ENDPOINT = "/chat/completions"
DEFAULT_KEY_ENV = "DEEPSEEK_API_KEY"
DEFAULT_MODEL = "deepseek-v4-flash"

sys.path.insert(0, str(REPO / "src"))

from turingos import codec  # noqa: E402
from turingos.worker import cost as worker_cost  # noqa: E402


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hex_digest(value: Any) -> str:
    return codec.content_digest(value).removeprefix("sha256:")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_chat_request(
    *,
    model: str,
    prompt: str,
    thinking: str,
    reasoning_effort: str | None,
    max_tokens: int,
) -> dict[str, Any]:
    if thinking not in {"enabled", "disabled"}:
        raise ValueError("thinking must be enabled or disabled")
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a provider canary. Return a compact JSON object only.",
            },
            {"role": "user", "content": prompt},
        ],
        "thinking": {"type": thinking},
        "stream": False,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if reasoning_effort:
        if reasoning_effort not in {"high", "max"}:
            raise ValueError("reasoning_effort must be high, max, or omitted")
        body["reasoning_effort"] = reasoning_effort
    return body


def _int_field(data: dict[str, Any], key: str, default: int = 0) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"usage.{key} must be a nonnegative integer")
    return value


def normalize_deepseek_usage(raw_usage: dict[str, Any]) -> dict[str, int]:
    prompt_tokens = _int_field(raw_usage, "prompt_tokens", 0)
    completion_tokens = _int_field(raw_usage, "completion_tokens", _int_field(raw_usage, "output_tokens", 0))
    total_tokens = _int_field(raw_usage, "total_tokens", prompt_tokens + completion_tokens)

    details = raw_usage.get("prompt_tokens_details")
    cached_from_details = 0
    if isinstance(details, dict) and isinstance(details.get("cached_tokens"), int):
        cached_from_details = details["cached_tokens"]
    cache_hit = _int_field(raw_usage, "prompt_cache_hit_tokens", cached_from_details)
    cache_miss = _int_field(raw_usage, "prompt_cache_miss_tokens", max(prompt_tokens - cache_hit, 0))

    if cache_hit + cache_miss > prompt_tokens and prompt_tokens:
        raise ValueError("DeepSeek cache hit/miss tokens exceed prompt_tokens")

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_cache_hit_tokens": cache_hit,
        "prompt_cache_miss_tokens": cache_miss,
    }


def _price_row_from_m3_table(price_table: dict[str, Any], model: str) -> dict[str, int]:
    for row in price_table.get("models", []):
        if not isinstance(row, dict):
            continue
        if row.get("provider") == "deepseek" and row.get("model_id") == model:
            return {
                "prompt_cache_hit_tokens": _int_field(row, "input_cache_hit_microusd_per_mtok"),
                "prompt_cache_miss_tokens": _int_field(row, "input_cache_miss_microusd_per_mtok"),
                "completion_tokens": _int_field(row, "output_microusd_per_mtok"),
            }

    rows = price_table.get("prices", [])
    price_by_class: dict[str, int] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if row.get("provider") == "deepseek" and row.get("model") == model:
            price_by_class[str(row.get("token_class"))] = _int_field(row, "unit_microusd_per_mtok")
    required = {"prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens"}
    if required.issubset(price_by_class):
        return {key: price_by_class[key] for key in sorted(required)}

    raise ValueError(f"DeepSeek model {model!r} is not priced in the supplied price table")


def deepseek_cost_microusd(
    *,
    model: str,
    usage: dict[str, int],
    price_table: dict[str, Any],
) -> int:
    prices = _price_row_from_m3_table(price_table, model)
    numerator = (
        usage["prompt_cache_hit_tokens"] * prices["prompt_cache_hit_tokens"]
        + usage["prompt_cache_miss_tokens"] * prices["prompt_cache_miss_tokens"]
        + usage["completion_tokens"] * prices["completion_tokens"]
    )
    return (numerator + 1_000_000 - 1) // 1_000_000


def _message_from_response(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response.choices must be a non-empty list")
    first = choices[0]
    if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
        raise ValueError("response.choices[0].message must be an object")
    return first["message"]


def _receipt(
    *,
    run_id: str,
    capsule_id: str,
    model_requested: str,
    response_sha256: str,
) -> dict[str, Any]:
    receipt_hex = hex_digest(
        {
            "run_id": run_id,
            "capsule_id": capsule_id,
            "model_requested": model_requested,
            "response_sha256": response_sha256,
        }
    )
    return {
        "schema_id": "turingos.receipt.v1",
        "receipt_id": "rcpt:" + receipt_hex,
        "capsule_id": capsule_id,
        "worker_id": f"deepseek-provider-canary:{model_requested}",
        "worktree_path": "/tmp/turingos-provider-canary",
        "candidate": {
            "tree_oid": response_sha256.removeprefix("sha256:"),
            "files_touched": [],
        },
        "declared_test_results": [],
        "status": "ok",
        "no_orphan": True,
    }


def build_canary_packet(
    *,
    run_id: str,
    problem_id: str,
    split: str,
    branch_id: str,
    canary_kind: str,
    base_url: str,
    endpoint: str,
    api_key_env: str,
    model_requested: str,
    thinking: str,
    reasoning_effort: str | None,
    request_payload: dict[str, Any],
    response: dict[str, Any],
    response_raw: str,
    wall_time_ms: int,
    price_table: dict[str, Any],
    allowed_reported_models: list[str] | None = None,
) -> dict[str, Any]:
    message = _message_from_response(response)
    content = message.get("content") or ""
    if not isinstance(content, str):
        raise ValueError("response content must be a string or null")
    reasoning_content = message.get("reasoning_content")
    if reasoning_content is not None and not isinstance(reasoning_content, str):
        raise ValueError("reasoning_content must be a string or null")

    raw_usage = response.get("usage")
    if not isinstance(raw_usage, dict):
        raise ValueError("response.usage must be an object")
    usage = normalize_deepseek_usage(raw_usage)
    model_reported = str(response.get("model") or "")
    allowed = set(allowed_reported_models or [])
    allowed.add(model_requested)
    status = "PASS" if model_reported in allowed else "BLOCKED_MODEL_MISMATCH"

    response_sha256 = sha256_text(response_raw)
    request_sha256 = codec.content_digest(request_payload)
    capsule_id = "cap:" + hex_digest(
        {
            "schema_id": "DeepSeekProviderCanaryCapsule.v1",
            "run_id": run_id,
            "request_sha256": request_sha256,
        }
    )
    receipt = _receipt(
        run_id=run_id,
        capsule_id=capsule_id,
        model_requested=model_requested,
        response_sha256=response_sha256,
    )
    cost_microusd = deepseek_cost_microusd(
        model=model_requested,
        usage=usage,
        price_table=price_table,
    )
    cost_event = worker_cost.cost_event_from_receipt(
        receipt,
        run_id=run_id,
        problem_id=problem_id,
        split=split,
        agent_id=f"m3-p4-deepseek-{canary_kind}-canary",
        branch_id=branch_id,
        adapter_kind="native_api",
        provider="deepseek",
        model_id_requested=model_requested,
        model_id_resolved=model_reported or "unknown",
        endpoint=base_url.rstrip("/") + endpoint,
        request_id=str(response.get("id") or response_sha256),
        response_sha256=response_sha256,
        usage=usage,
        cost_source_kind="provider_receipt_inline",
        cost_microusd=cost_microusd,
        wall_time_ms=wall_time_ms,
        provider_usage_raw=raw_usage,
        price_table_digest_value=codec.content_digest(price_table),
    )

    return {
        "schema_id": "turingos.m3.deepseek_provider_canary.v1",
        "status": status,
        "canary_kind": canary_kind,
        "provider": "deepseek",
        "base_url": base_url,
        "endpoint": endpoint,
        "api_key_env": api_key_env,
        "credential_material": "env_only_not_serialized",
        "model_requested": model_requested,
        "model_reported": model_reported,
        "allowed_reported_models": sorted(allowed),
        "thinking": {"type": thinking},
        "reasoning_effort": reasoning_effort,
        "request_sha256": request_sha256,
        "response_sha256": response_sha256,
        "content_sha256": sha256_text(content),
        "content_length_chars": len(content),
        "reasoning_content_sha256": sha256_text(reasoning_content) if reasoning_content is not None else None,
        "reasoning_content_length_chars": len(reasoning_content) if reasoning_content is not None else 0,
        "usage": usage,
        "usage_raw_sha256": codec.content_digest(raw_usage),
        "provider_request_id": str(response.get("id") or ""),
        "cost_event": cost_event,
        "cost_source_kind": "provider_receipt_inline",
        "price_table_digest": codec.content_digest(price_table),
        "wall_time_ms": wall_time_ms,
        "claim_boundary": {
            "canary_only": True,
            "worker_authorized_for_pilot": status == "PASS" and canary_kind == "worker",
            "no_s02_prediction": True,
            "no_uplift_result": True,
        },
    }


def call_deepseek(
    *,
    base_url: str,
    endpoint: str,
    api_key: str,
    request_payload: dict[str, Any],
    timeout_s: int,
) -> tuple[dict[str, Any], str, int]:
    data = json.dumps(request_payload, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + endpoint,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        raw_bytes = response.read()
    wall_time_ms = int((time.monotonic() - start) * 1000)
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("DeepSeek response must be a JSON object")
    return parsed, raw_text, wall_time_ms


def failure_packet(
    *,
    status: str,
    reason: str,
    canary_kind: str,
    base_url: str,
    endpoint: str,
    api_key_env: str,
    model_requested: str,
    thinking: str,
    reasoning_effort: str | None,
    request_payload: dict[str, Any] | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "schema_id": "turingos.m3.deepseek_provider_canary.v1",
        "status": status,
        "reason": reason,
        "canary_kind": canary_kind,
        "provider": "deepseek",
        "base_url": base_url,
        "endpoint": endpoint,
        "api_key_env": api_key_env,
        "credential_material": "env_only_not_serialized",
        "model_requested": model_requested,
        "thinking": {"type": thinking},
        "reasoning_effort": reasoning_effort,
        "request_sha256": codec.content_digest(request_payload) if request_payload is not None else None,
        "claim_boundary": {
            "canary_only": True,
            "worker_authorized_for_pilot": False,
            "no_s02_prediction": True,
            "no_uplift_result": True,
        },
    }
    if extra:
        packet.update(extra)
    return packet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--api-key-env", default=DEFAULT_KEY_ENV)
    parser.add_argument("--thinking", choices=["enabled", "disabled"], default="disabled")
    parser.add_argument("--reasoning-effort", choices=["high", "max"])
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--price-table", type=Path, default=DEFAULT_PRICE_TABLE)
    parser.add_argument("--run-id", default="m3-p4-deepseek-provider-canary-20260703")
    parser.add_argument("--problem-id", default="m3-p4-provider-canary")
    parser.add_argument("--split", default="s02-pilot-preflight")
    parser.add_argument("--branch-id", default="branch:m3-p4")
    parser.add_argument("--canary-kind", choices=["worker", "meta_ai"], default="worker")
    parser.add_argument("--allow-reported-model", action="append", default=[])
    parser.add_argument(
        "--prompt",
        default='Return exactly {"ok":true,"provider":"deepseek"} as JSON.',
    )
    args = parser.parse_args(argv)

    request_payload = build_chat_request(
        model=args.model,
        prompt=args.prompt,
        thinking=args.thinking,
        reasoning_effort=args.reasoning_effort,
        max_tokens=args.max_tokens,
    )
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        write_json(
            args.out,
            failure_packet(
                status="NOT_RUN",
                reason=f"missing environment variable: {args.api_key_env}",
                canary_kind=args.canary_kind,
                base_url=args.base_url,
                endpoint=args.endpoint,
                api_key_env=args.api_key_env,
                model_requested=args.model,
                thinking=args.thinking,
                reasoning_effort=args.reasoning_effort,
                request_payload=request_payload,
                extra={"missing_env": [args.api_key_env]},
            ),
        )
        return 2

    try:
        price_table = load_json(args.price_table)
        response, response_raw, wall_time_ms = call_deepseek(
            base_url=args.base_url,
            endpoint=args.endpoint,
            api_key=api_key,
            request_payload=request_payload,
            timeout_s=args.timeout_s,
        )
        packet = build_canary_packet(
            run_id=args.run_id,
            problem_id=args.problem_id,
            split=args.split,
            branch_id=args.branch_id,
            canary_kind=args.canary_kind,
            base_url=args.base_url,
            endpoint=args.endpoint,
            api_key_env=args.api_key_env,
            model_requested=args.model,
            thinking=args.thinking,
            reasoning_effort=args.reasoning_effort,
            request_payload=request_payload,
            response=response,
            response_raw=response_raw,
            wall_time_ms=wall_time_ms,
            price_table=price_table,
            allowed_reported_models=args.allow_reported_model,
        )
    except urllib.error.HTTPError as error:
        error_body = error.read()
        packet = failure_packet(
            status="API_ERROR",
            reason="DeepSeek HTTP error",
            canary_kind=args.canary_kind,
            base_url=args.base_url,
            endpoint=args.endpoint,
            api_key_env=args.api_key_env,
            model_requested=args.model,
            thinking=args.thinking,
            reasoning_effort=args.reasoning_effort,
            request_payload=request_payload,
            extra={
                "http_status": error.code,
                "error_body_sha256": sha256_bytes(error_body),
            },
        )
    except Exception as error:  # noqa: BLE001 - evidence runner must record external failures.
        packet = failure_packet(
            status="ERROR",
            reason=type(error).__name__,
            canary_kind=args.canary_kind,
            base_url=args.base_url,
            endpoint=args.endpoint,
            api_key_env=args.api_key_env,
            model_requested=args.model,
            thinking=args.thinking,
            reasoning_effort=args.reasoning_effort,
            request_payload=request_payload,
            extra={"error_message": str(error)},
        )

    write_json(args.out, packet)
    return 0 if packet.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

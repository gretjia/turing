from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from turingos import schemas


REPO = Path(__file__).resolve().parents[1]
CANARY = REPO / "tools" / "bench" / "run_deepseek_provider_canary.py"


def load_canary():
    spec = importlib.util.spec_from_file_location("deepseek_provider_canary", CANARY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_chat_request_controls_thinking_without_sampling_knobs():
    canary = load_canary()

    payload = canary.build_chat_request(
        model="deepseek-v4-flash",
        prompt="Return JSON.",
        thinking="disabled",
        reasoning_effort=None,
        max_tokens=32,
    )

    assert payload["model"] == "deepseek-v4-flash"
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["stream"] is False
    assert payload["max_tokens"] == 32
    assert "temperature" not in payload
    assert "top_p" not in payload


def test_enabled_thinking_adds_reasoning_effort():
    canary = load_canary()

    payload = canary.build_chat_request(
        model="deepseek-v4-pro",
        prompt="Audit this.",
        thinking="enabled",
        reasoning_effort="high",
        max_tokens=16,
    )

    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"


def test_deepseek_usage_and_integer_cost_from_m3_table_shape():
    canary = load_canary()
    table = {
        "schema_id": "turingos.m3.price_table.v1",
        "models": [
            {
                "provider": "deepseek",
                "model_id": "deepseek-v4-flash",
                "input_cache_hit_microusd_per_mtok": 2800,
                "input_cache_miss_microusd_per_mtok": 140000,
                "output_microusd_per_mtok": 280000,
            }
        ],
    }
    raw_usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "total_tokens": 1200,
        "prompt_cache_hit_tokens": 300,
        "prompt_cache_miss_tokens": 700,
    }

    usage = canary.normalize_deepseek_usage(raw_usage)
    cost = canary.deepseek_cost_microusd(
        model="deepseek-v4-flash",
        usage=usage,
        price_table=table,
    )

    assert usage["prompt_cache_hit_tokens"] == 300
    assert usage["prompt_cache_miss_tokens"] == 700
    assert usage["completion_tokens"] == 200
    assert cost == 155


def test_canary_packet_validates_cost_event_and_scrubs_secret_material():
    canary = load_canary()
    table = {
        "schema_id": "turingos.m3.price_table.v1",
        "models": [
            {
                "provider": "deepseek",
                "model_id": "deepseek-v4-flash",
                "input_cache_hit_microusd_per_mtok": 2800,
                "input_cache_miss_microusd_per_mtok": 140000,
                "output_microusd_per_mtok": 280000,
            }
        ],
    }
    request_payload = canary.build_chat_request(
        model="deepseek-v4-flash",
        prompt="Return OK.",
        thinking="disabled",
        reasoning_effort=None,
        max_tokens=8,
    )
    response = {
        "id": "chatcmpl-unit",
        "model": "deepseek-v4-flash",
        "choices": [{"message": {"content": "OK", "reasoning_content": "hidden chain"}}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
            "prompt_cache_hit_tokens": 4,
            "prompt_cache_miss_tokens": 6,
        },
    }

    packet = canary.build_canary_packet(
        run_id="m3-p4-canary-unit",
        problem_id="m3-p4-provider-canary",
        split="s02-pilot-preflight",
        branch_id="branch:m3-p4",
        canary_kind="worker",
        base_url="https://api.deepseek.com",
        endpoint="/chat/completions",
        api_key_env="DEEPSEEK_API_KEY",
        model_requested="deepseek-v4-flash",
        thinking="disabled",
        reasoning_effort=None,
        request_payload=request_payload,
        response=response,
        response_raw=json.dumps(response, sort_keys=True),
        wall_time_ms=12,
        price_table=table,
    )

    assert packet["status"] == "PASS"
    assert packet["credential_material"] == "env_only_not_serialized"
    assert packet["model_reported"] == "deepseek-v4-flash"
    assert packet["reasoning_content_sha256"].startswith("sha256:")
    assert "hidden chain" not in json.dumps(packet, sort_keys=True)
    assert "sentinel-secret-must-not-appear" not in json.dumps(packet, sort_keys=True)
    schemas.validate_cost_event_v2(packet["cost_event"])

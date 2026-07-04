#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
M4="$ROOT/m4_self_improvement"
BUILD="$M4/metric/build_m3_real_inputs.py"
ASSEMBLE="$M4/metric/assemble_hvpput_report.py"
METRIC="$M4/metric/compute_hvpput.py"
PYTHONPATH="/home/zephryj/turingos_backup/work/turing/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

test -x "$BUILD" || fail "missing executable real-input builder"
test -x "$ASSEMBLE" || fail "missing executable report assembler"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/arm_B/tasks/task-1"

cat > "$tmp/registry.json" <<'JSON'
{
  "instance_ids": ["task-1"],
  "registry_sha256_self_excluded": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "schema_id": "heldout_task_registry.v1",
  "shard": "S01",
  "shard_manifest_sha256": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
}
JSON

cat > "$tmp/price_table.json" <<'JSON'
{
  "currency": "USD",
  "integer_micro_usd_only": true,
  "models": [
    {
      "input_cache_hit_microusd_per_mtok": 3500,
      "input_cache_miss_microusd_per_mtok": 420000,
      "model_id": "deepseek-v4-pro",
      "output_microusd_per_mtok": 840000,
      "provider": "deepseek"
    }
  ],
  "schema_id": "turingos.m3.price_table.v1"
}
JSON

price_digest="$(python3 - <<'PY' "$tmp/price_table.json"
import json, sys
from pathlib import Path
from turingos import codec
print(codec.content_digest(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))))
PY
)"

cat > "$tmp/arm_B/tasks/task-1/worker_receipt.json" <<JSON
{
  "cost_event": {
    "agent_id": "m3-test-agent",
    "branch_id": "branch:m3-test",
    "capsule_id": "cap:test",
    "cost": {
      "bound_kind": null,
      "cost_microusd": 3,
      "cost_source_kind": "provider_receipt_inline",
      "price_table_digest": "$price_digest"
    },
    "problem_id": "task-1",
    "receipt_id": "rcpt:test",
    "run_id": "m3-test-run",
    "schema_id": "turingos.cost_event.v2",
    "split": "s01-test",
    "usage": {
      "completion_tokens": 1,
      "prompt_cache_hit_tokens": 2,
      "prompt_cache_miss_tokens": 3,
      "provider_usage_raw_sha256": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
      "prompt_tokens": 5,
      "total_tokens": 6
    },
    "wall_time_ms": 7,
    "worker": {
      "adapter_kind": "native_api",
      "endpoint": "https://api.deepseek.com/chat/completions",
      "model_id_requested": "deepseek-v4-pro",
      "model_id_resolved": "deepseek-v4-pro",
      "provider": "deepseek",
      "request_id": "req-test",
      "response_sha256": "sha256:3333333333333333333333333333333333333333333333333333333333333333"
    }
  },
  "instance_id": "task-1",
  "request_sha256": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
  "response_sha256": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
  "schema_id": "turingos.m3.deepseek_loop_worker_receipt.v1",
  "usage": {
    "completion_tokens": 1,
    "prompt_cache_hit_tokens": 2,
    "prompt_cache_miss_tokens": 3,
    "prompt_tokens": 5,
    "total_tokens": 6
  },
  "wall_time_ms": 7
}
JSON

cat > "$tmp/arm_B_report.json" <<'JSON'
{
  "completed_ids": ["task-1"],
  "error_ids": [],
  "resolved_ids": ["task-1"],
  "schema_version": "fixture",
  "submitted_ids": ["task-1"],
  "unresolved_ids": []
}
JSON

python3 "$BUILD" \
  --registry "$tmp/registry.json" \
  --price-table "$tmp/price_table.json" \
  --out-dir "$tmp/out" \
  --created-at-utc "2026-07-03T00:00:00Z" \
  --arm "B=$tmp/arm_B/tasks=$tmp/arm_B_report.json"

python3 - <<'PY' "$tmp/out/inputs/arm_B_receipts.json" "$price_digest"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["schema_id"] == "m4.normalized_receipts.v1"
event = data["events"][0]
assert event["task"] == "task-1"
assert event["event_ref"] == "rcpt:test"
assert event["cost_source_kind"] == "provider_receipt_inline"
assert event["usage_schema"] == "deepseek_chat_v1"
assert event["usage"]["output_tokens"] == 1
assert event["usage"]["completion_tokens"] == 1
assert event["computed_cost_microusd"] == 3
assert event["price_table_digest"] == sys.argv[2]
PY

mkdir -p "$tmp/out/per_arm"
python3 "$METRIC" \
  --registry "$tmp/registry.json" \
  --receipts "$tmp/out/inputs/arm_B_receipts.json" \
  --results "$tmp/out/inputs/arm_B_results.json" \
  --price-table "$tmp/out/inputs/price_table.m4.json" \
  --out "$tmp/out/per_arm/arm_B_hvpput_report.v1.json"

python3 - <<'PY' "$tmp/out/per_arm/arm_B_hvpput_report.v1.json"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["class_breakdown"] == {"n_billing_complete": 1, "n_bounded": 0, "n_excluded": 0}
assert data["billing_complete_portfolio"]["total_solves"] == 1
assert data["billing_complete_portfolio"]["total_cost_microusd"] == 3
assert data["billing_complete_portfolio"]["total_wall_ms"] == 7
PY

python3 "$ASSEMBLE" \
  --registry "$tmp/registry.json" \
  --input-digests "$tmp/out/inputs/INPUT_DIGESTS.json" \
  --receipt-binding-note "$tmp/out/inputs/RECEIPT_BINDING_NOTE.json" \
  --out "$tmp/out/hvpput_report.v1.json" \
  --arm-report "B=$tmp/out/per_arm/arm_B_hvpput_report.v1.json"

python3 - <<'PY' "$tmp/out/hvpput_report.v1.json"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["schema_id"] == "m4.hvpput_report.v1"
assert data["class_breakdown"] == {"n_billing_complete": 1, "n_bounded": 0, "n_excluded": 0}
assert data["arms"]["B"]["billing_complete_portfolio"]["total_solves"] == 1
assert data["receipt_binding_verification"]["provider_receipt_inline_events"] == 1
assert data["receipt_binding_verification"]["all_provider_receipt_inline_events_normalized"] is True
PY

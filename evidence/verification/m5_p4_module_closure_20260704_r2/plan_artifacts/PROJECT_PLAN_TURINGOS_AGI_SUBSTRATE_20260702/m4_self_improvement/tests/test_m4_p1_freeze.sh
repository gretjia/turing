#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
M4="$ROOT/m4_self_improvement"
METRIC="$M4/metric/compute_hvpput.py"
REGISTRY_GEN="$M4/metric/gen_registry.py"
FIXTURE="$M4/metric/selftest_fixture"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for n in 001 002 003 004 005 006 007; do
  adr="$(find "$ROOT/adr" -maxdepth 1 -type f -name "ADR-M4-${n}-*.md" | sort | head -n 1)"
  test -n "$adr" || fail "missing ADR-M4-${n}"
  rg -q "status: accepted-addressed" "$adr" || fail "ADR-M4-${n} status"
  rg -q "status_ceiling: ADDRESSED" "$adr" || fail "ADR-M4-${n} ceiling"
done

test -x "$METRIC" || fail "missing executable metric script"
test -x "$REGISTRY_GEN" || fail "missing executable registry generator"
test -f "$M4/NORTHSTAR_REPORT.skeleton.md" || fail "missing report skeleton"
test -f "$M4/CLAIM_BOUNDARY.template.json" || fail "missing claim boundary template"
test -f "$M4/M4_P1_FREEZE_RECORD.json" || fail "missing freeze record"

rg -q "Δ_BC = x \\[CI a,b\\], H2 passed at pre-registered α; failure-memory contribution is supported at this scale\\." "$M4/NORTHSTAR_REPORT.skeleton.md" || fail "missing positive template"
rg -q "Δ_BC = x \\[CI includes 0\\]; the study was powered for MDE = y; smaller true effects are not excluded\\. No failure-memory efficacy claim is made\\." "$M4/NORTHSTAR_REPORT.skeleton.md" || fail "missing null template"
rg -q 'Negative: same as null plus "the point estimate is negative; a harm hypothesis was not pre-registered and is flagged for a future pre-registered study\."' "$M4/NORTHSTAR_REPORT.skeleton.md" || fail "missing negative template"

python3 - <<'PY' "$M4/CLAIM_BOUNDARY.template.json"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["failure_memory_causal_claim_allowed"] == "<bool tied to H2>"
assert data["hvpput_is_capability_claim"] is False
assert data["absolute_rate_is_capability_claim"] is False
PY

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

python3 "$METRIC" --fixture "$FIXTURE" > "$tmp/hvpput_report.v1.json"
cmp -s "$FIXTURE/expected_hvpput_report.v1.json" "$tmp/hvpput_report.v1.json" || {
  diff -u "$FIXTURE/expected_hvpput_report.v1.json" "$tmp/hvpput_report.v1.json" >&2 || true
  fail "fixture output differs"
}

python3 - <<'PY' "$tmp/hvpput_report.v1.json"
import json, re, sys
text = open(sys.argv[1], encoding="utf-8").read()
json.load(open(sys.argv[1], encoding="utf-8"))
for match in re.finditer(r'(?<!["A-Za-z0-9_])[-]?\d+\.\d+(?!["A-Za-z0-9_])', text):
    raise SystemExit(f"float token found: {match.group(0)}")
PY

python3 - <<'PY' "$FIXTURE/expected_hvpput_report.v1.json"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["class_breakdown"] == {
    "n_billing_complete": 1,
    "n_bounded": 1,
    "n_excluded": 1,
}
assert data["billing_complete_portfolio"]["total_cost_microusd"] == 7560
assert data["billing_complete_portfolio"]["total_wall_ms"] == 105000
assert data["billing_complete_portfolio"]["hvpput_pair"] == {
    "numerator_solves": 1,
    "denominator_microusd_ms": 793800000,
}
assert data["billing_complete_portfolio"]["hvpput_m_str"] == "0.001259763"
assert data["billing_complete_portfolio"]["solves_per_dollar_e6_str"] == "132275132"
assert data["bounded_portfolio"]["hvpput_bound_kind"] == "lower_bound_via_cost_upper_bound"
PY

cp -R "$FIXTURE" "$tmp/bad_out_of_registry"
python3 - <<'PY' "$tmp/bad_out_of_registry/receipts.json"
import json, sys
path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
data["events"][0]["task"] = "not-in-registry"
open(path, "w", encoding="utf-8").write(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY
if python3 "$METRIC" --fixture "$tmp/bad_out_of_registry" > "$tmp/out_of_registry.json" 2> "$tmp/out_of_registry.err"; then
  fail "out-of-registry receipt unexpectedly passed"
fi
rg -q "out_of_registry" "$tmp/out_of_registry.err" || fail "out-of-registry error missing"

cp -R "$FIXTURE" "$tmp/bad_inline"
python3 - <<'PY' "$tmp/bad_inline/receipts.json"
import json, sys
path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
del data["events"][0]["provider_request_id"]
open(path, "w", encoding="utf-8").write(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY
if python3 "$METRIC" --fixture "$tmp/bad_inline" > "$tmp/bad_inline.json" 2> "$tmp/bad_inline.err"; then
  fail "mislabeled inline receipt unexpectedly passed"
fi
rg -q "provider_receipt_inline_missing_field" "$tmp/bad_inline.err" || fail "mislabeled inline error missing"

cp -R "$FIXTURE" "$tmp/aggregate_ceiling"
python3 - <<'PY' "$tmp/aggregate_ceiling/receipts.json"
import json, sys
path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
event = data["events"][0]
event["computed_cost_microusd"] = 1
event["usage"] = {
    "output_tokens": 1,
    "prompt_cache_hit_tokens": 1,
    "prompt_cache_miss_tokens": 1,
}
open(path, "w", encoding="utf-8").write(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY
python3 "$METRIC" --fixture "$tmp/aggregate_ceiling" > "$tmp/aggregate_ceiling.json" 2> "$tmp/aggregate_ceiling.err" || {
  cat "$tmp/aggregate_ceiling.err" >&2
  fail "aggregate ceiling recomputation rejected a valid CostEvent.v2 cost"
}

cat > "$tmp/shard_manifest.json" <<'JSON'
{
  "schema_id": "m3.shard_manifest.fixture.v1",
  "shards": {
    "S01": [
      {"instance_id": "t1"},
      {"instance_id": "t2"},
      {"instance_id": "t3"}
    ]
  }
}
JSON
python3 "$REGISTRY_GEN" --shard-manifest "$tmp/shard_manifest.json" --shard S01 --out "$tmp/heldout_task_registry.v1.json" --created-at-utc FIXTURE
python3 - <<'PY' "$tmp/shard_manifest.json" "$tmp/heldout_task_registry.v1.json"
import hashlib, json, sys
manifest_path, registry_path = sys.argv[1:3]
registry = json.load(open(registry_path, encoding="utf-8"))
assert registry["schema_id"] == "heldout_task_registry.v1"
assert registry["shard"] == "S01"
assert registry["instance_ids"] == ["t1", "t2", "t3"]
expected = "sha256:" + hashlib.sha256(open(manifest_path, "rb").read()).hexdigest()
assert registry["shard_manifest_sha256"] == expected
assert registry["registry_sha256_self_excluded"].startswith("sha256:")
PY

python3 - <<'PY' "$M4" "$M4/M4_P1_FREEZE_RECORD.json" "$M4/M4_P1_METRIC_CORRECTION_RECORD.json"
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
record = json.load(open(sys.argv[2], encoding="utf-8"))
correction = json.load(open(sys.argv[3], encoding="utf-8"))
assert record["schema_id"] == "m4.p1.freeze_record.v1"
assert record["freeze_scope"] == "FIXTURE_ONLY_NO_M3_OUTPUT_READ"
assert correction["schema_id"] == "m4.p1.metric_correction_record.v1"
assert correction["correction_reason"] == "aggregate_ceiling_costevent_v2_recompute"
corrections = {
    entry["path"]: entry
    for entry in correction["corrected_artifacts"]
}
required = [
    "metric/compute_hvpput.py",
    "metric/gen_registry.py",
    "metric/selftest_fixture/expected_hvpput_report.v1.json",
    "NORTHSTAR_REPORT.skeleton.md",
    "CLAIM_BOUNDARY.template.json",
]
artifacts = {entry["path"]: entry["sha256"] for entry in record["artifacts"]}
for path in required:
    assert path in artifacts, path
    assert artifacts[path].startswith("sha256:")
    actual = "sha256:" + hashlib.sha256((root / path).read_bytes()).hexdigest()
    if artifacts[path] != actual:
        assert path in corrections, (path, artifacts[path], actual)
        assert corrections[path]["previous_sha256"] == artifacts[path]
        assert corrections[path]["sha256"] == actual
PY

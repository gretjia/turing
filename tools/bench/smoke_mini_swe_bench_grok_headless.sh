#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-/tmp/turingos-mini-swe-bench-smoke}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

TASKS="$OUT_DIR/verified-mini-smoke.jsonl"
PLAN="$OUT_DIR/plan.json"
AUDIT="$OUT_DIR/audit.json"

cat > "$TASKS" <<'JSONL'
{"instance_id":"smoke__fixture-00001","repo":"https://github.com/example/smoke","base_commit":"0000000","problem_statement":"Smoke fixture: build the benchmark plan only; do not invoke a model."}
JSONL

python3 "$REPO_ROOT/tools/bench/mini_swe_bench_grok_headless.py" \
  --tasks-jsonl "$TASKS" \
  --out "$PLAN" \
  --dry-run \
  --limit 1 \
  --randomization-seed 20260627 \
  --meta-provider deepseek \
  --meta-model deepseek-v4-pro \
  --meta-api-key-env DEEPSEEK_API_KEY

python3 "$REPO_ROOT/tools/bench/audit_mini_swe_bench_plan.py" \
  --plan "$PLAN" \
  --out "$AUDIT" \
  --allow-smoke \
  --min-tasks 1

python3 - "$PLAN" "$AUDIT" <<'PY'
import json
import pathlib
import re
import sys

plan = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
audit = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))

if re.search(r"sk-[A-Za-z0-9_-]{16,}", plan):
    raise SystemExit("plan contains API-key-shaped material")
if audit.get("verdict") != "PASS":
    raise SystemExit(f"smoke audit did not PASS: {audit}")
if audit.get("scientific_status") != "SMOKE_ONLY_NOT_REAL_BENCHMARK":
    raise SystemExit(f"unexpected smoke scientific status: {audit.get('scientific_status')}")

print(json.dumps({
    "schema_id": "MiniSweBenchSmokeResult.v1",
    "verdict": "PASS",
    "plan": str(sys.argv[1]),
    "audit": str(sys.argv[2]),
}, sort_keys=True))
PY

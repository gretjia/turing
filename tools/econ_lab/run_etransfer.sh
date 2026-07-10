#!/usr/bin/env bash
# CAPSULE E launcher — etransfer stage-market vs atomic GLOBAL-bucket confirmatory run.
# Pattern: run_stage_b_prime.sh (atomic status, arm concurrency 2, aggregated exit).
# Docker shared with CAPSULE D: arms concurrent ≤2, harness max_workers=1 (driver default).
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"
RUN_ROOT="$REPO/tools/econ_lab/runs/etransfer_20260710"
SCORING_PY="$HOME/.turingos/swebench-venv/bin/python"
STAGE_DRIVER="$REPO/tools/econ_lab/depthk/etransfer_driver.py"
FLAT_DRIVER="$REPO/tools/econ_lab/depthk/etransfer_flat_driver.py"
SPLIT_MANIFEST="$RUN_ROOT/etransfer_split_manifest.json"
mkdir -p "$RUN_ROOT"

# shellcheck disable=SC1090
source "$HOME/.turingos/secrets.env"
export SILICONFLOW_API_KEY DEEPSEEK_API_KEY

if [ ! -f "$SPLIT_MANIFEST" ]; then
  echo "[etransfer] missing split manifest: $SPLIT_MANIFEST" >&2
  exit 1
fi

write_status() {
  local dir="$1" json="$2"
  echo "$json" > "$dir/status.json.tmp" && mv "$dir/status.json.tmp" "$dir/status.json"
}

run_arm_T() {
  local dir="$RUN_ROOT/T"
  mkdir -p "$dir"
  write_status "$dir" "{\"arm\":\"T\",\"status\":\"RUNNING\",\"started_unix\":$(date +%s)}"
  python3 "$STAGE_DRIVER" \
    --out "$dir" \
    --stream-manifest "$SPLIT_MANIFEST" \
    --tau 0.5 \
    --fractional-reward \
    --run-label "etransfer-T" \
    --scoring-python "$SCORING_PY" \
    --scoring-timeout-s 2700 \
    --resume \
    > "$dir/driver.log" 2>&1
  local rc=$?
  write_status "$dir" "{\"arm\":\"T\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s)}"
  echo "[etransfer] arm T finished rc=$rc"
  return $rc
}

run_arm_A() {
  local dir="$RUN_ROOT/A"
  mkdir -p "$dir"
  write_status "$dir" "{\"arm\":\"A\",\"status\":\"RUNNING\",\"started_unix\":$(date +%s)}"
  python3 "$FLAT_DRIVER" \
    --out "$dir" \
    --stream-manifest "$SPLIT_MANIFEST" \
    --tau 0.5 \
    --fractional-reward \
    --run-label "etransfer-A" \
    --scoring-python "$SCORING_PY" \
    --scoring-timeout-s 2700 \
    --resume \
    > "$dir/driver.log" 2>&1
  local rc=$?
  write_status "$dir" "{\"arm\":\"A\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s)}"
  echo "[etransfer] arm A finished rc=$rc"
  return $rc
}

MODE="${1:-full}"

if [ "$MODE" = "smoke" ]; then
  # 1 TRAIN task × 2 arms (≤2-3 calls)
  echo "[etransfer] SMOKE: 1 TRAIN task × 2 arms"
  SMOKE_ROOT="$RUN_ROOT/smoke"
  mkdir -p "$SMOKE_ROOT"
  # Build a 1-task stream from first TRAIN id
  python3 - <<PY
import json
from pathlib import Path
root = Path("$RUN_ROOT")
m = json.loads((root / "etransfer_split_manifest.json").read_text())
train = m["train_instance_ids"]
if not train:
    raise SystemExit("no TRAIN tasks in manifest")
smoke = {
    "schema": "econ_lab.etransfer_smoke_stream.v1",
    "instance_ids": [train[0]],
    "train_instance_ids": [train[0]],
    "heldout_instance_ids": [],
    "heldout_start_index": 1,
    "fingerprint_sha256": m.get("fingerprint_sha256"),
    "parent_split": str(root / "etransfer_split_manifest.json"),
    "note": "smoke: first TRAIN instance only",
}
out = root / "smoke" / "smoke_stream_manifest.json"
out.write_text(json.dumps(smoke, indent=2, sort_keys=True) + "\n")
print(out, train[0])
PY
  SMOKE_MANIFEST="$SMOKE_ROOT/smoke_stream_manifest.json"

  run_smoke_T() {
    local dir="$SMOKE_ROOT/T"
    mkdir -p "$dir"
    write_status "$dir" "{\"arm\":\"T\",\"status\":\"RUNNING\",\"mode\":\"smoke\",\"started_unix\":$(date +%s)}"
    python3 "$STAGE_DRIVER" \
      --out "$dir" \
      --stream-manifest "$SMOKE_MANIFEST" \
      --tau 0.5 \
      --fractional-reward \
      --run-label "etransfer-smoke-T" \
      --scoring-python "$SCORING_PY" \
      --scoring-timeout-s 2700 \
      --max-tasks 1 \
      --max-worker-calls 1 \
      > "$dir/driver.log" 2>&1
    local rc=$?
    write_status "$dir" "{\"arm\":\"T\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s)}"
    echo "[etransfer-smoke] T rc=$rc"
    return $rc
  }
  run_smoke_A() {
    local dir="$SMOKE_ROOT/A"
    mkdir -p "$dir"
    write_status "$dir" "{\"arm\":\"A\",\"status\":\"RUNNING\",\"mode\":\"smoke\",\"started_unix\":$(date +%s)}"
    python3 "$FLAT_DRIVER" \
      --out "$dir" \
      --stream-manifest "$SMOKE_MANIFEST" \
      --tau 0.5 \
      --fractional-reward \
      --run-label "etransfer-smoke-A" \
      --scoring-python "$SCORING_PY" \
      --scoring-timeout-s 2700 \
      --max-tasks 1 \
      > "$dir/driver.log" 2>&1
    local rc=$?
    write_status "$dir" "{\"arm\":\"A\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s)}"
    echo "[etransfer-smoke] A rc=$rc"
    return $rc
  }

  pids=()
  run_smoke_T & pids+=($!)
  run_smoke_A & pids+=($!)
  for p in "${pids[@]}"; do wait "$p" || true; done
  LAUNCH_RC=0
  for label in T A; do
    s="$SMOKE_ROOT/$label/status.json"
    if [ ! -f "$s" ]; then LAUNCH_RC=1; continue; fi
    cat "$s"; echo
    grep -q '"status":"DONE"' "$s" || LAUNCH_RC=1
  done
  # Prove GLOBAL keys in meta
  python3 - <<'PY'
import json, sys
from pathlib import Path
root = Path("tools/econ_lab/runs/etransfer_20260710/smoke")
ok = True
for arm in ("T", "A"):
    v = json.loads((root / arm / "verdict.json").read_text())
    if arm == "T":
        b = v.get("domain_bucket")
        mode = v.get("domain_bucket_mode")
        print(f"T domain_bucket={b} mode={mode}")
        if b != "global" or mode != "GLOBAL_CONSTANT":
            ok = False
        for t in v.get("tasks") or []:
            if t.get("domain_bucket") != "global":
                ok = False
    else:
        buckets = (v.get("stage_b_prime_meta") or {}).get("domain_buckets_observed") or []
        mode = v.get("domain_bucket_mode")
        print(f"A buckets={buckets} mode={mode}")
        if buckets != ["global"] or mode != "GLOBAL_CONSTANT":
            ok = False
print("GLOBAL_KEY_PROOF", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
PY
  GRC=$?
  if [ $GRC -ne 0 ]; then LAUNCH_RC=1; fi
  exit $LAUNCH_RC
fi

# Full run: both arms concurrent (MAX_PAR=2)
ARM_LABELS=("T" "A")
ARM_FNS=("run_arm_T" "run_arm_A")
MAX_PAR=2
pids=()
for fn in "${ARM_FNS[@]}"; do
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_PAR" ]; do
    wait -n || true
  done
  "$fn" &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || true; done

echo "[etransfer] all arms complete"
LAUNCH_RC=0
for label in "${ARM_LABELS[@]}"; do
  s="$RUN_ROOT/$label/status.json"
  if [ ! -f "$s" ]; then
    echo "[etransfer] $label: status.json missing"
    LAUNCH_RC=1
    continue
  fi
  cat "$s"; echo
  grep -q '"status":"DONE"' "$s" || LAUNCH_RC=1
done
exit $LAUNCH_RC

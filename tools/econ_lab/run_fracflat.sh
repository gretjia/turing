#!/usr/bin/env bash
# Fracflat launcher — CAPSULE D §3/§5 (FL fractional-live / BL binary-live / UU uniform).
# 3 arms x 50 pool tasks = 150 runs. Pattern (launcher shape, concurrency, atomic
# status writes, aggregated exit code, scoring venv) copied from run_p3e3.sh /
# run_stage_b_prime.sh.
#
# Arms (all 12-route flat market, cold P=0.5 — no --priors):
#   FL  --fractional-reward, live backup, tau=0.5
#   BL  binary (no fractional), live backup, tau=0.5
#   UU  tau=inf uniform, no fractional
#
# Docker shared with CAPSULE E: arm concurrency 2, harness max_workers 1 (driver-hardcoded).
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ROOT="$REPO/tools/econ_lab/runs/fracflat_20260710"
SCORING_PY="$HOME/.turingos/swebench-venv/bin/python"
DRIVER="$REPO/tools/econ_lab/live_driver.py"
STREAM_MANIFEST="$REPO/tools/econ_lab/analysis/fracflat_stream_manifest.json"
POOL_MANIFEST="$REPO/tools/econ_lab/analysis/fracflat_pool_manifest.json"
TASK_SHARD="$REPO/tools/econ_lab/analysis/fracflat_task_root"
CLI_BIN="$REPO/target/debug/econ_fold_cli"
mkdir -p "$RUN_ROOT"

# shellcheck disable=SC1090
source "$HOME/.turingos/secrets.env"
export SILICONFLOW_API_KEY DEEPSEEK_API_KEY

if [ ! -x "$CLI_BIN" ]; then
  echo "[fracflat] building econ_fold_cli..." >&2
  (cd "$REPO" && cargo build -p turing-economy --bin econ_fold_cli) || exit 1
fi

if [ ! -f "$STREAM_MANIFEST" ] || [ ! -f "$POOL_MANIFEST" ]; then
  echo "[fracflat] REFUSING: missing pool/stream manifest — run fracflat_build_pool.py first" >&2
  exit 1
fi
if [ ! -d "$TASK_SHARD/ipqc" ]; then
  echo "[fracflat] REFUSING: missing task root $TASK_SHARD — run fracflat_build_pool.py first" >&2
  exit 1
fi

ACTUAL_POOL_SHA256="$(sha256sum "$POOL_MANIFEST" | cut -d' ' -f1)"
ACTUAL_STREAM_SHA256="$(sha256sum "$STREAM_MANIFEST" | cut -d' ' -f1)"
if [ -n "${PINNED_POOL_SHA256:-}" ] && [ "$ACTUAL_POOL_SHA256" != "$PINNED_POOL_SHA256" ]; then
  echo "[fracflat] REFUSING TO LAUNCH: pool sha $ACTUAL_POOL_SHA256 != pinned $PINNED_POOL_SHA256" >&2
  exit 1
fi
if [ -n "${PINNED_STREAM_SHA256:-}" ] && [ "$ACTUAL_STREAM_SHA256" != "$PINNED_STREAM_SHA256" ]; then
  echo "[fracflat] REFUSING TO LAUNCH: stream sha $ACTUAL_STREAM_SHA256 != pinned $PINNED_STREAM_SHA256" >&2
  exit 1
fi
echo "[fracflat] pool_sha256=$ACTUAL_POOL_SHA256 stream_manifest_sha256=$ACTUAL_STREAM_SHA256"

# Optional smoke: FRACFLAT_MAX_TASKS=1 for 1 task x 3 arms
MAX_TASKS_ARGS=()
if [ -n "${FRACFLAT_MAX_TASKS:-}" ]; then
  MAX_TASKS_ARGS=(--max-tasks "$FRACFLAT_MAX_TASKS")
  echo "[fracflat] max-tasks override: $FRACFLAT_MAX_TASKS"
fi

# Optional single-arm filter: FRACFLAT_ARMS="FL BL" etc.
REQUESTED_ARMS="${FRACFLAT_ARMS:-FL BL UU}"

write_status() {
  local dir="$1" json="$2"
  echo "$json" > "$dir/status.json.tmp" && mv "$dir/status.json.tmp" "$dir/status.json"
}

run_arm() {
  local label="$1"
  shift
  local extra_args=("$@")
  local dir="$RUN_ROOT/$label"
  mkdir -p "$dir"
  # Record pool sha in status (driver cannot be modified to embed it).
  write_status "$dir" "{\"arm\":\"$label\",\"status\":\"RUNNING\",\"started_unix\":$(date +%s),\"pool_manifest_sha256\":\"$ACTUAL_POOL_SHA256\",\"stream_manifest_sha256\":\"$ACTUAL_STREAM_SHA256\"}"
  python3 "$DRIVER" \
    --task-shard "$TASK_SHARD" \
    --stream-manifest "$STREAM_MANIFEST" \
    --out "$dir/verdict.json" \
    --task-dir-root "$dir/task_runs" \
    --report-dir "$dir/scoring" \
    --scoring-python "$SCORING_PY" \
    --scoring-timeout-s 2700 \
    --econ-fold-cli "$CLI_BIN" \
    --run-label "$label" \
    "${MAX_TASKS_ARGS[@]}" \
    "${extra_args[@]}" \
    > "$dir/driver.log" 2>&1
  local rc=$?
  write_status "$dir" "{\"arm\":\"$label\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s),\"pool_manifest_sha256\":\"$ACTUAL_POOL_SHA256\",\"stream_manifest_sha256\":\"$ACTUAL_STREAM_SHA256\"}"
  echo "[fracflat] arm $label finished rc=$rc"
  return $rc
}

run_arm_fl() { run_arm "FL" --tau "0.5" --fractional-reward; }
run_arm_bl() { run_arm "BL" --tau "0.5"; }
run_arm_uu() { run_arm "UU" --tau "inf"; }

declare -A ARM_FN_MAP=(
  [FL]=run_arm_fl
  [BL]=run_arm_bl
  [UU]=run_arm_uu
)

ARM_LABELS=()
ARM_FNS=()
for lab in $REQUESTED_ARMS; do
  fn="${ARM_FN_MAP[$lab]:-}"
  if [ -z "$fn" ]; then
    echo "[fracflat] unknown arm $lab" >&2
    exit 1
  fi
  ARM_LABELS+=("$lab")
  ARM_FNS+=("$fn")
done

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

echo "[fracflat] requested arms complete"
LAUNCH_RC=0
for label in "${ARM_LABELS[@]}"; do
  s="$RUN_ROOT/$label/status.json"
  if [ ! -f "$s" ]; then
    echo "[fracflat] $label: status.json missing"
    LAUNCH_RC=1
    continue
  fi
  cat "$s"; echo
  grep -q '"status":"DONE"' "$s" || LAUNCH_RC=1
done
exit $LAUNCH_RC

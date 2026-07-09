#!/usr/bin/env bash
# P3-E3 launcher — CAPSULE A §3/§5 (L live / Z frozen / R reset-at-22).
# 3 arms x 50 S03 tasks = 150 runs. Pattern (launcher shape, concurrency, atomic
# status writes, aggregated exit code, scoring venv, priors sha guard) copied
# from run_stage_b_prime.sh.
#
# Arms (all tau=0.5, same S01+S02 pooled priors, same stream manifest):
#   L  live backup
#   Z  frozen backup
#   R  live backup + --reset-at-task-index 22
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ROOT="$REPO/tools/econ_lab/runs/p3e3_20260709"
SCORING_PY="$HOME/.turingos/swebench-venv/bin/python"
DRIVER="$REPO/tools/econ_lab/live_driver.py"
PRIORS_FILE="$REPO/tools/econ_lab/analysis/p3e3_priors_s01s02.json"
STREAM_MANIFEST="$REPO/tools/econ_lab/analysis/p3e3_stream_manifest.json"
TASK_SHARD="$REPO/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S03"
CLI_BIN="$REPO/target/debug/econ_fold_cli"
mkdir -p "$RUN_ROOT"

# shellcheck disable=SC1090
source "$HOME/.turingos/secrets.env"
export SILICONFLOW_API_KEY DEEPSEEK_API_KEY

if [ ! -x "$CLI_BIN" ]; then
  echo "[p3e3] building econ_fold_cli..." >&2
  (cd "$REPO" && cargo build -p turing-economy --bin econ_fold_cli) || exit 1
fi

# Pinned at launch time from the generated file (HANDOFF records the same sha).
# Refuse silent drift: if PINNED_PRIORS_SHA256 is set in the environment, enforce it;
# otherwise compute and echo the live sha for the HANDOFF.
ACTUAL_PRIORS_SHA256="$(sha256sum "$PRIORS_FILE" | cut -d' ' -f1)"
if [ -n "${PINNED_PRIORS_SHA256:-}" ] && [ "$ACTUAL_PRIORS_SHA256" != "$PINNED_PRIORS_SHA256" ]; then
  echo "[p3e3] REFUSING TO LAUNCH: $PRIORS_FILE sha256 $ACTUAL_PRIORS_SHA256 != pinned $PINNED_PRIORS_SHA256" >&2
  exit 1
fi
ACTUAL_STREAM_SHA256="$(sha256sum "$STREAM_MANIFEST" | cut -d' ' -f1)"
if [ -n "${PINNED_STREAM_SHA256:-}" ] && [ "$ACTUAL_STREAM_SHA256" != "$PINNED_STREAM_SHA256" ]; then
  echo "[p3e3] REFUSING TO LAUNCH: $STREAM_MANIFEST sha256 $ACTUAL_STREAM_SHA256 != pinned $PINNED_STREAM_SHA256" >&2
  exit 1
fi
echo "[p3e3] priors_sha256=$ACTUAL_PRIORS_SHA256 stream_manifest_sha256=$ACTUAL_STREAM_SHA256"

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
  write_status "$dir" "{\"arm\":\"$label\",\"status\":\"RUNNING\",\"started_unix\":$(date +%s)}"
  python3 "$DRIVER" \
    --tau "0.5" \
    --task-shard "$TASK_SHARD" \
    --stream-manifest "$STREAM_MANIFEST" \
    --priors "$PRIORS_FILE" \
    --out "$dir/verdict.json" \
    --task-dir-root "$dir/task_runs" \
    --report-dir "$dir/scoring" \
    --scoring-python "$SCORING_PY" \
    --scoring-timeout-s 2700 \
    --econ-fold-cli "$CLI_BIN" \
    --run-label "$label" \
    "${extra_args[@]}" \
    > "$dir/driver.log" 2>&1
  local rc=$?
  write_status "$dir" "{\"arm\":\"$label\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s)}"
  echo "[p3e3] arm $label finished rc=$rc"
  return $rc
}

run_arm_l() { run_arm "L"; }
run_arm_z() { run_arm "Z" --frozen-backup; }
run_arm_r() { run_arm "R" --reset-at-task-index 22; }

ARM_LABELS=("L" "Z" "R")
ARM_FNS=("run_arm_l" "run_arm_z" "run_arm_r")
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

echo "[p3e3] all arms complete"
LAUNCH_RC=0
for label in "${ARM_LABELS[@]}"; do
  s="$RUN_ROOT/$label/status.json"
  if [ ! -f "$s" ]; then
    echo "[p3e3] $label: status.json missing"
    LAUNCH_RC=1
    continue
  fi
  cat "$s"; echo
  grep -q '"status":"DONE"' "$s" || LAUNCH_RC=1
done
exit $LAUNCH_RC

#!/usr/bin/env bash
# Stage B' launcher — ADR-ECON-003 Decision 7.6/7.7, PREREG Appendix A amendment #4.
# 4 arms x 50 S02 tasks = 200 runs. Pattern (launcher shape, concurrency, atomic status
# writes, aggregated exit code, scoring venv) copied verbatim from run_stage_a.sh -- only the
# arm definitions and the new --priors/--frozen-backup/--task-shard flags differ.
#
# Arms (all tau*=0.5, PREREG amendment #4, except U which is the uniform-random control):
#   W (warm-start P=S01 pooled posterior, backup ACTIVE)
#   F (same P, backup FROZEN -- Q_eff stays pinned at P for the whole run)
#   C (P=0.5 uninformative prior, backup ACTIVE -- no --priors)
#   U (uniform/tau=inf, no --priors)
# Evaluation task stream = S02 (disjoint from the priors' S01 source stream, out-of-sample
# discipline, ADR-ECON-003 Decision 7.6: "评测任务与先验来源任务必须零交集").
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ROOT="$REPO/tools/econ_lab/runs/stageBprime_20260708"
SCORING_PY="$HOME/.turingos/swebench-venv/bin/python"
DRIVER="$REPO/tools/econ_lab/live_driver.py"
PRIORS_FILE="$REPO/tools/econ_lab/analysis/stage_b_prime_priors_s01.json"
TASK_SHARD="$REPO/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02"
mkdir -p "$RUN_ROOT"

# shellcheck disable=SC1090
source "$HOME/.turingos/secrets.env"
export SILICONFLOW_API_KEY DEEPSEEK_API_KEY

# Pinned provenance check (ADR-ECON-003 Decision 7.6): refuse to launch against a priors file
# that does not match the sha256 pinned in the ADR / PREREG Appendix A amendment #4 -- a
# silent drift here would invalidate the out-of-sample warm-start claim.
PINNED_PRIORS_SHA256="d7f900934d3d9c95243af717e6ee7e3fdab7df7c989c17f05a59171757fe41ac"
ACTUAL_PRIORS_SHA256="$(sha256sum "$PRIORS_FILE" | cut -d' ' -f1)"
if [ "$ACTUAL_PRIORS_SHA256" != "$PINNED_PRIORS_SHA256" ]; then
  echo "[stageBprime] REFUSING TO LAUNCH: $PRIORS_FILE sha256 $ACTUAL_PRIORS_SHA256 != pinned $PINNED_PRIORS_SHA256" >&2
  exit 1
fi

# Atomic status write: the health probe (if any) reads status.json concurrently; a
# truncate-then-write leaves a window where it reads an empty file.
write_status() {
  local dir="$1" json="$2"
  echo "$json" > "$dir/status.json.tmp" && mv "$dir/status.json.tmp" "$dir/status.json"
}

run_arm() {
  local label="$1" tau="$2"
  shift 2
  local extra_args=("$@")
  local dir="$RUN_ROOT/$label"
  mkdir -p "$dir"
  write_status "$dir" "{\"arm\":\"$label\",\"status\":\"RUNNING\",\"started_unix\":$(date +%s)}"
  python3 "$DRIVER" \
    --tau "$tau" \
    --task-shard "$TASK_SHARD" \
    --out "$dir/verdict.json" \
    --task-dir-root "$dir/task_runs" \
    --report-dir "$dir/scoring" \
    --scoring-python "$SCORING_PY" \
    --scoring-timeout-s 2700 \
    --run-label "stageBprime-$label" \
    "${extra_args[@]}" \
    > "$dir/driver.log" 2>&1
  local rc=$?
  write_status "$dir" "{\"arm\":\"$label\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s)}"
  echo "[stageBprime] arm $label finished rc=$rc"
  return $rc
}

# label:tau:extra-args (space-separated extra flags, expanded via eval-free array below).
# Ordered so the two primary-hypothesis arms (W, F -- H-B1/H-B2) finish first.
run_arm_w() { run_arm "W" "0.5" --priors "$PRIORS_FILE"; }
run_arm_f() { run_arm "F" "0.5" --priors "$PRIORS_FILE" --frozen-backup; }
run_arm_c() { run_arm "C" "0.5"; }
run_arm_u() { run_arm "U" "inf"; }

ARM_LABELS=("W" "F" "C" "U")
ARM_FNS=("run_arm_w" "run_arm_f" "run_arm_c" "run_arm_u")
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

# Aggregate the launcher exit code from the arms' terminal statuses (not from `wait` codes:
# the `wait -n` throttle may already have reaped a pid, making a later `wait $pid`
# unreliable). Any FAILED/missing status -> exit 1 so a supervisor wrapper sees the failure
# instead of an unconditional 0.
echo "[stageBprime] all arms complete"
LAUNCH_RC=0
for label in "${ARM_LABELS[@]}"; do
  s="$RUN_ROOT/$label/status.json"
  if [ ! -f "$s" ]; then
    echo "[stageBprime] $label: status.json missing"
    LAUNCH_RC=1
    continue
  fi
  cat "$s"; echo
  grep -q '"status":"DONE"' "$s" || LAUNCH_RC=1
done
exit $LAUNCH_RC

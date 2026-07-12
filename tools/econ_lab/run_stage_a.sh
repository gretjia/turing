#!/usr/bin/env bash
# Stage A launcher — PREREG E-price-tau (frozen Appendix A, amendment #1).
# 5 arms (tau = 0 / 0.5 / 1 / 2 / inf) x 50 S01 tasks = 250 runs <= 305 cap.
# Concurrency deliberately capped at 2 arms (4-core host: avoid docker-scoring
# CPU contention inducing timeout bias); within-arm order is sequential by
# design (fold feedback). Scoring uses the pinned numpy<2 venv harness.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ROOT="$REPO/tools/econ_lab/runs/stageA_20260707"
SCORING_PY="$HOME/.turingos/swebench-venv/bin/python"
DRIVER="$REPO/tools/econ_lab/live_driver.py"
mkdir -p "$RUN_ROOT"

# shellcheck disable=SC1090
source "$HOME/.turingos/secrets.env"
export SILICONFLOW_API_KEY DEEPSEEK_API_KEY

# Atomic status write: the health probe reads status.json concurrently; a
# truncate-then-write leaves a window where it reads an empty file.
write_status() {
  local dir="$1" json="$2"
  echo "$json" > "$dir/status.json.tmp" && mv "$dir/status.json.tmp" "$dir/status.json"
}

run_arm() {
  local tau="$1" label="$2"
  local dir="$RUN_ROOT/tau_$label"
  mkdir -p "$dir"
  write_status "$dir" "{\"arm\":\"tau_$label\",\"status\":\"RUNNING\",\"started_unix\":$(date +%s)}"
  python3 "$DRIVER" \
    --tau "$tau" \
    --out "$dir/verdict.json" \
    --task-dir-root "$dir/task_runs" \
    --report-dir "$dir/scoring" \
    --scoring-python "$SCORING_PY" \
    --scoring-timeout-s 2700 \
    > "$dir/driver.log" 2>&1
  local rc=$?
  write_status "$dir" "{\"arm\":\"tau_$label\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s)}"
  echo "[stageA] arm tau_$label finished rc=$rc"
  return $rc
}

# Arms ordered so the two decision-critical extremes (0, inf) finish first.
ARMS=("0:0" "inf:inf" "0.5:0p5" "1:1" "2:2")
MAX_PAR=2
pids=()
for spec in "${ARMS[@]}"; do
  tau="${spec%%:*}"; label="${spec##*:}"
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_PAR" ]; do
    wait -n || true
  done
  run_arm "$tau" "$label" &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || true; done

# Aggregate the launcher exit code from the arms' terminal statuses (not from
# `wait` codes: the `wait -n` throttle may already have reaped a pid, making a
# later `wait $pid` unreliable). Any FAILED/missing status -> exit 1 so a
# supervisor wrapper sees the failure instead of an unconditional 0.
echo "[stageA] all arms complete"
LAUNCH_RC=0
for spec in "${ARMS[@]}"; do
  label="${spec##*:}"
  s="$RUN_ROOT/tau_$label/status.json"
  if [ ! -f "$s" ]; then
    echo "[stageA] tau_$label: status.json missing"
    LAUNCH_RC=1
    continue
  fi
  cat "$s"; echo
  grep -q '"status":"DONE"' "$s" || LAUNCH_RC=1
done
exit $LAUNCH_RC

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

run_arm() {
  local tau="$1" label="$2"
  local dir="$RUN_ROOT/tau_$label"
  mkdir -p "$dir"
  echo "{\"arm\":\"tau_$label\",\"status\":\"RUNNING\",\"started_unix\":$(date +%s)}" > "$dir/status.json"
  python3 "$DRIVER" \
    --tau "$tau" \
    --out "$dir/verdict.json" \
    --task-dir-root "$dir/task_runs" \
    --report-dir "$dir/scoring" \
    --scoring-python "$SCORING_PY" \
    --scoring-timeout-s 2700 \
    > "$dir/driver.log" 2>&1
  local rc=$?
  echo "{\"arm\":\"tau_$label\",\"status\":\"$([ $rc -eq 0 ] && echo DONE || echo FAILED)\",\"exit\":$rc,\"finished_unix\":$(date +%s)}" > "$dir/status.json"
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

echo "[stageA] all arms complete"
for spec in "${ARMS[@]}"; do
  label="${spec##*:}"
  cat "$RUN_ROOT/tau_$label/status.json"; echo
done

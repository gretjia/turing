#!/usr/bin/env bash
# Stage A health probe — cron-invoked long-run supervision (read-only + state file).
# Exit 0 = healthy; exit 1 = ALARM lines present. Never mutates the run.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="$REPO/tools/econ_lab/runs/stageA_20260707"
STATE="$ROOT/.health_state"
NOW=$(date +%s)
ALARM=0
say() { echo "$@"; }
alarm() { echo "ALARM $*"; ALARM=1; }

# 1. launcher / arm process liveness vs arm statuses
LAUNCHER_ALIVE=$(pgrep -f "run_stage_a.sh" | head -1 || true)
DRIVERS=$(pgrep -fc "live_driver.py --tau" || true)
say "launcher_pid=${LAUNCHER_ALIVE:-dead} driver_procs=${DRIVERS:-0}"

RUNNING=0; DONE=0; FAILED=0; PENDING=0
for label in 0 inf 0p5 1 2; do
  s="$ROOT/tau_$label/status.json"
  if [ ! -f "$s" ]; then PENDING=$((PENDING+1)); say "arm tau_$label: PENDING"; continue; fi
  st=$(grep -o '"status":"[A-Z]*"' "$s" | cut -d'"' -f4)
  n=$(ls "$ROOT/tau_$label/task_runs" 2>/dev/null | wc -l)
  say "arm tau_$label: $st tasks_started=$n"
  case "$st" in
    RUNNING) RUNNING=$((RUNNING+1));;
    DONE) DONE=$((DONE+1));;
    FAILED) alarm "arm tau_$label FAILED (exit in status.json; driver.log tail follows)"; tail -3 "$ROOT/tau_$label/driver.log" 2>/dev/null; FAILED=$((FAILED+1));;
  esac
done

# 2. stall detection: newest artifact age across RUNNING arms
if [ "$RUNNING" -gt 0 ]; then
  NEWEST=$(find "$ROOT" -type f \( -name "*.json" -o -name "*.log" -o -name "*.patch" \) -newer "$STATE" 2>/dev/null | head -1)
  if [ -f "$STATE" ] && [ -z "$NEWEST" ]; then
    LAST=$(stat -c %Y "$STATE")
    AGE=$(( (NOW - LAST) / 60 ))
    [ "$AGE" -ge 50 ] && alarm "no new artifacts for ${AGE}min with $RUNNING arm(s) RUNNING (stall?)"
  fi
fi
touch "$STATE"

# 3. launcher dead but arms incomplete
if [ -z "$LAUNCHER_ALIVE" ] && [ $((DONE)) -lt 5 ] && [ "$RUNNING" -eq 0 ] && [ "$PENDING" -gt 0 ]; then
  alarm "launcher dead with $PENDING arm(s) never started"
fi
if [ -z "$LAUNCHER_ALIVE" ] && [ "$RUNNING" -gt 0 ]; then
  say "note: launcher dead but $RUNNING driver(s) still running (orphaned-but-alive arms)"
fi

# 4. resources
FREE_G=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
[ "$FREE_G" -lt 15 ] && alarm "disk low: ${FREE_G}G free"
say "disk_free=${FREE_G}G"
ORPHANS=$(pgrep -fc -- "--serve --socket" || true)
PREV_ORPHANS=$(cat "$ROOT/.orphan_count" 2>/dev/null || echo "${ORPHANS:-0}")
echo "${ORPHANS:-0}" > "$ROOT/.orphan_count"
GROWTH=$(( ${ORPHANS:-0} - PREV_ORPHANS ))
{ [ "$GROWTH" -gt 5 ] || [ "${ORPHANS:-0}" -gt 40 ]; } && alarm "marketd orphans: ${ORPHANS:-0} (growth +$GROWTH; known stale baseline ~24, owner cleanup pending)"
say "marketd_procs=${ORPHANS:-0} growth=$GROWTH"
STUCK=$(docker ps -q --filter "name=sweb.eval" | wc -l)
say "eval_containers_running=$STUCK"

# 5. completion summary when all arms terminal
if [ "$DONE" -eq 5 ]; then
  say "ALL_ARMS_DONE — per-arm verdicts:"
  for label in 0 inf 0p5 1 2; do
    v="$ROOT/tau_$label/verdict.json"
    [ -f "$v" ] && say "  tau_$label verdict present ($(wc -c < "$v") bytes)" || alarm "tau_$label DONE but verdict.json missing"
  done
fi

exit $ALARM

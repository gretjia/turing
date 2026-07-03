#!/usr/bin/env bash
# HW-SW-002 B1 — canonical TuringOS IPQC checkpoint interval calculator.
#
# ipqc_interval = max(25, floor(eta_steps * (0.15 - min(0.10, failure_rate))))
#
# This is the roadmap/TuringOS-native contract (distinct from the
# harness-internal checkpoint formula used elsewhere in the loop skill).
# All arithmetic is pure integer/string math: failure_rate is parsed into an
# exact fixed-point numerator (scale 10000) with no floating point involved,
# so the result never depends on binary floating-point rounding.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: calc-ipqc-interval.sh ETA_STEPS FAILURE_RATE

Computes the canonical TuringOS IPQC checkpoint interval:
  ipqc_interval = max(25, floor(eta_steps * (0.15 - min(0.10, failure_rate))))

  ETA_STEPS      non-negative integer (planned step budget)
  FAILURE_RATE   decimal in [0, 1], up to 4 fractional digits (e.g. 0.08)

Prints the resulting integer interval to stdout. Exits 2 with this usage
message on stderr for malformed input.
EOF
}

if [ $# -ne 2 ]; then
  usage >&2
  exit 2
fi

ETA_STEPS="$1"
FAILURE_RATE="$2"

if ! [[ "$ETA_STEPS" =~ ^[0-9]+$ ]]; then
  usage >&2
  exit 2
fi

if ! [[ "$FAILURE_RATE" =~ ^[0-9]+\.[0-9]{1,4}$ || "$FAILURE_RATE" =~ ^[0-9]+$ ]]; then
  usage >&2
  exit 2
fi

SCALE=10000

# Parse ETA_STEPS as base-10 (avoid bash arithmetic treating a leading "0" as octal).
eta_num=$((10#$ETA_STEPS))

# Parse FAILURE_RATE into an exact integer numerator over SCALE — pure
# integer/string arithmetic, no floating point anywhere.
if [[ "$FAILURE_RATE" == *.* ]]; then
  int_part="${FAILURE_RATE%%.*}"
  frac_part="${FAILURE_RATE#*.}"
else
  int_part="$FAILURE_RATE"
  frac_part=""
fi
while [ "${#frac_part}" -lt 4 ]; do
  frac_part="${frac_part}0"
done
int_part_num=$((10#$int_part))
frac_part_num=$((10#$frac_part))
fr_scaled=$(( int_part_num * SCALE + frac_part_num ))

CEIL_15=$(( 15 * SCALE / 100 ))  # 0.15 * SCALE
CAP_10=$(( 10 * SCALE / 100 ))   # 0.10 * SCALE

min_fr=$fr_scaled
if [ "$min_fr" -gt "$CAP_10" ]; then
  min_fr=$CAP_10
fi

remainder_scaled=$(( CEIL_15 - min_fr ))
if [ "$remainder_scaled" -lt 0 ]; then
  remainder_scaled=0
fi

raw=$(( eta_num * remainder_scaled / SCALE ))

result=$raw
if [ "$result" -lt 25 ]; then
  result=25
fi

echo "$result"

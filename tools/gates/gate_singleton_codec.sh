#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

is_allowed_path() {
  case "$1" in
    src/turingos/codec.py) return 0 ;; # Rust owner client plus labeled Python xcheck fixture.
    src/turingos/tape.py) return 0 ;; # Legacy Python Tape path, demoted in M1e.
    src/turingos/replay.py) return 0 ;; # Replay manifest digest helper, not substrate owner.
    tools/bench/audit_micro_tape_decision_dag.py) return 0 ;; # Independent auditor by design.
    tools/bench/audit_mini_swe_bench_plan.py) return 0 ;; # Legacy plan digest helper.
    tools/bench/mini_swe_bench_grok_headless.py) return 0 ;; # Legacy seed digest helper.
    tools/bench/prepare_stage12_run_plan.py) return 0 ;; # JSONL fixture materializer.
    tools/bench/run_mini_swe_bench_substrate_smoke.py) return 0 ;; # Legacy smoke harness shim.
    tools/headless/fixture_probe.py) return 0 ;; # Headless fixture digest helper.
    tools/headless/grok_verify.py) return 0 ;; # Verifier packet digest helper.
    tools/headless/headless_common.py) return 0 ;; # Shared verifier packet digest helper.
    *) return 1 ;;
  esac
}

scan_dirs() {
  local root="$1"
  local candidates=(
    "$root/src"
    "$root/tools/bench"
    "$root/tools/headless"
    "$root/crates"
  )
  local found=0
  for path in "${candidates[@]}"; do
    if [[ -d "$path" ]]; then
      printf '%s\n' "$path"
      found=1
    fi
  done
  if [[ "$found" -eq 0 ]]; then
    return 3
  fi
}

gate_scan() {
  local root="$1"
  local hits
  hits="$(mktemp)"

  mapfile -t dirs < <(scan_dirs "$root") || {
    echo "SINGLETON_CODEC_NOT_RUN no scan directories" >&2
    rm -f "$hits"
    return 3
  }

  rg -n --no-heading -g '*.py' \
    'def[[:space:]]+(canonical_bytes|canonical_dumps|canonical_json_bytes)[[:space:]]*\(' \
    "${dirs[@]}" >>"$hits" || true
  rg -n --no-heading -g '*.py' \
    'json\.dumps\([^#]*(sort_keys[[:space:]]*=[[:space:]]*True[^#]*separators[[:space:]]*=|separators[[:space:]]*=[^#]*sort_keys[[:space:]]*=[[:space:]]*True)' \
    "${dirs[@]}" >>"$hits" || true

  local bad=0
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    local path rel
    path="${hit%%:*}"
    rel="${path#"$root"/}"
    if ! is_allowed_path "$rel"; then
      echo "SINGLETON_CODEC_FAIL $hit"
      bad=1
    fi
  done <"$hits"

  if [[ "$bad" -ne 0 ]]; then
    rm -f "$hits"
    return 1
  fi
  rm -f "$hits"
  echo "SINGLETON_CODEC_PASS"
}

wide_report() {
  local root="$1"
  mapfile -t dirs < <(scan_dirs "$root") || return 3
  rg -n --no-heading -g '*.py' 'sort_keys[[:space:]]*=[[:space:]]*True' "${dirs[@]}" || true
}

self_test() {
  local work
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN
  mkdir -p "$work/src/turingos" "$work/tools/bench"
  printf '%s\n' \
    'import json' \
    'def canonical_bytes(value):' \
    '    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")' \
    >"$work/src/turingos/codec.py"
  gate_scan "$work" >/dev/null

  printf '%s\n' \
    'import json' \
    'def canonical_bytes(value):' \
    '    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")' \
    >"$work/tools/bench/bad.py"
  if gate_scan "$work" >/dev/null; then
    echo "SINGLETON_CODEC_SELF_TEST_FAIL tamper fixture was not detected" >&2
    return 1
  fi
  echo "SINGLETON_CODEC_SELF_TEST_PASS"
}

case "${1:-}" in
  --self-test)
    self_test
    ;;
  --wide)
    wide_report "${M1A_SCAN_ROOT:-$repo_root}"
    gate_scan "${M1A_SCAN_ROOT:-$repo_root}"
    ;;
  "" )
    gate_scan "${M1A_SCAN_ROOT:-$repo_root}"
    ;;
  * )
    echo "usage: $0 [--self-test|--wide]" >&2
    exit 2
    ;;
esac

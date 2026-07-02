#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

is_allowed_path() {
  case "$1" in
    crates/turing-git-tape/*) return 0 ;; # Designated sovereign-ref writer.
    src/turingos/tape.py) return 0 ;; # Legacy Python Tape path, demoted in M1e.
    tools/bench/run_mini_swe_bench_substrate_smoke.py) return 0 ;; # Legacy harness shim until routed.
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
    echo "REF_LINT_NOT_RUN no scan directories" >&2
    rm -f "$hits"
    return 3
  }

  rg -n --no-heading -g '*.py' -g '*.rs' -g '*.sh' \
    'update-ref|REF_AUTHORIZATION_HEAD' \
    "${dirs[@]}" >>"$hits" || true

  local bad=0
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    local path rel
    path="${hit%%:*}"
    rel="${path#"$root"/}"
    if ! is_allowed_path "$rel"; then
      echo "REF_LINT_FAIL $hit"
      bad=1
    fi
  done <"$hits"

  if [[ "$bad" -ne 0 ]]; then
    rm -f "$hits"
    return 1
  fi
  rm -f "$hits"
  echo "REF_LINT_PASS"
}

self_test() {
  local work
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN
  mkdir -p "$work/crates/turing-git-tape/src" "$work/tools/bench"
  printf '%s\n' 'pub const REF_AUTHORIZATION_HEAD: &str = "refs/turingos/authorization_head";' \
    >"$work/crates/turing-git-tape/src/append.rs"
  gate_scan "$work" >/dev/null

  printf '%s\n' 'git update-ref refs/turingos/tape_tip "$oid"' >"$work/tools/bench/bad.sh"
  if gate_scan "$work" >/dev/null; then
    echo "REF_LINT_SELF_TEST_FAIL tamper fixture was not detected" >&2
    return 1
  fi
  echo "REF_LINT_SELF_TEST_PASS"
}

case "${1:-}" in
  --self-test)
    self_test
    ;;
  "" )
    gate_scan "${M1A_SCAN_ROOT:-$repo_root}"
    ;;
  * )
    echo "usage: $0 [--self-test]" >&2
    exit 2
    ;;
esac

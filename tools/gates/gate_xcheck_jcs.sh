#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
corpus="${M1A_XCHECK_CORPUS:-$repo_root/tools/gates/corpus_jcs_extended.jsonl}"

run_xcheck() {
  local corpus_path="$1"
  local work
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN

  PYTHONPATH="$repo_root/src" python3 "$repo_root/tools/gates/xcheck_emit.py" "$corpus_path" >"$work/python.tsv"
  cargo run -q -p turing-xcheck <"$corpus_path" >"$work/rust.tsv"
  diff -u "$work/python.tsv" "$work/rust.tsv" >"$work/diff.txt" || {
    cat "$work/diff.txt"
    return 1
  }
  local cases
  cases="$(grep -Ev '^[[:space:]]*(#|$)' "$corpus_path" | wc -l | tr -d ' ')"
  echo "XCHECK_PASS corpus=$corpus_path cases=$cases"
}

self_test() {
  local work
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN

  printf '%s\n' '{"z":2,"a":"é","control":"\u0000"}' >"$work/corpus.jsonl"
  PYTHONPATH="$repo_root/src" python3 "$repo_root/tools/gates/xcheck_emit.py" "$work/corpus.jsonl" >"$work/python.tsv"
  cargo run -q -p turing-xcheck <"$work/corpus.jsonl" >"$work/rust.tsv"
  diff -u "$work/python.tsv" "$work/rust.tsv" >/dev/null

  cp "$work/rust.tsv" "$work/tampered.tsv"
  printf '%s\n' '999	00' >>"$work/tampered.tsv"
  if diff -u "$work/python.tsv" "$work/tampered.tsv" >/dev/null; then
    echo "XCHECK_SELF_TEST_FAIL tamper fixture was not detected" >&2
    return 1
  fi
  echo "XCHECK_SELF_TEST_PASS"
}

case "${1:-}" in
  --self-test)
    self_test
    ;;
  "" )
    run_xcheck "$corpus"
    ;;
  * )
    echo "usage: $0 [--self-test]" >&2
    exit 2
    ;;
esac

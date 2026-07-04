#!/usr/bin/env bash
# HW-SW-002 B3 — "no macro-as-micro" sufficiency audit.
#
# Default mode proves the invariant with the real integration tests that pin
# it: turing-kernel's head-transition tests (accepted_head, authorization_head,
# head_effect_tamper) and turing-replay's replay_determinism test all green.
#
# --scope projections is a fast grep-only mode: it asserts the reducer
# (crates/turing-kernel) is the sole head-mover by confirming no
# `refs/turingos/accepted_head` write-site constant exists outside
# crates/turing-kernel/ and crates/turing-git-tape/.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: audit-no-macro-as-micro.sh [--scope projections]

Default:
  cargo test -p turing-kernel --test accepted_head --test authorization_head \
    --test head_effect_tamper
  cargo test -p turing-replay --test replay_determinism

--scope projections: grep-only fast mode asserting the reducer is the sole
  head-mover (no refs/turingos/accepted_head write sites outside
  crates/turing-kernel/ and crates/turing-git-tape/).
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

fail() {
  echo "FAIL: $1"
  exit 1
}

SCOPE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --scope)
      [ $# -ge 2 ] || { usage >&2; exit 2; }
      SCOPE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

if [ -n "$SCOPE" ] && [ "$SCOPE" != "projections" ]; then
  usage >&2
  exit 2
fi

if [ "$SCOPE" = "projections" ]; then
  # Code references (not doc comments) to the accepted_head ref path, outside
  # the two crates allowed to hold write sites for it.
  hits="$(grep -rn 'refs/turingos/accepted_head' --include='*.rs' "$REPO_ROOT/crates" \
    | grep -v -E "^${REPO_ROOT}/crates/turing-kernel/|^${REPO_ROOT}/crates/turing-git-tape/" \
    | grep -v -E ':[0-9]+:[[:space:]]*///?' || true)"
  if [ -n "$hits" ]; then
    fail "refs/turingos/accepted_head write-site reference outside turing-kernel/turing-git-tape: $hits"
  fi
  echo "PASS: reducer is the sole head-mover (no accepted_head write sites outside turing-kernel/turing-git-tape)"
  exit 0
fi

echo "running: cargo test -p turing-kernel --test accepted_head --test authorization_head --test head_effect_tamper --quiet"
if ! ( cd "$REPO_ROOT" && cargo test -p turing-kernel --test accepted_head --test authorization_head --test head_effect_tamper --quiet ); then
  fail "cargo test -p turing-kernel (accepted_head/authorization_head/head_effect_tamper) failed"
fi
echo "PASS: turing-kernel head-transition tests green (accepted_head, authorization_head, head_effect_tamper)"

echo "running: cargo test -p turing-replay --test replay_determinism --quiet"
if ! ( cd "$REPO_ROOT" && cargo test -p turing-replay --test replay_determinism --quiet ); then
  fail "cargo test -p turing-replay --test replay_determinism failed"
fi
echo "PASS: turing-replay replay_determinism test green"

echo "PASS: audit-no-macro-as-micro complete"

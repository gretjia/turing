#!/usr/bin/env bash
# HW-SW-002 B2 — approval byte-surface equivalence audit.
#
# Approval bytes are sovereignty-bearing: every consumer (visible card hash,
# signature, gate replay) must sign/display/replay the exact same canonical
# payload bytes. This audit greps ApprovalByteSurfaces for its four
# byte-surface fields, then runs `cargo test -p turing-approval` to prove
# they stay byte-equivalent at runtime.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: audit-approval-bytes-equivalence.sh

Verifies ApprovalByteSurfaces still exposes all four signed-byte-surface
fields (canonical_bytes, visible_card_hash_bytes, signed_bytes,
gate_replay_bytes) in crates/turing-approval/src/lib.rs, then runs
`cargo test -p turing-approval` to prove the four surfaces stay
byte-equivalent at runtime.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi
if [ $# -ne 0 ]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APPROVAL_LIB="$REPO_ROOT/crates/turing-approval/src/lib.rs"

fail() {
  echo "FAIL: $1"
  exit 1
}

[ -f "$APPROVAL_LIB" ] || fail "source file missing: $APPROVAL_LIB"

grep -q "struct ApprovalByteSurfaces" "$APPROVAL_LIB" \
  || fail "ApprovalByteSurfaces struct not found in $APPROVAL_LIB"

for field in canonical_bytes visible_card_hash_bytes signed_bytes gate_replay_bytes; do
  grep -q "pub $field: Vec<u8>" "$APPROVAL_LIB" \
    || fail "byte-surface field missing: $field in ApprovalByteSurfaces"
done
echo "PASS: all four byte-surface fields present on ApprovalByteSurfaces (canonical_bytes, visible_card_hash_bytes, signed_bytes, gate_replay_bytes)"

echo "running: cargo test -p turing-approval --quiet"
if ! ( cd "$REPO_ROOT" && cargo test -p turing-approval --quiet ); then
  fail "cargo test -p turing-approval failed"
fi
echo "PASS: cargo test -p turing-approval green"

# HW-SW-005 B2 — explicitly exercise the four-surface mutation property suite
# (seeded in-file PRNG, >=1024 honest + >=1024 tampered cases across all six
# tamper classes; zero honest rejections, zero tamper acceptances, no panics).
echo "running: cargo test -p turing-approval --test prop_approval_byte_surfaces"
if ! ( cd "$REPO_ROOT" && cargo test -p turing-approval --test prop_approval_byte_surfaces --quiet ); then
  fail "prop_approval_byte_surfaces (four-surface mutation suite) failed"
fi
echo "PASS: prop_approval_byte_surfaces four-surface mutation suite green"

echo "PASS: audit-approval-bytes-equivalence complete"

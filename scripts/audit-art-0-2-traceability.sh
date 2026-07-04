#!/usr/bin/env bash
# HW-SW-001 A1 — Art. 0.2 10-commit traceability audit.
#
# Verifies the docs/roadmap/secure_os_18_month/02_software_sufficiency_proof.md
# §1.3 table (10 rows, Commit 1..10, each mapped to its frozen constitutional
# V-code set) and that the real source anchors the table names actually
# resolve in this checkout. Optionally checks the conditional head-order
# invariant when runtime tape refs exist.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: audit-art-0-2-traceability.sh [--commit N]

Checks, in order:
  (a) matrix doc exists and its §1.3 table has exactly 10 data rows,
      Commit 1..10 each present once
  (b) every row's "violation closed" cell matches the constitutional
      V-code contract
  (c) real source anchors resolve (ApprovalByteSurfaces, SignatureRoute,
      HardwareFuture, trait SigningBackend, refs/turingos/tape_tip,
      replay_determinism.rs)
  (d) head-order (conditional): only enforced when refs/turingos/tape_tip
      exists in this checkout; N/A in a dev checkout with no tape refs

  --commit N   run only row N's matrix check plus the anchor checks
               (skips the full 10-row scan and the head-order check)
  -h, --help   show this help

Env:
  TURINGOS_WORK_ROOT   workspace root (default: /home/zephryj/turingos_backup/work)
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_ROOT="${TURINGOS_WORK_ROOT:-/home/zephryj/turingos_backup/work}"
MATRIX_DOC="$WORK_ROOT/docs/roadmap/secure_os_18_month/02_software_sufficiency_proof.md"

fail() {
  echo "FAIL: $1"
  exit 1
}

COMMIT_FILTER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit)
      [ $# -ge 2 ] || { usage >&2; exit 2; }
      COMMIT_FILTER="$2"
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

# Frozen contract: constitution's Art. 0.2 repair list, Commit -> V-code set
# (comma-separated, no spaces, order matters).
declare -A EXPECTED_VCODES=(
  [1]="V-01,V-06,V-18"
  [2]="V-02,V-03,V-22"
  [3]="V-04,V-05,V-15,V-16"
  [4]="V-03,V-09,V-13"
  [5]="V-08a,V-17"
  [6]="V-07"
  [7]="V-08b,V-22"
  [8]="V-10,V-11,V-14"
  [9]="V-19,V-21"
  [10]="V-18,V-24"
)

# ---- (a) + (b): matrix doc exists, 10 rows, V-code contract --------------
[ -f "$MATRIX_DOC" ] || fail "matrix doc not found at $MATRIX_DOC"

mapfile -t ROW_LINES < <(grep -E '^\| *[0-9]+ *\|' "$MATRIX_DOC" || true)

declare -A SEEN_COMMITS=()
for line in "${ROW_LINES[@]}"; do
  IFS='|' read -r _ f_commit f_vcodes _rest <<<"$line"
  commit="$(echo "$f_commit" | tr -d '[:space:]')"
  vcodes="$(echo "$f_vcodes" | tr -d '[:space:]')"
  if [ -n "${SEEN_COMMITS[$commit]:-}" ]; then
    fail "duplicate row for commit $commit in matrix table"
  fi
  SEEN_COMMITS[$commit]="$vcodes"
done

if [ -n "$COMMIT_FILTER" ]; then
  vcodes="${SEEN_COMMITS[$COMMIT_FILTER]:-}"
  [ -n "$vcodes" ] || fail "commit $COMMIT_FILTER not present in matrix table"
  expected="${EXPECTED_VCODES[$COMMIT_FILTER]:-}"
  [ -n "$expected" ] || fail "commit $COMMIT_FILTER has no known V-code contract"
  [ "$vcodes" = "$expected" ] || fail "commit $COMMIT_FILTER: expected V-codes $expected, got $vcodes"
  echo "PASS: matrix row $COMMIT_FILTER V-codes = $vcodes"
else
  row_count="${#SEEN_COMMITS[@]}"
  [ "$row_count" -eq 10 ] || fail "expected exactly 10 data rows, found $row_count"
  for commit in $(seq 1 10); do
    [ -n "${SEEN_COMMITS[$commit]:-}" ] || fail "commit $commit missing from matrix table"
    expected="${EXPECTED_VCODES[$commit]}"
    actual="${SEEN_COMMITS[$commit]}"
    [ "$actual" = "$expected" ] || fail "commit $commit: expected V-codes $expected, got $actual"
  done
  echo "PASS: matrix table has exactly 10 rows (commit 1..10), all V-code sets match constitutional contract"
fi

# ---- (c): real source anchors resolve -------------------------------------
APPROVAL_LIB="$REPO_ROOT/crates/turing-approval/src/lib.rs"
LOOP_LIB="$REPO_ROOT/crates/turing-loop/src/lib.rs"
REPLAY_TEST="$REPO_ROOT/crates/turing-replay/tests/replay_determinism.rs"

[ -f "$APPROVAL_LIB" ] || fail "anchor file missing: $APPROVAL_LIB"
grep -q "ApprovalByteSurfaces" "$APPROVAL_LIB" || fail "anchor missing: ApprovalByteSurfaces in $APPROVAL_LIB"
grep -q "SignatureRoute" "$APPROVAL_LIB" || fail "anchor missing: SignatureRoute in $APPROVAL_LIB"
grep -q "HardwareFuture" "$APPROVAL_LIB" || fail "anchor missing: HardwareFuture in $APPROVAL_LIB"
grep -q "trait SigningBackend" "$APPROVAL_LIB" || fail "anchor missing: trait SigningBackend in $APPROVAL_LIB"

[ -f "$LOOP_LIB" ] || fail "anchor file missing: $LOOP_LIB"
grep -q "refs/turingos/tape_tip" "$LOOP_LIB" || fail "anchor missing: refs/turingos/tape_tip in $LOOP_LIB"

[ -f "$REPLAY_TEST" ] || fail "anchor file missing: $REPLAY_TEST"

echo "PASS: real source anchors resolve (ApprovalByteSurfaces, SignatureRoute, HardwareFuture, trait SigningBackend, refs/turingos/tape_tip, replay_determinism.rs)"

# ---- (d): head-order (conditional on tape refs existing) ------------------
if [ -z "$COMMIT_FILTER" ]; then
  TAPE_TIP_REFS="$(git -C "$REPO_ROOT" for-each-ref refs/turingos/tape_tip)"
  if [ -n "$TAPE_TIP_REFS" ]; then
    if git -C "$REPO_ROOT" merge-base --is-ancestor refs/turingos/accepted_head refs/turingos/authorization_head \
       && git -C "$REPO_ROOT" merge-base --is-ancestor refs/turingos/authorization_head refs/turingos/tape_tip; then
      echo "PASS: head-order (accepted_head <= authorization_head <= tape_tip)"
    else
      fail "head-order violation: accepted_head/authorization_head/tape_tip are not in ancestor order"
    fi
  else
    echo "head-order: N/A (no tape refs in dev checkout)"
  fi
fi

echo "PASS: audit-art-0-2-traceability complete"

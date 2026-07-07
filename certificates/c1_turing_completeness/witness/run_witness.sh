#!/usr/bin/env bash
# C1b — the executable witness (RES_AOC §C1, "Turing-complete under governance").
#
# Builds two governed tapes from a clean checkout with NOTHING but the real kernel
# primitives already shipped in this repo (crates/turing-git-tape, crates/turing-witness,
# crates/turing-cli), then replay-verifies both from genesis:
#
#   1. Rule 110 (Cook 2004; proven universal) run for N generations over a fixed-zero-
#      boundary row, where EVERY SINGLE CELL-UPDATE is a governed tape event: propose
#      (bit-shift lookup) -> validate (independent 8-case truth-table match) -> append
#      only on PASS.
#   2. A small universal-ish TM: the ALREADY-SHIPPED two-counter Minsky-machine
#      interpreter/emitter from `crates/turing-witness` (the C1a proof target) executing
#      `multiply_small` end-to-end, through the exact same governed append path.
#
# This script touches NOTHING outside this certificate directory: the witness crate is a
# standalone Cargo workspace (see its Cargo.toml) so the root Cargo.toml never needs a
# `members` edit, and every tape produced lands in a fresh temp directory, never inside
# the repo tree.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

on_branch="$(git -C "$REPO_ROOT" branch --show-current)"
if [[ "$on_branch" != "hci/software3-20260705" ]]; then
  echo "ABORT: expected branch hci/software3-20260705, got '$on_branch'" >&2
  exit 1
fi

WIDTH="${1:-31}"
STEPS="${2:-16}"
TM_PROGRAM="${3:-multiply_small}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/c1b_witness.XXXXXX")"
RULE110_REPO="$WORKDIR/rule110_tape"
TM_REPO="$WORKDIR/tm_tape"
trap 'echo; echo "(tape repos left on disk for inspection at: $WORKDIR)"' EXIT

echo "======================================================================"
echo " C1b GOVERNED WITNESS — RES_AOC section C1"
echo "======================================================================"
echo "repo_root : $REPO_ROOT"
echo "branch    : $on_branch"
echo "workdir   : $WORKDIR"
echo "params    : width=$WIDTH steps=$STEPS tm_program=$TM_PROGRAM"
echo

echo "-- [1/6] building the real kernel CLI (turing) from the root workspace --"
cargo build --manifest-path "$REPO_ROOT/Cargo.toml" --bin turing --quiet
TURING_BIN="$REPO_ROOT/target/debug/turing"
echo "   built: $TURING_BIN"
echo

echo "-- [2/6] building the C1b witness emitters (standalone crate, NOT a workspace member) --"
cargo build --manifest-path "$SCRIPT_DIR/Cargo.toml" --quiet
RULE110_BIN="$SCRIPT_DIR/target/debug/rule110_witness"
TM_BIN="$SCRIPT_DIR/target/debug/tm_witness"
echo "   built: $RULE110_BIN"
echo "   built: $TM_BIN"
echo

echo "-- [3/6] cargo test — proves the Rule 110 predicate gate has teeth --"
echo "   (rejects a forged proposal on all 8 truth-table cases; replay round-trip test)"
cargo test --manifest-path "$SCRIPT_DIR/Cargo.toml" --quiet
echo

echo "======================================================================"
echo " [4/6] WITNESS 1 of 2 — Rule 110 under governance"
echo " every cell-update: propose -> validate (8-case truth table) -> append"
echo "======================================================================"
"$RULE110_BIN" "$RULE110_REPO" "$WIDTH" "$STEPS"
echo

echo "-- replay --verify (Rule 110 tape, genesis to tip) --"
if RULE110_REPLAY_OUT="$("$TURING_BIN" replay --verify --micro-git "$RULE110_REPO")"; then
  echo "$RULE110_REPLAY_OUT"
  RULE110_REPLAY_STATUS="PASS"
else
  echo "$RULE110_REPLAY_OUT" >&2
  RULE110_REPLAY_STATUS="FAIL"
fi
echo "rule110_replay_verify: $RULE110_REPLAY_STATUS"
echo

echo "======================================================================"
echo " [5/6] WITNESS 2 of 2 — small universal-ish TM under governance"
echo " (two-counter Minsky machine, reusing the existing C1a turing-witness"
echo " crate's interpreter/emitter/reducer — nothing reinvented), program=$TM_PROGRAM"
echo "======================================================================"
"$TM_BIN" "$TM_REPO" "$TM_PROGRAM"
echo

echo "-- replay --verify (TM tape, genesis to tip) --"
if TM_REPLAY_OUT="$("$TURING_BIN" replay --verify --micro-git "$TM_REPO")"; then
  echo "$TM_REPLAY_OUT"
  TM_REPLAY_STATUS="PASS"
else
  echo "$TM_REPLAY_OUT" >&2
  TM_REPLAY_STATUS="FAIL"
fi
echo "tm_replay_verify: $TM_REPLAY_STATUS"
echo

echo "======================================================================"
echo " [6/6] SUMMARY"
echo "======================================================================"
echo "rule110_replay_verify : $RULE110_REPLAY_STATUS"
echo "tm_replay_verify      : $TM_REPLAY_STATUS"
echo "rule110_tape          : $RULE110_REPO"
echo "tm_tape               : $TM_REPO"

if [[ "$RULE110_REPLAY_STATUS" == "PASS" && "$TM_REPLAY_STATUS" == "PASS" ]]; then
  echo "OVERALL: PASS"
  exit 0
else
  echo "OVERALL: FAIL" >&2
  exit 1
fi

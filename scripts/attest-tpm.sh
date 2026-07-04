#!/usr/bin/env bash
# scripts/attest-tpm.sh — Phase 4 (HW-SW-010..013) TPM quote roundtrip.
#
# Every receipt this script writes is a LOCAL evidence artifact
# (evidence/loops/hw_sw_010_20260704/*.json). Quotes do not enter the tape
# this phase (Phase 6, HW-SW-017..019).
#
# Modes:
#   --simulator   swtpm user-space simulator: full createprimary/createek ->
#                 createak -> quote -> checkquote roundtrip over a
#                 caller-fixed 32-byte qualifying value. No sudo. Writes
#                 receipt_sim.json {kind:"TpmSimulator", ...}.
#   --seal-test   swtpm simulator: seal a SECONDARY (non-sovereign) secret to
#                 a PCR policy (sha256:0,7), unseal while PCRs match, extend
#                 a PCR, assert unseal now fails closed. Writes
#                 seal_test.json {sealed, unseal_ok_when_matching,
#                 unseal_fails_after_pcr_change}.
#   --real        Real /dev/tpmrm0 device (root-only): same roundtrip as
#                 --simulator, run under this script's own `sudo -n` for
#                 every tpm2-tools invocation. Writes receipt_real.json
#                 {kind:"Vtpm", ...}. Never extends a PCR on the real
#                 device (it is shared/persistent state, unlike the
#                 simulator's throwaway state dir).
#
# TODO markers below are filled in atom-by-atom (HW-SW-012/013); this
# script's --simulator mode (HW-SW-010/011) is complete.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EVIDENCE_DIR="$REPO_ROOT/evidence/loops/hw_sw_010_20260704"
PCR_SELECTION="sha256:0,7"

usage() {
  cat <<'EOF'
Usage: attest-tpm.sh --simulator | --seal-test | --real
EOF
}

# Script-global (not function-local) cleanup state: the EXIT trap fires
# after any function that set these has already returned, so it must read
# variables that are still in scope at process-exit time, not a callee's
# `local`s.
SWTPM_PID=""
CLEANUP_DIRS=()
cleanup() {
  if [ -n "$SWTPM_PID" ] && kill -0 "$SWTPM_PID" 2>/dev/null; then
    kill "$SWTPM_PID" 2>/dev/null || true
    wait "$SWTPM_PID" 2>/dev/null || true
  fi
  local d
  for d in "${CLEANUP_DIRS[@]+"${CLEANUP_DIRS[@]}"}"; do
    rm -rf "$d"
  done
}
trap cleanup EXIT

# --- shared helpers -----------------------------------------------------

# Finds a free TCP port `p` such that `p` and `p+1` (the tcti-swtpm
# control-channel convention) are both free. Small TOCTOU race window
# accepted for local dev/test use (SPEC.md: "pick whichever TCTI connects
# to reliably").
free_port_pair() {
  python3 - <<'PY'
import socket
while True:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        c.bind(("127.0.0.1", port + 1))
    except OSError:
        continue
    finally:
        c.close()
    print(port)
    break
PY
}

hex_of_file() {
  # `-v` is required: plain `od` collapses runs of identical 16-byte lines
  # into a single `*` marker, which would silently corrupt the hex string
  # for any file with repeated bytes (e.g. an all-zero PCR value) — found
  # empirically during this atom's development (see LESSONS.md).
  od -v -An -tx1 "$1" | tr -d ' \n'
}

# --- --simulator ---------------------------------------------------------

run_simulator() {
  local WORKDIR
  WORKDIR="$(mktemp -d)"
  CLEANUP_DIRS+=("$WORKDIR")
  local STATE_DIR="$WORKDIR/state"
  mkdir -p "$STATE_DIR"

  local DATA_PORT CTRL_PORT
  DATA_PORT="$(free_port_pair)"
  CTRL_PORT="$((DATA_PORT + 1))"
  local TCTI="swtpm:host=localhost,port=${DATA_PORT}"

  swtpm_setup --tpm2 --tpmstate "$STATE_DIR" --config /dev/null --createek \
    >"$WORKDIR/setup.log" 2>&1 \
    || { echo "FAIL: swtpm_setup" >&2; cat "$WORKDIR/setup.log" >&2; return 1; }

  swtpm socket --tpmstate "dir=$STATE_DIR" \
    --ctrl "type=tcp,port=${CTRL_PORT}" \
    --server "type=tcp,port=${DATA_PORT}" \
    --tpm2 --flags not-need-init &
  SWTPM_PID=$!

  export TPM2TOOLS_TCTI="$TCTI"

  # Poll via tpm2_startup itself (avoids raw-socket /dev/tcp timing quirks):
  # retry a bounded number of times with a short sleep between attempts.
  local tries=0 started=0
  while [ "$tries" -lt 60 ]; do
    if tpm2_startup -c >/dev/null 2>&1; then
      started=1
      break
    fi
    tries=$((tries + 1))
    sleep 0.2
  done
  [ "$started" -eq 1 ] || { echo "FAIL: swtpm never became reachable via tpm2_startup" >&2; return 1; }

  # swtpm/libtpms has only a small number of transient-object slots;
  # flushing before every step that loads a context is cheap insurance
  # against "out of memory for object contexts" (observed empirically
  # during this atom's development — see LESSONS.md).
  flush_transient() {
    tpm2_flushcontext -t >/dev/null 2>&1 || true
    tpm2_flushcontext -s >/dev/null 2>&1 || true
    tpm2_flushcontext -l >/dev/null 2>&1 || true
  }
  flush_transient

  tpm2_createek -c "$WORKDIR/ek.ctx" -G rsa -u "$WORKDIR/ek.pub" >/dev/null \
    || { echo "FAIL: tpm2_createek" >&2; return 1; }
  flush_transient
  tpm2_createak -C "$WORKDIR/ek.ctx" -c "$WORKDIR/ak.ctx" -G rsa -g sha256 -s rsassa \
    -u "$WORKDIR/ak.pub" -r "$WORKDIR/ak.priv" -n "$WORKDIR/ak.name" >/dev/null \
    || { echo "FAIL: tpm2_createak" >&2; return 1; }
  flush_transient

  # Caller-supplied 32-byte qualifying value (fixed/deterministic for this
  # local evidence artifact — not a sovereign-tape nonce).
  printf '%s' "turingos-hw-sw-010-simulator-qq" > "$WORKDIR/qualifying.bin"
  local QUAL_HEX
  QUAL_HEX="$(hex_of_file "$WORKDIR/qualifying.bin")"

  tpm2_quote -c "$WORKDIR/ak.ctx" -l "$PCR_SELECTION" -q "$WORKDIR/qualifying.bin" \
    -m "$WORKDIR/quote.msg" -s "$WORKDIR/quote.sig" -o "$WORKDIR/pcrs.out" -g sha256 \
    >/dev/null \
    || { echo "FAIL: tpm2_quote" >&2; return 1; }
  flush_transient

  tpm2_checkquote -u "$WORKDIR/ak.pub" -m "$WORKDIR/quote.msg" -s "$WORKDIR/quote.sig" \
    -f "$WORKDIR/pcrs.out" -q "$QUAL_HEX" >/dev/null \
    || { echo "FAIL: tpm2_checkquote (self-verify)" >&2; return 1; }

  local AK_PUB_B64 QUOTE_SIG_B64 PRODUCED_AT PCR_DIGEST
  AK_PUB_B64="$(base64 -w0 "$WORKDIR/ak.pub")"
  QUOTE_SIG_B64="$(base64 -w0 "$WORKDIR/quote.sig")"
  PCR_DIGEST="$(hex_of_file "$WORKDIR/pcrs.out")"
  PRODUCED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  mkdir -p "$EVIDENCE_DIR"
  cat > "$EVIDENCE_DIR/receipt_sim.json" <<EOF
{
  "kind": "TpmSimulator",
  "pcr_selection": "$PCR_SELECTION",
  "pcr_digest": "$PCR_DIGEST",
  "quote_sig_b64": "$QUOTE_SIG_B64",
  "ak_pub_b64": "$AK_PUB_B64",
  "qualifying_hex": "$QUAL_HEX",
  "produced_at": "$PRODUCED_AT",
  "verified": true
}
EOF
  echo "PASS: receipt_sim.json written ($EVIDENCE_DIR/receipt_sim.json)"
}

# --- mode dispatch --------------------------------------------------------

MODE="${1:-}"
case "$MODE" in
  --simulator)
    run_simulator
    ;;
  --seal-test)
    echo "TODO: HW-SW-012 not yet implemented" >&2
    exit 1
    ;;
  --real)
    echo "TODO: HW-SW-013 not yet implemented" >&2
    exit 1
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

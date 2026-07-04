#!/usr/bin/env bash
# scripts/attest-tpm.sh — Phase 4 (HW-SW-010..013) TPM quote roundtrip.
#
# Every receipt this script writes is a LOCAL evidence artifact
# (evidence/loops/hw_sw_010_20260704/*.json). Quotes do not enter the tape
# this phase (Phase 6, HW-SW-017..019).
#
# Modes:
#   --simulator   swtpm user-space simulator: full createek -> createak ->
#                 quote -> checkquote roundtrip over a caller-fixed 32-byte
#                 qualifying value. No sudo. Writes receipt_sim.json
#                 {kind:"TpmSimulator", ...}.
#   --seal-test   swtpm simulator: seal a SECONDARY (non-sovereign) demo
#                 secret to a PCR policy (sha256:0,7), unseal while PCRs
#                 match, extend a PCR, assert unseal now fails closed. The
#                 sealed key is NOT the sovereign approval key -- key
#                 custody for that stays with SigningBackend
#                 (turing-approval/src/lib.rs), untouched by this phase.
#                 Writes seal_test.json {sealed, unseal_ok_when_matching,
#                 unseal_fails_after_pcr_change}.
#   --real        Real /dev/tpmrm0 device (root-only): same quote
#                 roundtrip as --simulator, run under this script's own
#                 `sudo -n` for every tpm2-tools invocation. Writes
#                 receipt_real.json {kind:"Vtpm", ...}. Never extends a
#                 PCR on the real device (it is shared/persistent state,
#                 unlike the simulator's throwaway state dir) and never
#                 touches turing-approval / sovereign key material.
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
# `local`s (see LESSONS.md rework 1).
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
  # empirically during this atom's development (see LESSONS.md rework 2).
  od -v -An -tx1 "$1" | tr -d ' \n'
}

# swtpm/libtpms has only a small number of transient-object slots; leaving
# a loaded context around between steps starves later ones with "out of
# memory for object contexts" (LESSONS.md rework 3). Best-effort/non-fatal.
flush_transient() {
  tpm2_flushcontext -t >/dev/null 2>&1 || true
  tpm2_flushcontext -s >/dev/null 2>&1 || true
  tpm2_flushcontext -l >/dev/null 2>&1 || true
}

# Starts a fresh swtpm instance in $1 (a directory that already exists and
# is already registered in CLEANUP_DIRS by the caller). Sets TPM2TOOLS_TCTI
# and SWTPM_PID as a side effect; returns non-zero (does not exit) on
# failure so callers can report a mode-specific message.
start_swtpm() {
  local workdir="$1"
  local state_dir="$workdir/state"
  mkdir -p "$state_dir"

  local data_port ctrl_port
  data_port="$(free_port_pair)"
  ctrl_port="$((data_port + 1))"

  swtpm_setup --tpm2 --tpmstate "$state_dir" --config /dev/null --createek \
    >"$workdir/setup.log" 2>&1 \
    || { echo "FAIL: swtpm_setup" >&2; cat "$workdir/setup.log" >&2; return 1; }

  swtpm socket --tpmstate "dir=$state_dir" \
    --ctrl "type=tcp,port=${ctrl_port}" \
    --server "type=tcp,port=${data_port}" \
    --tpm2 --flags not-need-init &
  SWTPM_PID=$!

  export TPM2TOOLS_TCTI="swtpm:host=localhost,port=${data_port}"

  # Poll via tpm2_startup itself (avoids raw-socket /dev/tcp timing
  # quirks): retry a bounded number of times with a short sleep between
  # attempts.
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
  flush_transient
}

# --- --simulator ---------------------------------------------------------

run_simulator() {
  local WORKDIR
  WORKDIR="$(mktemp -d)"
  CLEANUP_DIRS+=("$WORKDIR")

  start_swtpm "$WORKDIR" || return 1

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

# --- --seal-test -----------------------------------------------------------

run_seal_test() {
  local WORKDIR
  WORKDIR="$(mktemp -d)"
  CLEANUP_DIRS+=("$WORKDIR")

  start_swtpm "$WORKDIR" || return 1

  # PCR policy: unseal is only authorized while sha256 PCRs 0,7 match the
  # values captured when the policy session below is created.
  tpm2_startauthsession -S "$WORKDIR/policy_session.ctx" >/dev/null \
    || { echo "FAIL: tpm2_startauthsession (policy creation)" >&2; return 1; }
  tpm2_policypcr -S "$WORKDIR/policy_session.ctx" -l "$PCR_SELECTION" -L "$WORKDIR/pcr.policy" \
    >/dev/null \
    || { echo "FAIL: tpm2_policypcr (policy creation)" >&2; return 1; }
  tpm2_flushcontext "$WORKDIR/policy_session.ctx" >/dev/null 2>&1 || true
  flush_transient

  # Parent for the sealed object. A plain ECC primary under the
  # endorsement hierarchy -- unrelated to, and never reused as, the AK
  # from --simulator/--real.
  tpm2_createprimary -C e -g sha256 -G ecc -c "$WORKDIR/primary.ctx" >/dev/null \
    || { echo "FAIL: tpm2_createprimary (seal parent)" >&2; return 1; }
  flush_transient

  # SECONDARY demo secret -- explicitly NOT the sovereign approval key.
  # Key custody for the real approval key stays entirely with
  # SigningBackend (turing-approval/src/lib.rs); nothing in this script
  # touches that surface.
  printf '%s' "turingos-hw-sw-012-secondary-demo-secret-not-sovereign" > "$WORKDIR/secret.bin"
  tpm2_create -C "$WORKDIR/primary.ctx" -u "$WORKDIR/sealed.pub" -r "$WORKDIR/sealed.priv" \
    -i "$WORKDIR/secret.bin" -L "$WORKDIR/pcr.policy" -c "$WORKDIR/sealed.ctx" >/dev/null \
    || { echo "FAIL: tpm2_create (seal)" >&2; return 1; }
  flush_transient
  local SEALED=true

  # Unseal while PCRs still match the policy.
  tpm2_startauthsession --policy-session -S "$WORKDIR/unseal1.ctx" >/dev/null \
    || { echo "FAIL: tpm2_startauthsession (unseal 1)" >&2; return 1; }
  tpm2_policypcr -S "$WORKDIR/unseal1.ctx" -l "$PCR_SELECTION" >/dev/null \
    || { echo "FAIL: tpm2_policypcr (unseal 1)" >&2; return 1; }
  local UNSEAL_OK_WHEN_MATCHING=false
  local UNSEALED_TEXT
  if UNSEALED_TEXT="$(tpm2_unseal -c "$WORKDIR/sealed.ctx" -p "session:$WORKDIR/unseal1.ctx" 2>"$WORKDIR/unseal1.err")"; then
    if [ "$UNSEALED_TEXT" = "$(cat "$WORKDIR/secret.bin")" ]; then
      UNSEAL_OK_WHEN_MATCHING=true
    else
      echo "FAIL: unsealed text did not match the original secret" >&2
      return 1
    fi
  else
    echo "FAIL: unseal while PCRs match was expected to succeed:" >&2
    cat "$WORKDIR/unseal1.err" >&2
    return 1
  fi
  tpm2_flushcontext "$WORKDIR/unseal1.ctx" >/dev/null 2>&1 || true
  flush_transient

  # Extend PCR 0 (simulator-only state; never done against --real, whose
  # PCRs are the workspace's shared/persistent hardware state).
  tpm2_pcrextend "0:sha256=0000000000000000000000000000000000000000000000000000000000000000" \
    >/dev/null \
    || { echo "FAIL: tpm2_pcrextend" >&2; return 1; }
  flush_transient

  # Unseal again: policy is no longer satisfied, this MUST fail closed.
  tpm2_startauthsession --policy-session -S "$WORKDIR/unseal2.ctx" >/dev/null \
    || { echo "FAIL: tpm2_startauthsession (unseal 2)" >&2; return 1; }
  tpm2_policypcr -S "$WORKDIR/unseal2.ctx" -l "$PCR_SELECTION" >/dev/null \
    || { echo "FAIL: tpm2_policypcr (unseal 2)" >&2; return 1; }
  local UNSEAL_FAILS_AFTER_PCR_CHANGE=false
  if tpm2_unseal -c "$WORKDIR/sealed.ctx" -p "session:$WORKDIR/unseal2.ctx" \
      >"$WORKDIR/unseal2.out" 2>"$WORKDIR/unseal2.err"; then
    echo "FAIL: unseal succeeded after a PCR change -- policy is not enforcing" >&2
    return 1
  else
    UNSEAL_FAILS_AFTER_PCR_CHANGE=true
  fi
  tpm2_flushcontext "$WORKDIR/unseal2.ctx" >/dev/null 2>&1 || true

  mkdir -p "$EVIDENCE_DIR"
  cat > "$EVIDENCE_DIR/seal_test.json" <<EOF
{
  "sealed": $SEALED,
  "unseal_ok_when_matching": $UNSEAL_OK_WHEN_MATCHING,
  "unseal_fails_after_pcr_change": $UNSEAL_FAILS_AFTER_PCR_CHANGE
}
EOF
  echo "PASS: seal_test.json written ($EVIDENCE_DIR/seal_test.json)"

  [ "$SEALED" = "true" ] && [ "$UNSEAL_OK_WHEN_MATCHING" = "true" ] \
    && [ "$UNSEAL_FAILS_AFTER_PCR_CHANGE" = "true" ]
}

# --- --real ----------------------------------------------------------------

run_real() {
  echo "TODO: HW-SW-013 not yet implemented" >&2
  return 1
}

# --- mode dispatch --------------------------------------------------------

MODE="${1:-}"
case "$MODE" in
  --simulator)
    run_simulator
    ;;
  --seal-test)
    run_seal_test
    ;;
  --real)
    run_real
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

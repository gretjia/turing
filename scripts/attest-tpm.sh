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
# TODO markers below are filled in atom-by-atom (HW-SW-010/012/013); this
# skeleton intentionally fails every mode until then (red-first).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EVIDENCE_DIR="$REPO_ROOT/evidence/loops/hw_sw_010_20260704"

usage() {
  cat <<'EOF'
Usage: attest-tpm.sh --simulator | --seal-test | --real
EOF
}

MODE="${1:-}"
case "$MODE" in
  --simulator)
    echo "TODO: HW-SW-010 not yet implemented" >&2
    exit 1
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

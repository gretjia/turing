#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VALIDATOR="$ROOT/m5_verification/tools/validate_closure_certificate.py"
CORPUS="$ROOT/m5_verification/corpus/closure_certificate_selftest"
PACKET="$CORPUS/PACKET_MANIFEST.json"

run_accept() {
  local cert="$1"
  local out
  out="$(python3 "$VALIDATOR" "$cert" "$PACKET")"
  [[ "$out" == "VALID" ]]
}

run_reject() {
  local cert="$1"
  local reason="$2"
  local out
  set +e
  out="$(python3 "$VALIDATOR" "$cert" "$PACKET" 2>&1)"
  local status=$?
  set -e
  [[ "$status" -ne 0 ]]
  [[ "$out" == *"REJECT:$reason"* ]]
}

run_accept "$CORPUS/cert_valid_FIXTURE.json"
run_reject "$CORPUS/cert_implementer_family_FIXTURE.json" "verifier_family"
run_reject "$CORPUS/cert_custody_false_FIXTURE.json" "custody_booleans"
run_reject "$CORPUS/cert_subject_digest_mismatch_FIXTURE.json" "subject_digest_mismatch"
run_reject "$CORPUS/cert_disjunctive_hatch_FIXTURE.json" "disjunctive_escape_hatch"

echo "PASS closure certificate validator self-test corpus"

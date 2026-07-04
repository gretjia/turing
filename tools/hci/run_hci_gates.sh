#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR=""
SELF_TEST=0

usage() {
  echo "usage: $0 [--self-test] --out-dir <path>"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --self-test)
      SELF_TEST=1
      shift
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$OUT_DIR" ]]; then
  echo "--out-dir is required" >&2
  usage >&2
  exit 2
fi

mkdir -p "$OUT_DIR"
cd "$ROOT"

run_logged() {
  local name="$1"
  shift
  "$@" >"$OUT_DIR/${name}.stdout.txt" 2>"$OUT_DIR/${name}.stderr.txt"
}

self_test() {
  test -x tools/hci/make_fixture_micro_tape.py
  test -f tools/hci/audit_projection_integrity.py
  test -f schemas/operator/operator_view_snapshot.v1.provenance.json
  python3 tools/hci/make_fixture_micro_tape.py \
    --out "$OUT_DIR/self_test_micro_tape" \
    --summary-json "$OUT_DIR/self_test_fixture.json" \
    >"$OUT_DIR/self_test_fixture.stdout.txt"
  echo "HCI_GATES_SELF_TEST_PASS"
}

if [[ "$SELF_TEST" -eq 1 ]]; then
  self_test
  exit 0
fi

run_logged hci_no_write_self_test bash tools/hci/gate_hci_no_write.sh --self-test
run_logged hci_no_write_gate bash tools/hci/gate_hci_no_write.sh
run_logged projection_clippy cargo clippy -p turing-projection --all-targets -- \
  -D clippy::disallowed_methods \
  -D clippy::disallowed_types
run_logged cli_dynamic_gates cargo test -p turing-cli --test cli_gates operator_command_matrix --quiet
run_logged cli_projection_tests cargo test -p turing-cli -p turing-projection --tests --quiet
run_logged python_hci_tests env PYTHONPATH=src python3 -m pytest \
  tests/test_operator_agent.py \
  tests/audit \
  tests/e2e \
  tests/test_hci_no_write_gate.py \
  tests/test_hci_projection_integrity.py \
  -q

python3 tools/hci/make_fixture_micro_tape.py \
  --out "$OUT_DIR/micro_tape" \
  --summary-json "$OUT_DIR/fixture.json" \
  >"$OUT_DIR/fixture.stdout.txt"
cargo run -p turing-cli --quiet -- status --micro-git "$OUT_DIR/micro_tape" --json \
  >"$OUT_DIR/operator_snapshot.json" \
  2>"$OUT_DIR/operator_snapshot.stderr.txt"
cargo run -p turing-cli --quiet -- status --micro-git "$OUT_DIR/micro_tape" \
  >"$OUT_DIR/operator_status.txt" \
  2>"$OUT_DIR/operator_status.stderr.txt"
python3 tools/hci/audit_projection_integrity.py \
  --micro-git "$OUT_DIR/micro_tape" \
  --snapshot-json "$OUT_DIR/operator_snapshot.json" \
  --text-output "$OUT_DIR/operator_status.txt" \
  --provenance schemas/operator/operator_view_snapshot.v1.provenance.json \
  --repo-root "$ROOT" \
  --out "$OUT_DIR/hci_projection_integrity_verdict.json" \
  >"$OUT_DIR/hci_projection_integrity.stdout.txt" \
  2>"$OUT_DIR/hci_projection_integrity.stderr.txt"

python3 - "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
verdict = json.loads((out / "hci_projection_integrity_verdict.json").read_text())
summary = {
    "schema_id": "hci_gates_result.v1",
    "verdict": "PASS",
    "projection_integrity_verdict": verdict["verdict"],
    "checks": verdict["checks"],
    "status_ceiling": "ADDRESSED",
}
(out / "hci_gates_result.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
PY

echo "HCI_GATES_PASS"

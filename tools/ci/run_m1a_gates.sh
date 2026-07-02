#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

case "${1:-}" in
  --self-test)
    bash tools/gates/gate_xcheck_jcs.sh --self-test
    bash tools/gates/gate_singleton_codec.sh --self-test
    python3 tools/gates/lint_no_second_codec.py --self-test
    bash tools/gates/gate_ref_lint.sh --self-test
    echo "M1A_SELF_TEST_PASS"
    ;;
  "" )
    bash tools/gates/gate_xcheck_jcs.sh
    bash tools/gates/gate_singleton_codec.sh
    python3 tools/gates/lint_no_second_codec.py
    bash tools/gates/gate_ref_lint.sh
    echo "M1A_GATES_PASS"
    ;;
  * )
    echo "usage: $0 [--self-test]" >&2
    exit 2
    ;;
esac

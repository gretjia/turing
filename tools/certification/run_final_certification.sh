#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLAN_ROOT="$(cd "$REPO/.." && pwd)/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
OUT=""
BUDGET_MICROUSD="0"

usage() {
  echo "usage: $0 [--self-test] [--repo REPO] [--plan-root PLAN] [--out ROOT] [--budget-ceiling-microusd N]" >&2
}

if [ "${1:-}" = "--self-test" ]; then
  python3 "$SCRIPT_DIR/score_certification.py" --self-test
  python3 "$SCRIPT_DIR/run_scenarios.py" --self-test
  python3 "$SCRIPT_DIR/gen_fixture_tape.py" --self-test
  python3 "$SCRIPT_DIR/gen_fixture_broadcast_rules.py" --self-test
  python3 "$SCRIPT_DIR/checks/entry_criteria.py" --self-test
  python3 - <<'PY' "$SCRIPT_DIR"
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ("w1.json", "w2.json", "w3.json"):
    data = json.load(open(root / "workflow_scripts" / name, encoding="utf-8"))
    assert data["schema_id"] == "turingos.fce_workflow_script.v1"
    assert data["workflow_id"].startswith("FCE-W")
    assert data["steps"]
PY
  echo "FCE_HARNESS_SELF_TEST_PASS"
  exit 0
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      REPO="$2"
      shift 2
      ;;
    --plan-root)
      PLAN_ROOT="$2"
      shift 2
      ;;
    --out)
      OUT="$2"
      shift 2
      ;;
    --budget-ceiling-microusd)
      BUDGET_MICROUSD="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

CERT_SHA="$(git -C "$REPO" rev-parse HEAD)"
if [ -z "$OUT" ]; then
  OUT="$REPO/evidence/certification/final_certification_$(date -u +%Y%m%d)"
fi
mkdir -p "$OUT"
cat > "$OUT/README.md" <<'EOF'
# Final Certification Evidence Root

This root is created by the FCE harness. If entry criteria fail, all scenarios remain NOT_RUN, which is a failing certification state.

Status ceiling: ADDRESSED. This harness cannot emit CLOSED, RELEASED, or SHIPPED.
EOF
cat > "$OUT/CLAIM_BOUNDARY.json" <<'EOF'
{
  "schema_id": "CLAIM_BOUNDARY.v2",
  "evidence_class": "REAL_OR_NOT_RUN_BY_ENTRY_CRITERIA",
  "claims": ["FCE harness evidence root only"],
  "non_claims": ["not shipped", "not released", "not externally verified"]
}
EOF

set +e
python3 "$SCRIPT_DIR/checks/entry_criteria.py" \
  --repo "$REPO" \
  --plan-root "$PLAN_ROOT" \
  --out "$OUT/FCE_RUN_MANIFEST.json" \
  --budget-ceiling-microusd "$BUDGET_MICROUSD"
entry_code=$?
set -e

if [ "$entry_code" -ne 0 ]; then
  echo "FCE_ENTRY_CRITERIA_NOT_MET"
  exit "$entry_code"
fi

python3 "$SCRIPT_DIR/run_scenarios.py" \
  --root "$OUT" \
  --repo "$REPO" \
  --plan-root "$PLAN_ROOT" \
  --cert-repo-sha "$CERT_SHA" \
  --out-final "$OUT/FINAL_CERTIFICATION_VERDICT.json"

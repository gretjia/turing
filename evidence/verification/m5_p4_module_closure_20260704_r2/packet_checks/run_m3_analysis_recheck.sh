#!/usr/bin/env bash
set -euo pipefail

PACKET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAN_ROOT="$PACKET_ROOT/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
ANALYSIS_ROOT="$PLAN_ROOT/m3_uplift_lab/analysis/s01_deepseek_only_20260703"
OUT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/m5p4_m3_recheck.XXXXXX")"

cleanup() {
  rm -rf "$OUT_ROOT"
}
trap cleanup EXIT

python3 "$PLAN_ROOT/m3_uplift_lab/analysis/analyze_uplift.py" \
  --root "$ANALYSIS_ROOT" \
  --out "$OUT_ROOT"

python3 - "$ANALYSIS_ROOT" "$OUT_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

analysis_root = pathlib.Path(sys.argv[1])
out_root = pathlib.Path(sys.argv[2])
published = analysis_root / "out/UPLIFT_REPORT.json"
recomputed = out_root / "UPLIFT_REPORT.json"

for path in [published, recomputed]:
    assert path.exists(), f"missing {path}"

published_sha = hashlib.sha256(published.read_bytes()).hexdigest()
recomputed_sha = hashlib.sha256(recomputed.read_bytes()).hexdigest()
assert published_sha == "9a3862fa76381187cef83ffbbdaec5c777c739750e02b2d103f377763456c0c4"

published_report = json.loads(published.read_text(encoding="utf-8"))
recomputed_report = json.loads(recomputed.read_text(encoding="utf-8"))
assert published_report["source_root"].endswith(
    "m3_uplift_lab/analysis/s01_deepseek_only_20260703"
)
assert recomputed_report["source_root"].endswith(
    "m3_uplift_lab/analysis/s01_deepseek_only_20260703"
)
published_report["source_root"] = "<normalized>"
recomputed_report["source_root"] = "<normalized>"
assert recomputed_report == published_report, (
    f"UPLIFT_REPORT content mismatch after source_root normalization: {recomputed_sha}"
)

print("M5_P4_PACKET_M3_ANALYSIS_RECHECK_PASS")
PY

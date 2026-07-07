#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE="$ROOT/evidence/session_20260702"

python3 "$ROOT/m6_hci/assemble_m6_gate.py" \
  --root "$ROOT" \
  --evidence-dir "$EVIDENCE" \
  --recorded-at-utc "2026-07-04T05:10:00Z"

python3 - "$ROOT" "$EVIDENCE" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
evidence = pathlib.Path(sys.argv[2])

rollup_path = evidence / "M6G_ARTIFACT_ROLLUP.json"
drift_path = evidence / "M6G_DRIFT_CHECKLIST.md"
verdict_path = evidence / "M6G_GATE_VERDICT.json"
handoff_path = evidence / "M6G_M5_P4_HANDOFF_PACKET.json"
manifest_path = evidence / "M6G_ARTIFACT_MANIFEST.sha256"

for path in [rollup_path, drift_path, verdict_path, handoff_path, manifest_path]:
    assert path.exists(), f"missing {path}"

rollup = json.loads(rollup_path.read_text())
verdict = json.loads(verdict_path.read_text())
handoff = json.loads(handoff_path.read_text())

assert rollup["schema_id"] == "turingos.m6_g_artifact_rollup.v1"
assert rollup["gate_id"] == "M6.G"
assert rollup["module"] == "M6"
assert rollup["status"] == "ADDRESSED"
assert rollup["status_ceiling"] == "ADDRESSED"
assert rollup["g7_kpi"]["displayed_values_replayable"] is True
assert rollup["g7_kpi"]["zero_head_moving_paths_static_and_dynamic"] is True
assert rollup["g7_kpi"]["branch_committed_or_archived"] is True
assert rollup["all_required_items_present"] is True
assert len(rollup["required_artifacts"]) == 7
assert all(item["status"] == "PASS" for item in rollup["required_artifacts"])

assert verdict["schema_id"] == "GateVerdict.v1"
assert verdict["gate_id"] == "M6.G"
assert verdict["status"] == "ADDRESSED"
assert verdict["status_ceiling"] == "ADDRESSED"
assert len(verdict["checklist_results"]) == 7
assert all(row["verdict"] == "PASS" for row in verdict["checklist_results"])
assert verdict["not_run_is_fail"] is True
assert "M6.G is not externally verified" in verdict["non_claims"]

assert handoff["schema_id"] == "turingos.m5_p4.module_closure_handoff.v1"
assert handoff["gate_id"] == "M6.G"
assert handoff["module"] == "M6"
assert handoff["status_ceiling"] == "ADDRESSED"
assert handoff["lineage_excluded"] is True
assert "implementer_transcript" not in json.dumps(handoff).lower()
assert "reasoning" not in json.dumps(handoff).lower()
assert len(handoff["artifact_paths"]) >= 7

for item in rollup["digest_bound_artifacts"]:
    path = pathlib.Path(item["path"])
    assert path.exists(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], path

manifest_lines = manifest_path.read_text().splitlines()
for expected in [rollup_path, drift_path, verdict_path, handoff_path]:
    assert any(str(expected) in line for line in manifest_lines), expected
for line in manifest_lines:
    digest, path = line.split(maxsplit=1)
    assert hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() == digest, path

drift = drift_path.read_text()
assert drift.count("| PASS |") >= 7
assert "M6.G Drift-Check Checklist" in drift
assert "G7" in drift
assert "does not authorize HCI-B" in drift

print("M6_G_ROLLUP_CHECK_PASS")
PY

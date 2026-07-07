#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE="$ROOT/evidence/session_20260702"

python3 - "$ROOT" "$EVIDENCE" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
evidence = pathlib.Path(sys.argv[2])

rollup_path = evidence / "M5G_ARTIFACT_ROLLUP.json"
drift_path = evidence / "M5G_DRIFT_CHECKLIST.md"
verdict_path = evidence / "M5G_GATE_VERDICT.json"
handoff_path = evidence / "M5G_EXTERNAL_HANDOFF_PACKET.json"
manifest_path = evidence / "M5G_ARTIFACT_MANIFEST.sha256"

for path in [rollup_path, drift_path, verdict_path, handoff_path, manifest_path]:
    assert path.exists(), f"missing {path}"

rollup = json.loads(rollup_path.read_text())
verdict = json.loads(verdict_path.read_text())
handoff = json.loads(handoff_path.read_text())

assert rollup["schema"] == "turingos.m5_g_artifact_rollup.v1"
assert rollup["gate_id"] == "M5.G"
assert rollup["status"] == "ADDRESSED"
assert rollup["all_required_items_present"] is True
assert rollup["external_pass_artifact_present"] is True
assert rollup["processed_module_closures_cert_or_fail"] is True
assert len(rollup["required_artifacts"]) == 9
assert all(item["status"] == "PASS" for item in rollup["required_artifacts"])
assert rollup["status_ceiling"] == "ADDRESSED"

assert verdict["schema"] == "GateVerdict.v1"
assert verdict["gate_id"] == "M5.G"
assert verdict["status"] == "ADDRESSED"
assert len(verdict["checklist_results"]) == 7
assert all(row["verdict"] == "PASS" for row in verdict["checklist_results"])
assert verdict["external_pass_artifact"]["gate_id"] == "M5.P3"
assert verdict["status_ceiling_note"].startswith("implementer")
assert "M5.G is not externally verified" in verdict["non_claims"]

assert handoff["gate_id"] == "M5.G"
assert handoff["lineage_excluded"] is True
assert handoff["requested_verifier_tier"] == "external_cross_family_or_human"
assert "implementer_transcript" not in json.dumps(handoff).lower()
assert "reasoning" not in json.dumps(handoff).lower()
assert len(handoff["artifact_paths"]) >= 9

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
assert "M5.G Drift-Check Checklist" in drift
assert "does not grant SHIPPED" in drift

print("M5_G_ROLLUP_CHECK_PASS")
PY

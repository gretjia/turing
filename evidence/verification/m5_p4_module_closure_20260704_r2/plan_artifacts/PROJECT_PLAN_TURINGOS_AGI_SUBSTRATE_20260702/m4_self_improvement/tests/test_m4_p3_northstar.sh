#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ROOT="$ROOT/m4_self_improvement/real_s01_deepseek_20260703"

python3 - "$ROOT" "$RUN_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
run_root = pathlib.Path(sys.argv[2])

report_path = run_root / "NORTHSTAR_REPORT.md"
boundary_path = run_root / "CLAIM_BOUNDARY.json"
result_path = root / "m4_self_improvement/M4_P3_NORTHSTAR_RESULT.json"
manifest_path = root / "m4_self_improvement/M4_P3_NORTHSTAR_ARTIFACTS.sha256"

for path in [report_path, boundary_path, result_path, manifest_path]:
    assert path.exists(), f"missing {path}"

report = report_path.read_text()
boundary = json.loads(boundary_path.read_text())
result = json.loads(result_path.read_text())
hvpput = json.loads((run_root / "hvpput_report.v1.json").read_text())
h2 = json.loads((run_root / "causal/h2_consumption_note.json").read_text())

for heading in [
    "## Headline",
    "## Mandatory Direction Sentence",
    "## Cost Provenance",
    "## Exclusion Table",
    "## Deviation Table",
    "## Claim Boundary",
]:
    assert heading in report, f"missing skeleton heading {heading}"

class_breakdown = hvpput["class_breakdown"]
headline = (
    f"- Run-class breakdown: {class_breakdown['n_billing_complete']} BILLING_COMPLETE / "
    f"{class_breakdown['n_bounded']} BOUNDED / {class_breakdown['n_excluded']} INADMISSIBLE."
)
assert headline in report

for arm in ["A", "B", "C"]:
    value = hvpput["arms"][arm]["billing_complete_portfolio"]["hvpput_m_str"]
    assert f"{arm}: {value}" in report

h2_data = h2["h2"]
assert h2_data["positive_direction"] is False
assert h2_data["blocked_by_h1"] is True
mde_for_sentence = h2["mde_statement"].rstrip(".")
required_null = (
    f"Δ_BC = {h2_data['delta']} [CI includes 0]; "
    f"the study was powered for MDE = {mde_for_sentence}; "
    "smaller true effects are not excluded. No failure-memory efficacy claim is made."
)
assert required_null in report
assert h2["mde_statement"] in report
assert "no effect" not in report.lower()

assert boundary["schema_id"] == "m4.claim_boundary.v1"
assert boundary["failure_memory_causal_claim_allowed"] is False
assert boundary["hvpput_is_capability_claim"] is False
assert boundary["absolute_rate_is_capability_claim"] is False
assert boundary["report_status_ceiling"] == "ADDRESSED"
assert boundary["selection_policy"] == "S01_AS_FROZEN_BY_M3"
assert boundary["h2_source_sha256"] == h2["source_sha256"]

assert result["status"] == "ADDRESSED"
assert result["status_ceiling"] == "ADDRESSED"
assert result["mandatory_direction"] == "null"
assert result["claim_boundary"]["failure_memory_causal_claim_allowed"] is False

manifest = manifest_path.read_text().splitlines()
assert any(str(report_path) in line for line in manifest)
assert any(str(boundary_path) in line for line in manifest)
assert any(str(result_path) in line for line in manifest)
for line in manifest:
    digest, path = line.split(maxsplit=1)
    actual = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    assert actual == digest, f"digest mismatch for {path}"

print("M4_P3_NORTHSTAR_CHECK_PASS")
PY

#!/usr/bin/env bash
set -euo pipefail

PACKET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAN_ROOT="$PACKET_ROOT/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
RUN_ROOT="$PLAN_ROOT/m4_self_improvement/real_s01_deepseek_20260703"

python3 - "$PACKET_ROOT" "$PLAN_ROOT" "$RUN_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

packet_root = pathlib.Path(sys.argv[1])
plan_root = pathlib.Path(sys.argv[2])
run_root = pathlib.Path(sys.argv[3])
repo_root = packet_root.parents[2]

report_path = run_root / "NORTHSTAR_REPORT.md"
boundary_path = run_root / "CLAIM_BOUNDARY.json"
result_path = plan_root / "m4_self_improvement/M4_P3_NORTHSTAR_RESULT.json"
manifest_path = plan_root / "m4_self_improvement/M4_P3_NORTHSTAR_ARTIFACTS.sha256"
hvpput_path = run_root / "hvpput_report.v1.json"
h2_path = run_root / "causal/h2_consumption_note.json"

for path in [
    report_path,
    boundary_path,
    result_path,
    manifest_path,
    hvpput_path,
    h2_path,
    packet_root / "SOURCE_MAP.json",
]:
    assert path.exists(), f"missing {path}"

report = report_path.read_text(encoding="utf-8")
boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
result = json.loads(result_path.read_text(encoding="utf-8"))
hvpput = json.loads(hvpput_path.read_text(encoding="utf-8"))
h2 = json.loads(h2_path.read_text(encoding="utf-8"))

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

source_map = json.loads((packet_root / "SOURCE_MAP.json").read_text(encoding="utf-8"))
source_sha_by_path = {entry["github_path"]: entry["sha256"] for entry in source_map}
required_paths = [
    report_path,
    boundary_path,
    result_path,
    manifest_path,
    hvpput_path,
    h2_path,
]
for path in required_paths:
    github_path = path.relative_to(repo_root).as_posix()
    assert github_path in source_sha_by_path, f"missing SOURCE_MAP entry for {github_path}"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = source_sha_by_path[github_path]
    assert actual == expected, f"digest mismatch for {github_path}"

manifest_text = manifest_path.read_text(encoding="utf-8")
for original_name in [
    "NORTHSTAR_REPORT.md",
    "CLAIM_BOUNDARY.json",
    "M4_P3_NORTHSTAR_RESULT.json",
]:
    assert original_name in manifest_text

print("M5_P4_PACKET_M4_P3_NORTHSTAR_CHECK_PASS")
PY

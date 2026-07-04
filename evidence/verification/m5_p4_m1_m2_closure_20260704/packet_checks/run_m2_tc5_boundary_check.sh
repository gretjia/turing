#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
PACKET_ROOT="$REPO_ROOT/evidence/verification/m5_p4_m1_m2_closure_20260704"
PLAN_ROOT="$PACKET_ROOT/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
M2_ROOT="$REPO_ROOT/evidence/theory/turing_completeness_witness_20260703"

cd "$REPO_ROOT"
sha256sum -c "evidence/theory/turing_completeness_witness_20260703/packet/PACKET_MANIFEST.sha256"

cd "$M2_ROOT"
sha256sum -c bundle_sha256s.txt

cd "$REPO_ROOT"
PYTHONPATH=src python3 -m pytest -q tests/test_theory_tc4_audit.py tests/test_theory_tc5_packet.py
python3 tools/theory/audit_tc4_witness.py --root "evidence/theory/turing_completeness_witness_20260703" >/tmp/m5p4_m2_tc4_audit.json
python3 tools/theory/build_tc5_packet.py --root "evidence/theory/turing_completeness_witness_20260703" --check >/tmp/m5p4_m2_tc5_check.json

python3 - "$PACKET_ROOT" "$PLAN_ROOT" "$M2_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

packet_root = pathlib.Path(sys.argv[1])
plan_root = pathlib.Path(sys.argv[2])
m2_root = pathlib.Path(sys.argv[3])
repo_root = packet_root.parents[2]

tc10 = json.loads((m2_root / "verdicts/TC-10.json").read_text(encoding="utf-8"))
descriptor = json.loads((plan_root / "evidence/session_20260702/M2_TC5_PACKET_DESCRIPTOR.json").read_text(encoding="utf-8"))
tc5_verdict = json.loads((plan_root / "evidence/session_20260702/M2_TC5_VERDICT.json").read_text(encoding="utf-8"))
m2g_gate = json.loads((plan_root / "evidence/session_20260702/M2G_GATE_VERDICT.json").read_text(encoding="utf-8"))
m2g_rollup = json.loads((plan_root / "evidence/session_20260702/M2G_ARTIFACT_ROLLUP.json").read_text(encoding="utf-8"))
tc5_packet = json.loads((m2_root / "packet/M2_TC5_PACKET.json").read_text(encoding="utf-8"))
boundary = json.loads((m2_root / "packet/CLAIM_BOUNDARY.json").read_text(encoding="utf-8"))

assert tc10["gate_id"] == "TC-10"
assert tc10["verdict"] == "NOT_RUN"
assert tc10["not_run_is_fail"] is True
assert tc10["implementer_may_run"] is False
assert tc10["external_verifier_required"] is True

assert descriptor["phase"] == "M2.TC5"
assert descriptor["phase_status"] == "ADDRESSED"
assert descriptor["external_verifier"]["status"] == "NOT_RUN"
assert descriptor["claims"]["tc10_external_artifact_exists"] is False
assert descriptor["claims"]["turing_completeness_claim_allowed"] is False
assert tc5_verdict["phase"] == "M2.TC5"
assert tc5_verdict["phase_status"] == "ADDRESSED"
assert tc5_verdict["not_run_is_fail"] is True
assert tc5_verdict["explicit_non_claims"]["tc10_passed"] is False

assert m2g_gate["gate_id"] == "M2.G"
assert m2g_gate["status"] == "ADDRESSED"
assert m2g_gate["tc10_verdict"] == "NOT_RUN"
assert m2g_gate["tc10_external_artifact_exists"] is False
assert m2g_gate["turing_completeness_claim_allowed"] is False
assert m2g_rollup["tc10_blocker"]["tc10_verdict"] == "NOT_RUN"
assert m2g_rollup["ship_gate_claim_boundary"]["external_verification_claim_allowed"] is False

assert tc5_packet["phase"] == "M2.TC5"
assert tc5_packet["tc10"]["verdict"] == "NOT_RUN"
assert tc5_packet["claims"]["tc10_external_artifact_exists"] is False
assert boundary["tc10_external_artifact_exists"] is False
assert boundary["turing_completeness_claim_allowed"] is False

repo_artifacts = json.loads((packet_root / "REPO_ARTIFACTS.json").read_text(encoding="utf-8"))
repo_sha_by_path = {entry["github_path"]: entry["sha256"] for entry in repo_artifacts}
for path in [
    m2_root / "packet/M2_TC5_PACKET.json",
    m2_root / "packet/PACKET_MANIFEST.sha256",
    m2_root / "verdicts/TC-10.json",
    repo_root / "tools/theory/audit_tc4_witness.py",
    repo_root / "tools/theory/build_tc5_packet.py",
]:
    github_path = path.relative_to(repo_root).as_posix()
    assert github_path in repo_sha_by_path, f"missing REPO_ARTIFACTS entry for {github_path}"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == repo_sha_by_path[github_path], f"digest mismatch for {github_path}"

print("M5_P4_REMAINING_PACKET_M2_TC5_BOUNDARY_CHECK_PASS")
PY

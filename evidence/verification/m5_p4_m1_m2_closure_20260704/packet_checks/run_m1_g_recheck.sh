#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
PACKET_ROOT="$REPO_ROOT/evidence/verification/m5_p4_m1_m2_closure_20260704"
PLAN_ROOT="$PACKET_ROOT/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/m5p4_m1_recheck.XXXXXX")"

cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

python3 - "$PACKET_ROOT" "$PLAN_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

packet_root = pathlib.Path(sys.argv[1])
plan_root = pathlib.Path(sys.argv[2])
repo_root = packet_root.parents[2]

required = [
    plan_root / "evidence/session_20260702/M1G_ARTIFACT_ROLLUP.json",
    plan_root / "evidence/session_20260702/M1G_DRIFT_CHECKLIST.md",
    plan_root / "evidence/session_20260702/M1G_GATE_VERDICT.json",
    plan_root / "evidence/session_20260702/M1G_FRESH_CONTEXT_VERIFIER.json",
]
for path in required:
    assert path.exists(), f"missing {path}"

gate = json.loads(required[2].read_text(encoding="utf-8"))
rollup = json.loads(required[0].read_text(encoding="utf-8"))
fresh = json.loads(required[3].read_text(encoding="utf-8"))

assert gate["gate_id"] == "M1.G"
assert gate["status"] == "ADDRESSED"
assert gate["alignment_verify"] == "GREEN"
assert all(item["verdict"] == "PASS" for item in gate["checklist_results"])
assert rollup["gate"] == "M1.G"
assert rollup["status_ceiling"] == "ADDRESSED"
assert rollup["ship_gate_claim_boundary"]["external_verification_claim_allowed"] is False
assert all(status == "ADDRESSED" for status in rollup["child_phase_statuses"].values())
assert fresh["verdict"] == "PASS"

source_map = json.loads((packet_root / "SOURCE_MAP.json").read_text(encoding="utf-8"))
source_sha_by_path = {entry["github_path"]: entry["sha256"] for entry in source_map}
for path in required:
    github_path = path.relative_to(repo_root).as_posix()
    assert github_path in source_sha_by_path, f"missing SOURCE_MAP entry for {github_path}"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == source_sha_by_path[github_path], f"digest mismatch for {github_path}"

print("M5_P4_REMAINING_PACKET_M1_METADATA_CHECK_PASS")
PY

bash "$REPO_ROOT/tools/ci/run_m1a_gates.sh" --self-test
bash "$REPO_ROOT/tools/ci/run_m1a_gates.sh"

python3 "$REPO_ROOT/tools/bench/audit_micro_tape_decision_dag.py"   --coverage "$PACKET_ROOT/packet_checks/m1b_packet_coverage.json"   --strict-vpput   --strict-terminal-market   --require-authorization-head   --require-cost-provenance   --require-sandbox-provenance   --out-dir "$TMP_ROOT/m1b"

python3 "$REPO_ROOT/tools/bench/audit_micro_tape_decision_dag.py"   --coverage "$PACKET_ROOT/packet_checks/m1c_packet_coverage.json"   --strict-vpput   --strict-terminal-market   --require-authorization-head   --require-cost-provenance   --require-sandbox-provenance   --out-dir "$TMP_ROOT/m1c"

python3 - "$TMP_ROOT" <<'PY'
import json
import pathlib
import sys

tmp = pathlib.Path(sys.argv[1])
required_checks = [
    "authorization_head",
    "cost_provenance",
    "sandbox_provenance",
    "terminal_golden_path_anchors_to_accepted_head",
    "vpput_accounting",
]
for label in ["m1b", "m1c"]:
    audit = json.loads((tmp / label / "micro_tape_decision_dag_audit.json").read_text(encoding="utf-8"))
    assert audit["verdict"] == "PASS", label
    assert audit["strict_findings"] == [], label
    assert audit["aggregate"]["sandbox_host_assumed_count"] == 0, label
    run = audit["runs"][0]
    for check in required_checks:
        assert run["checks"][check] == "PASS", (label, check, run["checks"].get(check))

print("M5_P4_REMAINING_PACKET_M1_G_RECHECK_PASS")
PY

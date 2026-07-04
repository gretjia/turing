#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
PACKET="$ROOT/evidence/verification/m5_p4_m6_closure_20260704"

cd "$PACKET"
sha256sum -c PACKET_MANIFEST.sha256

cd "$ROOT"
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path.cwd()
packet = root / "evidence/verification/m5_p4_m6_closure_20260704"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

for map_name in ["SOURCE_MAP.json", "REPO_ARTIFACTS.json"]:
    entries = json.loads((packet / map_name).read_text(encoding="utf-8"))
    if not entries:
        raise SystemExit(f"empty {map_name}")
    for entry in entries:
        path = root / entry["github_path"]
        if not path.exists():
            raise SystemExit(f"missing {map_name} entry: {entry['github_path']}")
        actual = sha256(path)
        if actual != entry["sha256"]:
            raise SystemExit(
                f"digest mismatch {map_name} {entry['github_path']}: {actual} != {entry['sha256']}"
            )

gate = json.loads(
    (packet / "plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_GATE_VERDICT.json").read_text(
        encoding="utf-8"
    )
)
if gate.get("schema_id") != "GateVerdict.v1":
    raise SystemExit("bad gate verdict schema")
if gate.get("gate_id") != "M6.G":
    raise SystemExit("bad gate id")
if gate.get("status") != "ADDRESSED" or gate.get("status_ceiling") != "ADDRESSED":
    raise SystemExit("bad M6.G status ceiling")
if gate.get("not_run_is_fail") is not True:
    raise SystemExit("M6.G not_run_is_fail must be true")

kpi = gate.get("g7_kpi") or {}
required = [
    "hci_a_adr_accepted",
    "displayed_values_replayable",
    "zero_head_moving_paths_static_and_dynamic",
    "branch_committed_or_archived",
]
missing = [key for key in required if kpi.get(key) is not True]
if missing:
    raise SystemExit(f"G7 KPI not satisfied: {missing}")

checklist = gate.get("checklist_results") or []
if len(checklist) != 7 or any(item.get("verdict") != "PASS" for item in checklist):
    raise SystemExit("M6.G drift checklist is not 7/7 PASS")

packet_json = json.loads((packet / "PACKET.json").read_text(encoding="utf-8"))
if packet_json.get("targets") != ["M6.G"]:
    raise SystemExit("packet targets must be ['M6.G']")
if packet_json.get("status_ceiling") != "ADDRESSED":
    raise SystemExit("packet status ceiling must be ADDRESSED")

non_claim_text = " ".join(packet_json.get("non_claims", []) + gate.get("non_claims", []))
for required_non_claim in [
    "HCI-B",
    "write-capable console behavior",
    "SHIPPED",
    "RELEASED",
    "RATIFIED",
    "M2 enablement",
    "release eligibility",
    "FCE.RUN",
    "OG-10/genesis signature",
    "constitution-byte change",
]:
    if required_non_claim not in non_claim_text:
        raise SystemExit(f"missing required non-claim: {required_non_claim}")

print("M6_G_PACKET_LOCAL_CHECK_PASS")
PY

bash tools/hci/run_hci_gates.sh --out-dir /tmp/turing-m6g-packet-hci-gates

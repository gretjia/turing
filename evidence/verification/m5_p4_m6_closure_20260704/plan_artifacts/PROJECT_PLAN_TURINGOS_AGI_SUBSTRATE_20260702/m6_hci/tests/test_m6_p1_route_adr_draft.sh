#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if grep -q "status: accepted-addressed" "$ROOT/adr/ADR-M6-001-adopt-hci-a-projection-route.md"; then
  exec bash "$ROOT/m6_hci/tests/test_m6_p1_route_acceptance.sh"
fi

python3 - "$ROOT" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])

adr_dir = root / "adr"
m6_dir = root / "m6_hci"
result_path = m6_dir / "M6_P1_ROUTE_ADR_DRAFT_RESULT.json"
manifest_path = m6_dir / "M6_P1_ROUTE_ADR_DRAFT_ARTIFACTS.sha256"

adrs = {
    "ADR-M6-001": adr_dir / "ADR-M6-001-adopt-hci-a-projection-route.md",
    "ADR-M6-002": adr_dir / "ADR-M6-002-archive-then-rebase-rescue.md",
    "ADR-M6-003": adr_dir / "ADR-M6-003-intent-preview-verb-surface.md",
    "ADR-M6-004": adr_dir / "ADR-M6-004-projection-integrity-audit.md",
    "ADR-M6-005": adr_dir / "ADR-M6-005-layered-no-write-enforcement.md",
    "ADR-M6-006": adr_dir / "ADR-M6-006-cli-json-presentation.md",
}

required_inputs = {
    "RES_M6": (
        root / "research/RES_M6_hci_projection_console.md",
        "55b138db6ab341252223d250b056a3915f8f963b2ae1f5f19eafcdee9e20813d",
    ),
    "MODULE_M6": (
        root / "modules/MODULE_M6_hci_console.md",
        "58e07e8453d4ee69db7df785da82d479da009a7910a07cf3d75a73a1ce13c763",
    ),
}

for label, (path, digest) in required_inputs.items():
    assert path.exists(), f"missing {label}: {path}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, label

for path in [result_path, manifest_path, *adrs.values()]:
    assert path.exists(), f"missing {path}"

def text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")

def has_evidence(body: str, digest: str) -> bool:
    return digest in body and "/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/" in body

adr1 = text(adrs["ADR-M6-001"])
assert "status: proposed" in adr1
assert re.search(r"decision-makers:\s*\n\s*-\s*owner", adr1), "ADR-M6-001 must be owner-decided"
assert "owner ratification pending" in adr1
assert "HCI-A" in adr1 and "projection-only" in adr1
assert "HCI-B" in adr1 and "defer" in adr1
assert "HCI-C is forbidden" in adr1
for phrase in [
    "M1 canonical-writer/authorization question",
    "M2 TC witness is independently audited",
    "M5 external ClosureCertificate machinery is live",
    "new owner-approved ADR",
    "can_write_truth",
    "writes_truth",
]:
    assert phrase in adr1, phrase

for adr_id in ["ADR-M6-002", "ADR-M6-003", "ADR-M6-004", "ADR-M6-005", "ADR-M6-006"]:
    body = text(adrs[adr_id])
    assert "status: accepted-addressed" in body, adr_id
    assert re.search(r"decision-makers:\s*\n\s*-\s*(Codex orchestrator|orchestrator)", body), adr_id
    assert "status_ceiling: ADDRESSED" in body, adr_id
    assert has_evidence(body, required_inputs["RES_M6"][1]), adr_id
    assert has_evidence(body, required_inputs["MODULE_M6"][1]), adr_id

for body_path in adrs.values():
    body = text(body_path)
    assert "CLOSED" not in body.split("## Consequences", 1)[-1], body_path
    assert has_evidence(body, required_inputs["RES_M6"][1]), body_path
    assert has_evidence(body, required_inputs["MODULE_M6"][1]), body_path

result = json.loads(result_path.read_text(encoding="utf-8"))
assert result["schema_id"] == "turingos.m6.p1.route_adr_draft.v1"
assert result["phase"] == "M6.P1"
assert result["status"] == "BLOCKED"
assert result["status_ceiling"] == "ADDRESSED"
assert result["m6_p1_tracker_status"] == "BLOCKED"
assert result["owner_acceptance_required"] is True
assert result["owner_acceptance_recorded"] is False
assert result["m6_p2_unblocked"] is False
assert result["route_selection_adr"] == str(adrs["ADR-M6-001"])
assert result["route_selection_status"] == "proposed"
assert result["route_selected_by_implementer"] is False
assert result["draft_adrs_complete"] is True

artifact_paths = [pathlib.Path(item["path"]) for item in result["digest_bound_artifacts"]]
for expected in adrs.values():
    assert expected in artifact_paths, expected
for item in result["digest_bound_artifacts"]:
    path = pathlib.Path(item["path"])
    assert path.exists(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], path

for line in manifest_path.read_text(encoding="utf-8").splitlines():
    digest, path = line.split(maxsplit=1)
    assert hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() == digest, path

print("M6_P1_ROUTE_ADR_DRAFT_CHECK_PASS")
PY

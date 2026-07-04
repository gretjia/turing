#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "$ROOT" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
adr_dir = root / "adr"
m6_dir = root / "m6_hci"

result_path = m6_dir / "M6_P1_ROUTE_ACCEPTANCE_RESULT.json"
manifest_path = m6_dir / "M6_P1_ROUTE_ACCEPTANCE_ARTIFACTS.sha256"

adr1_path = adr_dir / "ADR-M6-001-adopt-hci-a-projection-route.md"
adr_paths = [
    adr1_path,
    adr_dir / "ADR-M6-002-archive-then-rebase-rescue.md",
    adr_dir / "ADR-M6-003-intent-preview-verb-surface.md",
    adr_dir / "ADR-M6-004-projection-integrity-audit.md",
    adr_dir / "ADR-M6-005-layered-no-write-enforcement.md",
    adr_dir / "ADR-M6-006-cli-json-presentation.md",
]

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

def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")

for label, (path, digest) in required_inputs.items():
    assert path.exists(), f"missing {label}: {path}"
    assert sha256(path) == digest, label

for path in [result_path, manifest_path, *adr_paths]:
    assert path.exists(), f"missing {path}"

adr1 = text(adr1_path)
assert "status: accepted-addressed" in adr1
assert re.search(r"decision-makers:\s*\n\s*-\s*owner", adr1), "ADR-M6-001 must be owner-decided"
assert "owner ratification pending" not in adr1
assert "not accepted here" not in adr1
assert "M6.P2 remains blocked" not in adr1
assert "does not change constitution bytes" in adr1
assert "does not provide a genesis/OG-10 signature" in adr1
assert "does not enable M2" in adr1
assert "does not authorize HCI-B" in adr1
assert "does not authorize any write-capable console behavior" in adr1
for phrase in [
    "HCI-A",
    "projection-only",
    "HCI-C is forbidden",
    "can_write_truth",
    "writes_truth",
    "M1 canonical-writer/authorization question",
    "M2 TC witness is independently audited",
    "M5 external ClosureCertificate machinery is live",
    "new owner-approved ADR",
]:
    assert phrase in adr1, phrase

for path in adr_paths[1:]:
    body = text(path)
    assert "status: accepted-addressed" in body, path
    assert "status_ceiling: ADDRESSED" in body, path

result = json.loads(result_path.read_text(encoding="utf-8"))
assert result["schema_id"] == "turingos.m6.p1.route_acceptance.v1"
assert result["phase"] == "M6.P1"
assert result["status"] == "ADDRESSED"
assert result["status_ceiling"] == "ADDRESSED"
assert result["m6_p1_tracker_status"] == "ADDRESSED"
assert result["route_selection_adr"] == str(adr1_path)
assert result["route_selection_status"] == "accepted-addressed"
assert result["route_selected_by_implementer"] is False
assert result["owner_acceptance_required"] is True
assert result["owner_acceptance_recorded"] is True
assert result["m6_p2_unblocked"] is True
assert result["accepted_route"] == "HCI-A projection-only"
assert result["hci_b_authorized"] is False
assert result["write_capable_console_authorized"] is False
assert result["constitution_bytes_changed"] is False
assert result["m2_enabled"] is False

artifact_paths = [pathlib.Path(item["path"]) for item in result["digest_bound_artifacts"]]
for expected in adr_paths:
    assert expected in artifact_paths, expected
for item in result["digest_bound_artifacts"]:
    path = pathlib.Path(item["path"])
    assert path.exists(), path
    assert sha256(path) == item["sha256"], path

for line in manifest_path.read_text(encoding="utf-8").splitlines():
    digest, path = line.split(maxsplit=1)
    path = pathlib.Path(path)
    assert path.exists(), path
    assert sha256(path) == digest, path

print("M6_P1_ROUTE_ACCEPTANCE_CHECK_PASS")
PY

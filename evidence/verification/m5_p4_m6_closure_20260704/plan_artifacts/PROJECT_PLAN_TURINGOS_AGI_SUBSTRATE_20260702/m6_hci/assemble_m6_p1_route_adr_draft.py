#!/usr/bin/env python3
"""Assemble the M6.P1 route ADR draft/blocker record."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class M6P1Error(Exception):
    pass


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_item(label: str, path: Path) -> dict[str, str]:
    return {"label": label, "path": str(path), "sha256": file_sha256(path)}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_manifest(path: Path, entries: list[Path]) -> None:
    seen: set[Path] = set()
    lines: list[str] = []
    for entry in entries:
        if entry in seen:
            continue
        seen.add(entry)
        lines.append(f"{file_sha256(entry)}  {entry}\n")
    path.write_text("".join(lines), encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise M6P1Error(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--recorded-at-utc")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    adr_dir = root / "adr"
    m6_dir = root / "m6_hci"
    result_path = m6_dir / "M6_P1_ROUTE_ADR_DRAFT_RESULT.json"
    manifest_path = m6_dir / "M6_P1_ROUTE_ADR_DRAFT_ARTIFACTS.sha256"
    recorded_at = args.recorded_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    adrs = [
        adr_dir / "ADR-M6-001-adopt-hci-a-projection-route.md",
        adr_dir / "ADR-M6-002-archive-then-rebase-rescue.md",
        adr_dir / "ADR-M6-003-intent-preview-verb-surface.md",
        adr_dir / "ADR-M6-004-projection-integrity-audit.md",
        adr_dir / "ADR-M6-005-layered-no-write-enforcement.md",
        adr_dir / "ADR-M6-006-cli-json-presentation.md",
    ]
    inputs = [
        root / "research/RES_M6_hci_projection_console.md",
        root / "modules/MODULE_M6_hci_console.md",
        root / "01_PROJECT_INTENT.md",
        root.parent / "TURINGOS_RETROSPECTIVE_AUDIT_FINDINGS_20260702.md",
        root / "rescue/operator_console_v1/M6_P0a_VERDICT.json",
        root / "rescue/operator_console_v1/MANIFEST.sha256",
        root.parent / "turing/evidence/hci/operator_console_v1_rescue_20260702/M6_P0b_VERDICT.json",
    ]
    support = [
        root / "m6_hci/tests/test_m6_p1_route_adr_draft.sh",
        root / "m6_hci/assemble_m6_p1_route_adr_draft.py",
    ]

    for path in [*adrs, *inputs, *support]:
        require(path.exists(), f"missing required artifact: {path}")

    adr1 = adrs[0].read_text(encoding="utf-8")
    require("status: proposed" in adr1, "ADR-M6-001 must remain proposed until owner acceptance")
    require("owner ratification pending" in adr1, "ADR-M6-001 must record pending owner gate")
    require("HCI-C is forbidden" in adr1, "ADR-M6-001 must forbid HCI-C")

    result = {
        "schema_id": "turingos.m6.p1.route_adr_draft.v1",
        "phase": "M6.P1",
        "status": "BLOCKED",
        "status_ceiling": "ADDRESSED",
        "m6_p1_tracker_status": "BLOCKED",
        "recorded_at_utc": recorded_at,
        "draft_adrs_complete": True,
        "route_selection_adr": str(adrs[0]),
        "route_selection_status": "proposed",
        "route_selected_by_implementer": False,
        "owner_acceptance_required": True,
        "owner_acceptance_recorded": False,
        "m6_p2_unblocked": False,
        "blocked_on": "OWNER_ROUTE_SELECTION_FOR_ADR_M6_001",
        "accepted_implementer_adrs": [str(path) for path in adrs[1:]],
        "digest_bound_artifacts": [
            *[sha_item(f"adr_m6_{index:03d}", path) for index, path in enumerate(adrs, start=1)],
            *[sha_item(path.name, path) for path in inputs],
            *[sha_item(path.name, path) for path in support],
        ],
        "next_owner_action": (
            "If the owner accepts the HCI-A projection route, edit ADR-M6-001 in-file to "
            "status: accepted-addressed and decision-makers: owner, then rerun M6.P1 validation."
        ),
        "non_claims": [
            "M6.P1 is not ADDRESSED because ADR-M6-001 is owner-pending.",
            "M6.P2 is not unblocked.",
            "No HCI route acceptance, rescue branch, module gate, external verification, release, M2 enablement, OG-10/genesis signature, or constitution byte change is claimed.",
        ],
    }
    write_json(result_path, result)
    write_manifest(manifest_path, [result_path, *adrs, *inputs, *support])
    print(json.dumps({"verdict": "PASS", "result": str(result_path), "manifest": str(manifest_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

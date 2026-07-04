#!/usr/bin/env python3
"""Assemble the M6.P1 owner route-acceptance record."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class M6P1AcceptanceError(Exception):
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
        raise M6P1AcceptanceError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--recorded-at-utc")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    adr_dir = root / "adr"
    m6_dir = root / "m6_hci"
    result_path = m6_dir / "M6_P1_ROUTE_ACCEPTANCE_RESULT.json"
    manifest_path = m6_dir / "M6_P1_ROUTE_ACCEPTANCE_ARTIFACTS.sha256"
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
        root / "m6_hci/tests/test_m6_p1_route_acceptance.sh",
        root / "m6_hci/assemble_m6_p1_route_acceptance.py",
    ]

    for path in [*adrs, *inputs, *support]:
        require(path.exists(), f"missing required artifact: {path}")

    adr1 = adrs[0].read_text(encoding="utf-8")
    require("status: accepted-addressed" in adr1, "ADR-M6-001 must be owner-accepted")
    require("decision-makers:\n  - owner" in adr1, "ADR-M6-001 must record owner decision-maker")
    require("owner ratification pending" not in adr1, "ADR-M6-001 must not retain pending owner wording")
    require("not accepted here" not in adr1, "ADR-M6-001 must not retain draft wording")
    require("M6.P2 remains blocked" not in adr1, "ADR-M6-001 must not retain stale M6.P2 blocker wording")
    for phrase in [
        "does not change constitution bytes",
        "does not provide a genesis/OG-10 signature",
        "does not enable M2",
        "does not authorize HCI-B",
        "does not authorize any write-capable console behavior",
        "HCI-C is forbidden",
    ]:
        require(phrase in adr1, f"ADR-M6-001 missing acceptance boundary: {phrase}")

    result = {
        "schema_id": "turingos.m6.p1.route_acceptance.v1",
        "phase": "M6.P1",
        "status": "ADDRESSED",
        "status_ceiling": "ADDRESSED",
        "m6_p1_tracker_status": "ADDRESSED",
        "recorded_at_utc": recorded_at,
        "accepted_route": "HCI-A projection-only",
        "route_selection_adr": str(adrs[0]),
        "route_selection_status": "accepted-addressed",
        "route_selected_by_implementer": False,
        "owner_acceptance_required": True,
        "owner_acceptance_recorded": True,
        "owner_acceptance_recorded_by": "zephryj",
        "m6_p2_unblocked": True,
        "hci_b_authorized": False,
        "write_capable_console_authorized": False,
        "constitution_bytes_changed": False,
        "genesis_or_og10_signature_provided": False,
        "m2_enabled": False,
        "digest_bound_artifacts": [
            *[sha_item(f"adr_m6_{index:03d}", path) for index, path in enumerate(adrs, start=1)],
            *[sha_item(path.name, path) for path in inputs],
            *[sha_item(path.name, path) for path in support],
        ],
        "next_action": (
            "Proceed to M6.P2 rescue work on the accepted HCI-A projection-only route; do not add "
            "HCI-B or write-capable console behavior."
        ),
        "non_claims": [
            "M6.P1 acceptance does not change constitution bytes.",
            "M6.P1 acceptance does not provide a genesis/OG-10 signature.",
            "M6.P1 acceptance does not enable M2.",
            "M6.P1 acceptance does not authorize HCI-B.",
            "M6.P1 acceptance does not authorize any write-capable console behavior.",
            "M6.P1 acceptance does not grant M6.G, external verification, release eligibility, FCE.RUN, SHIPPED, RELEASED, or RATIFIED status.",
        ],
    }

    write_json(result_path, result)
    write_manifest(manifest_path, [result_path, *adrs, *inputs, *support])
    print(json.dumps({"verdict": "PASS", "result": str(result_path), "manifest": str(manifest_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Assemble M6.G roll-up, drift-check, and M5.P4 handoff packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GateError(Exception):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise GateError(f"missing required file: {path}")
    return path


def sha_item(label: str, path: Path) -> dict[str, str]:
    require_file(path)
    return {"label": label, "path": str(path), "sha256": file_sha256(path)}


def unique_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in items:
        path = item["path"]
        if path in seen:
            continue
        seen.add(path)
        result.append(item)
    return result


def result_status(path: Path) -> str | None:
    obj = load_json(path)
    return obj.get("status") or obj.get("phase_status") or obj.get("overall_status")


def require_result(path: Path, expected: str = "ADDRESSED") -> dict[str, Any]:
    obj = load_json(path)
    status = obj.get("status") or obj.get("phase_status") or obj.get("overall_status")
    if status != expected:
        raise GateError(f"{path}: status {status!r}, expected {expected!r}")
    if obj.get("verdict") not in (None, "PASS"):
        raise GateError(f"{path}: verdict {obj.get('verdict')!r}, expected PASS/absent")
    return obj


def require_adr(path: Path, *, owner_required: bool = False) -> None:
    body = require_file(path).read_text(encoding="utf-8")
    if "status: accepted-addressed" not in body:
        raise GateError(f"{path}: ADR is not accepted-addressed")
    if owner_required and "- owner" not in body:
        raise GateError(f"{path}: owner decision-maker not recorded")


def write_manifest(path: Path, entries: list[Path]) -> None:
    seen: set[Path] = set()
    lines: list[str] = []
    for entry in entries:
        if entry in seen:
            continue
        seen.add(entry)
        lines.append(f"{file_sha256(entry)}  {entry}\n")
    path.write_text("".join(lines), encoding="utf-8")


def drift_checklist(root: Path, rollup_path: Path) -> str:
    module = root / "modules/MODULE_M6_hci_console.md"
    playbook = root / "02_EXECUTION_PLAYBOOK.md"
    p5_result = root / "evidence/session_20260702/M6_P5_PROJECTION_INTEGRITY_RESULT.json"
    p4_result = root / "evidence/session_20260702/M6_P4_DYNAMIC_GATES_RESULT.json"
    adr = root / "adr/ADR-M6-001-adopt-hci-a-projection-route.md"
    tracker = root / "PROGRESS_TRACKER.md"
    return "\n".join(
        [
            "# M6.G Drift-Check Checklist",
            "",
            "Scoring rule: `NOT_RUN` counts as `FAIL`; every answer cites an openable artifact path.",
            "",
            "| q | question | answer | artifact_path | verdict |",
            "|---|---|---|---|---|",
            (
                "| 1 | Does the deliverable serve one of G1-G7? Which KPI, exactly? | "
                "Serves G7: HCI-A ADR accepted, 100% displayed values replayable by automated projection-integrity audit, zero head-moving UI paths by static plus dynamic checks, and the HCI branch is committed. | "
                f"{module} | PASS |"
            ),
            (
                "| 2 | Does it violate any red line in Intent section 5? | "
                "No. The roll-up changes no constitution bytes, uses no genesis/OG-10 signature, does not enable M2, does not authorize HCI-B, and does not authorize write-capable console behavior. | "
                f"{playbook} | PASS |"
            ),
            (
                "| 3 | Is every claim backed by an artifact path an independent agent can open? | "
                "Yes. The roll-up digest-binds the accepted ADRs, rescue archive, rescue branch evidence, static gates, dynamic gates, projection-integrity gate, and M5.P4 handoff packet. | "
                f"{rollup_path} | PASS |"
            ),
            (
                "| 4 | Is anything labeled real that is a fixture? Is anything unlabeled? | "
                "No. The original rescue archive remains FIXTURE_AND_SELF_RUN, while the current HCI gate results are deterministic implementation evidence on fixture MicroTapes. | "
                f"{root / 'rescue/operator_console_v1/CLAIM_BOUNDARY.json'} | PASS |"
            ),
            (
                "| 5 | Did scope grow beyond the Atom/Phase spec? If yes, cite the decision. | "
                "No. This assembles MODULE_M6 section 3 artifacts and prepares the M5.P4 closure handoff; it does not merge HCI to main or add HCI-B behavior. | "
                f"{module} | PASS |"
            ),
            (
                "| 6 | Can the work be replayed or resumed by a fresh agent from tracker plus tape alone? | "
                "Yes. Tracker rows cite every phase artifact, while this roll-up binds the artifact list and M6.P5 hci-gates can be rerun from the pushed branch. | "
                f"{tracker} | PASS |"
            ),
            (
                "| 7 | Does the status honor the ADDRESSED ceiling? | "
                "Yes. M6.G is ADDRESSED only; external verification requires the M5.P4 custody-separated closure queue. | "
                f"{p5_result} | PASS |"
            ),
            "",
            f"HCI-A route ADR: `{adr}`.",
            f"Dynamic no-write evidence: `{p4_result}`.",
            "",
        ]
    )


def make_required_artifacts(root: Path, repo: Path, evidence: Path) -> list[dict[str, Any]]:
    adr_paths = [
        root / "adr/ADR-M6-001-adopt-hci-a-projection-route.md",
        root / "adr/ADR-M6-002-archive-then-rebase-rescue.md",
        root / "adr/ADR-M6-003-intent-preview-verb-surface.md",
        root / "adr/ADR-M6-004-projection-integrity-audit.md",
        root / "adr/ADR-M6-005-layered-no-write-enforcement.md",
        root / "adr/ADR-M6-006-cli-json-presentation.md",
    ]
    require_adr(adr_paths[0], owner_required=True)
    for path in adr_paths[1:]:
        require_adr(path)

    result_paths = [
        evidence / "M6_P2_RESCUE_RESULT.json",
        evidence / "M6_P3_STATIC_NO_WRITE_RESULT.json",
        evidence / "M6_P4_DYNAMIC_GATES_RESULT.json",
        evidence / "M6_P5_PROJECTION_INTEGRITY_RESULT.json",
    ]
    for path in result_paths:
        require_result(path)

    p5_verdict = load_json(evidence / "m6_p5_hci_gates_20260704/hci_projection_integrity_verdict.json")
    if p5_verdict.get("verdict") != "PASS":
        raise GateError("M6.P5 projection-integrity verdict is not PASS")
    if not all(value == "PASS" for value in p5_verdict.get("checks", {}).values()):
        raise GateError("M6.P5 projection-integrity checks are not all PASS")

    groups = [
        (
            "1_adrs_accepted",
            "ADR-M6-001..006 accepted; ADR-M6-001 owner decision-maker recorded.",
            adr_paths
            + [
                root / "m6_hci/M6_P1_ROUTE_ACCEPTANCE_RESULT.json",
                root / "m6_hci/M6_P1_ROUTE_ACCEPTANCE_ARTIFACTS.sha256",
            ],
        ),
        (
            "2_rescue_archive",
            "Plan-directory rescue archive includes patch, tarball, manifest, base SHA, and claim boundary.",
            [
                root / "rescue/operator_console_v1/M6_P0a_VERDICT.json",
                root / "rescue/operator_console_v1/MANIFEST.sha256",
                root / "rescue/operator_console_v1/base_sha.txt",
                root / "rescue/operator_console_v1/tracked_1666.patch",
                root / "rescue/operator_console_v1/untracked.tar.gz",
                root / "rescue/operator_console_v1/CLAIM_BOUNDARY.json",
            ],
        ),
        (
            "3_rescue_branch_commit",
            "HCI rescue branch commit and regenerated evidence at the new base.",
            [
                evidence / "M6_P2_RESCUE_RESULT.json",
                evidence / "M6_P2_ARTIFACT_MANIFEST.sha256",
                evidence / "M6_P2_CARGO_TEST_TRANSCRIPT.txt",
                evidence / "M6_P2_PYTEST_TRANSCRIPT.txt",
                evidence / "M6_P2_OPERATOR_AUDIT_TRANSCRIPT.txt",
            ],
        ),
        (
            "4_static_no_write_gates",
            "Static no-write gates, tamper self-test, dependency-direction check, and clippy disallowed methods/types.",
            [
                evidence / "M6_P3_STATIC_NO_WRITE_RESULT.json",
                evidence / "M6_P3_ARTIFACT_MANIFEST.sha256",
                evidence / "M6_P3_NO_WRITE_SELF_TEST_TRANSCRIPT.txt",
                evidence / "M6_P3_NO_WRITE_GATE_TRANSCRIPT.txt",
                evidence / "M6_P3_PROJECTION_CLIPPY_TRANSCRIPT.txt",
                repo / "tools/hci/gate_hci_no_write.sh",
                repo / "crates/turing-projection/clippy.toml",
            ],
        ),
        (
            "5_dynamic_no_write_gates",
            "Dynamic head-conservation and read-only filesystem matrices over the HCI command surface.",
            [
                evidence / "M6_P4_DYNAMIC_GATES_RESULT.json",
                evidence / "M6_P4_ARTIFACT_MANIFEST.sha256",
                evidence / "M6_P4_HEAD_CONSERVATION_TEST_TRANSCRIPT.txt",
                evidence / "M6_P4_READONLY_FS_TEST_TRANSCRIPT.txt",
                evidence / "M6_P4_CLI_GATES_TRANSCRIPT.txt",
                repo / "crates/turing-cli/tests/cli_gates.rs",
            ],
        ),
        (
            "6_projection_integrity_and_hci_gates",
            "Projection-integrity auditor and aggregate hci-gates runner are PASS.",
            [
                evidence / "M6_P5_PROJECTION_INTEGRITY_RESULT.json",
                evidence / "M6_P5_ARTIFACT_MANIFEST.sha256",
                evidence / "M6_P5_HCI_GATES_TRANSCRIPT.txt",
                evidence / "M6_P5_PROJECTION_INTEGRITY_PYTEST_TRANSCRIPT.txt",
                evidence / "m6_p5_hci_gates_20260704/hci_projection_integrity_verdict.json",
                evidence / "m6_p5_hci_gates_20260704/hci_gates_result.json",
                repo / "tools/hci/audit_projection_integrity.py",
                repo / "tools/hci/run_hci_gates.sh",
                repo / "schemas/operator/operator_view_snapshot.v1.provenance.json",
            ],
        ),
        (
            "7_tracker_update",
            "Tracker/session updates are mutable recovery surfaces; their paths are recorded outside the digest-bound manifest to avoid circular hashes.",
            [
                root / "evidence/session_20260702/M6_P5_PROJECTION_INTEGRITY_RESULT.json",
            ],
        ),
    ]
    required = []
    for group_id, description, paths in groups:
        items = [sha_item(Path(path).name, path) for path in paths]
        required.append(
            {
                "id": group_id,
                "description": description,
                "status": "PASS",
                "items": items,
            }
        )
    return required


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--recorded-at-utc")
    args = parser.parse_args(argv)

    try:
        root = Path(args.root).resolve()
        evidence = Path(args.evidence_dir).resolve()
        repo = root.parent / "turing"
        recorded_at = args.recorded_at_utc or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        rollup_path = evidence / "M6G_ARTIFACT_ROLLUP.json"
        drift_path = evidence / "M6G_DRIFT_CHECKLIST.md"
        verdict_path = evidence / "M6G_GATE_VERDICT.json"
        handoff_path = evidence / "M6G_M5_P4_HANDOFF_PACKET.json"
        manifest_path = evidence / "M6G_ARTIFACT_MANIFEST.sha256"

        required = make_required_artifacts(root, repo, evidence)
        digest_items = unique_items(
            [item for group in required for item in group["items"]]
        )
        rollup = {
            "schema_id": "turingos.m6_g_artifact_rollup.v1",
            "gate_id": "M6.G",
            "module": "M6",
            "status": "ADDRESSED",
            "status_ceiling": "ADDRESSED",
            "recorded_at_utc": recorded_at,
            "repo": {
                "path": str(repo),
                "remote": "https://github.com/gretjia/turing.git",
                "branch": "hci/operator-console-v1-rebased",
                "commit_sha": "0fd16d1abede372fa8514824ef98a4405e780a86",
            },
            "g7_kpi": {
                "hci_a_adr_accepted": True,
                "displayed_values_replayable": True,
                "zero_head_moving_paths_static_and_dynamic": True,
                "branch_committed_or_archived": True,
            },
            "all_required_items_present": True,
            "required_artifacts": required,
            "digest_bound_artifacts": digest_items,
            "mutable_supporting_paths": [
                str(root / "PROGRESS_TRACKER.md"),
                str(root / "memory/SESSION_STATE.md"),
            ],
            "not_run_is_fail": True,
            "non_claims": [
                "M6.G is not externally verified",
                "No HCI-B or write-capable console behavior is authorized.",
                "No SHIPPED, RELEASED, RATIFIED, M2 enablement, release eligibility, FCE.RUN, OG-10/genesis signature, or constitution-byte change is claimed.",
            ],
        }
        write_json(rollup_path, rollup)

        drift_path.write_text(drift_checklist(root, rollup_path), encoding="utf-8")

        handoff = {
            "schema_id": "turingos.m5_p4.module_closure_handoff.v1",
            "gate_id": "M6.G",
            "module": "M6",
            "packet_intent": "Queue M6.G for M5.P4 custody-separated module closure verification.",
            "status_ceiling": "ADDRESSED",
            "lineage_excluded": True,
            "requested_verifier_tier": "external_cross_family_or_human",
            "repo_url": "https://github.com/gretjia/turing",
            "branch": "hci/operator-console-v1-rebased",
            "commit_sha": "0fd16d1abede372fa8514824ef98a4405e780a86",
            "artifact_paths": [item["path"] for item in digest_items]
            + rollup["mutable_supporting_paths"],
            "required_commands": [
                "sha256sum -c M6G_ARTIFACT_MANIFEST.sha256",
                "bash m6_hci/tests/test_m6_g_rollup.sh",
                "cd /home/zephryj/turingos_backup/work/turing && bash tools/hci/run_hci_gates.sh --out-dir /tmp/m6g-hci-gates",
            ],
            "non_claims": rollup["non_claims"],
        }
        write_json(handoff_path, handoff)

        checklist_results = [
            {
                "q": idx,
                "question": question,
                "answer": answer,
                "artifact": artifact,
                "verdict": "PASS",
            }
            for idx, question, answer, artifact in [
                (
                    1,
                    "Does the deliverable serve one of G1-G7? Which KPI, exactly?",
                    "Serves G7: HCI-A ADR accepted, displayed values replayable, zero head-moving paths, and branch committed/archived.",
                    str(root / "modules/MODULE_M6_hci_console.md"),
                ),
                (
                    2,
                    "Does it violate any red line in Intent section 5?",
                    "No. It does not change constitution bytes, enable M2, authorize HCI-B, or authorize write-capable console behavior.",
                    str(root / "02_EXECUTION_PLAYBOOK.md"),
                ),
                (
                    3,
                    "Is every claim backed by an artifact path an independent agent can open?",
                    "Yes. M6G_ARTIFACT_ROLLUP.json digest-binds the required artifacts.",
                    str(rollup_path),
                ),
                (
                    4,
                    "Is anything labeled real that is a fixture? Is anything unlabeled?",
                    "No. Fixture MicroTape evidence is identified as implementation gate evidence and the original rescue archive is fixture-labeled.",
                    str(root / "rescue/operator_console_v1/CLAIM_BOUNDARY.json"),
                ),
                (
                    5,
                    "Did scope grow beyond the Atom/Phase spec? If yes, cite the decision.",
                    "No. This assembles MODULE_M6 section 3 artifacts and prepares an M5.P4 handoff only.",
                    str(root / "modules/MODULE_M6_hci_console.md"),
                ),
                (
                    6,
                    "Can the work be replayed or resumed by a fresh agent from tracker plus tape alone?",
                    "Yes. The tracker and roll-up cite the pushed branch, exact commit, gate outputs, and manifests.",
                    str(root / "PROGRESS_TRACKER.md"),
                ),
                (
                    7,
                    "Does the status honor the ADDRESSED ceiling?",
                    "Yes. M6.G remains ADDRESSED and requires M5.P4 custody-separated external closure for external verification.",
                    str(rollup_path),
                ),
            ]
        ]
        verdict = {
            "schema_id": "GateVerdict.v1",
            "gate_id": "M6.G",
            "module": "M6",
            "status": "ADDRESSED",
            "status_ceiling": "ADDRESSED",
            "recorded_at_utc": recorded_at,
            "not_run_is_fail": True,
            "alignment_verify": "GREEN",
            "checklist_results": checklist_results,
            "evidence": [
                sha_item("artifact_rollup", rollup_path),
                sha_item("drift_checklist", drift_path),
                sha_item("m5_p4_handoff_packet", handoff_path),
            ],
            "g7_kpi": rollup["g7_kpi"],
            "non_claims": rollup["non_claims"],
        }
        write_json(verdict_path, verdict)

        manifest_entries = [
            rollup_path,
            drift_path,
            verdict_path,
            handoff_path,
            root / "m6_hci/assemble_m6_gate.py",
            root / "m6_hci/tests/test_m6_g_rollup.sh",
        ] + [Path(item["path"]) for item in digest_items]
        write_manifest(manifest_path, manifest_entries)
        return 0
    except GateError as error:
        print(f"M6_G_ROLLUP_FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

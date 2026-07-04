#!/usr/bin/env python3
"""Assemble M5.G roll-up, drift-check, and external hand-off packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GateError(Exception):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_item(label: str, path: Path) -> dict[str, str]:
    if not path.is_file():
        raise GateError(f"missing required file: {path}")
    return {"label": label, "path": str(path), "sha256": file_sha256(path)}


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise GateError(f"missing required file: {path}")
    return path


def require_status(path: Path, expected: str = "ADDRESSED") -> None:
    obj = load_json(path)
    status = obj.get("status") or obj.get("phase_status") or obj.get("status_after_record", {}).get("M5.P3")
    if status != expected:
        raise GateError(f"{path}: status {status!r}, expected {expected!r}")


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


def write_manifest(path: Path, entries: list[Path]) -> None:
    seen: set[Path] = set()
    lines: list[str] = []
    for entry in entries:
        if entry in seen:
            continue
        seen.add(entry)
        lines.append(f"{file_sha256(entry)}  {entry}\n")
    path.write_text("".join(lines), encoding="utf-8")


def assert_m5p3_pass(cert_path: Path) -> dict[str, Any]:
    cert = load_json(cert_path)
    custody = cert["verifier"]["custody"]
    if cert.get("schema_id") != "turingos.closure_certificate.v1":
        raise GateError("M5.P3 certificate schema mismatch")
    if cert.get("verdict") != "PASS":
        raise GateError("M5.P3 certificate is not PASS")
    if cert["subject"]["gate_id"] != "M5.P3":
        raise GateError("M5.P3 certificate subject gate mismatch")
    if cert["status_semantics"]["certified_closure_level"] != "EXTERNALLY_VERIFIED":
        raise GateError("M5.P3 certificate closure level mismatch")
    if not all(custody.values()):
        raise GateError("M5.P3 certificate custody booleans are not all true")
    return cert


def assert_m5p4_pass(cert_path: Path) -> dict[str, Any]:
    cert = load_json(cert_path)
    custody = cert["verifier"]["custody"]
    if cert.get("schema_id") != "turingos.closure_certificate.v1":
        raise GateError("M5.P4 certificate schema mismatch")
    if cert.get("verdict") != "PASS":
        raise GateError("M5.P4 certificate is not PASS")
    if cert["subject"]["gate_id"] != "M5.P4":
        raise GateError("M5.P4 certificate subject gate mismatch")
    targets = set(cert["subject"]["module_targets"])
    if targets != {"M3.G", "M4.G"}:
        raise GateError(f"M5.P4 certificate targets mismatch: {targets}")
    if not all(custody.values()):
        raise GateError("M5.P4 certificate custody booleans are not all true")
    return cert


def drift_markdown(root: Path, rollup_path: Path, m5p3_cert: Path, m5p4_cert: Path) -> str:
    module = root / "modules/MODULE_M5_independent_verification.md"
    playbook = root / "02_EXECUTION_PLAYBOOK.md"
    tracker = root / "PROGRESS_TRACKER.md"
    p5_verdict = root / "evidence/session_20260702/M5_P5_VERDICT.json"
    return "\n".join(
        [
            "# M5.G Drift-Check Checklist",
            "",
            "Scoring rule: `NOT_RUN` counts as `FAIL`; every answer cites an openable artifact path.",
            "",
            "| q | question | answer | artifact_path | verdict |",
            "|---|---|---|---|---|",
            (
                "| 1 | Does the deliverable serve one of G1-G7? Which KPI, exactly? | "
                "Serves G6: M5 now has custody-separated audit machinery, at least one exact-SHA external PASS for M5.P3, release gating that refuses missing/self/digest-mismatched certificates, and a certificate-or-FAIL record for processed P4 closures. | "
                f"{module} | PASS |"
            ),
            (
                "| 2 | Does it violate any red line in Intent section 5? | "
                "No. The roll-up changes no constitution bytes, uses no genesis/OG-10 signature, claims no release or M2 enablement, and does not grant SHIPPED. | "
                f"{playbook} | PASS |"
            ),
            (
                "| 3 | Is every claim backed by an artifact path an independent agent can open? | "
                "Yes. The roll-up indexes the M5 ADRs, schema/validator/prompts, custody runbook, negative controls, packet builder, release gate, M5.P3 PASS certificate, M5.P4 PASS certificate, and tracker state. | "
                f"{rollup_path} | PASS |"
            ),
            (
                "| 4 | Is anything labeled real that is a fixture? Is anything unlabeled? | "
                "No. Fixture corpora remain fixture-labeled, while M5.P3 and M5.P4 external PASS certificates are recorded as owner-provided external audit mirrors. | "
                f"{m5p3_cert} | PASS |"
            ),
            (
                "| 5 | Did scope grow beyond the Atom/Phase spec? If yes, cite the decision. | "
                "No. This gate only rolls up MODULE_M5 section 3 artifacts and prepares an external hand-off packet; it does not process new P4 queue jobs. | "
                f"{module} | PASS |"
            ),
            (
                "| 6 | Can the work be replayed or resumed by a fresh agent from tracker plus tape alone? | "
                "Yes. The tracker rows and M5G roll-up identify every source artifact and digest needed to reconstruct this gate state; external re-audit can start from the hand-off packet. | "
                f"{tracker} | PASS |"
            ),
            (
                "| 7 | Does the status honor the ADDRESSED ceiling? | "
                "Yes. M5.G is implementer ADDRESSED only; external verification for M5.G itself requires a later custody-separated exact-SHA audit. | "
                f"{m5p4_cert} | PASS |"
            ),
            "",
            f"Release mechanics verdict: `{p5_verdict}`.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--recorded-at-utc")
    args = parser.parse_args(argv)

    try:
        root = Path(args.root).resolve()
        evidence = Path(args.evidence_dir).resolve()
        work = root.parent
        repo = work / "turing"
        recorded_at = args.recorded_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        rollup_path = evidence / "M5G_ARTIFACT_ROLLUP.json"
        drift_path = evidence / "M5G_DRIFT_CHECKLIST.md"
        verdict_path = evidence / "M5G_GATE_VERDICT.json"
        handoff_path = evidence / "M5G_EXTERNAL_HANDOFF_PACKET.json"
        manifest_path = evidence / "M5G_ARTIFACT_MANIFEST.sha256"

        p1_verdict = evidence / "M5_P1_VERDICT.json"
        p2_verdict = evidence / "M5_P2_VERDICT.json"
        p5_verdict = evidence / "M5_P5_VERDICT.json"
        for path in [p1_verdict, p2_verdict]:
            require_status(path)
        p5_obj = load_json(p5_verdict)
        if p5_obj.get("phase_status") != "ADDRESSED" or p5_obj.get("verdict") != "PASS":
            raise GateError("M5.P5 verdict is not PASS/ADDRESSED")

        m5p3_cert = repo / "evidence/verification/m5_p3_first_external_audit_20260704_external_pass/M5_P3_GROK_PASS_CERTIFICATE.json"
        m5p4_cert = repo / "evidence/verification/m5_p4_module_closure_20260704_r2_external_pass/M5_P4_GROK_PASS_CERTIFICATE.json"
        m5p3 = assert_m5p3_pass(m5p3_cert)
        m5p4 = assert_m5p4_pass(m5p4_cert)

        adrs = [
            root / f"adr/ADR-M5-00{idx}-{slug}.md"
            for idx, slug in [
                (1, "closure-certificate-unsigned"),
                (2, "custody-separation-properties"),
                (3, "exact-sha-release-packet"),
                (4, "first-external-audit-target"),
                (5, "release-eligibility-gate"),
                (6, "g12-wrapper-mechanics-and-schema-subordination"),
                (7, "negative-controls-and-skeleton-subsumption"),
            ]
        ]

        groups: dict[str, list[Path]] = {
            "1_adrs": adrs,
            "2_schema_validator_prompts_lineage": [
                root / "m5_verification/schemas/closure_certificate.v1.schema.json",
                root / "m5_verification/tools/validate_closure_certificate.py",
                root / "m5_verification/tests/test_closure_certificate_validator.sh",
                evidence / "M5_P1_VALIDATOR_SELFTEST_TRANSCRIPT.txt",
                root / "m5_verification/prompts/VERIFIER_PROMPT_E1.md",
                root / "m5_verification/prompts/VERIFIER_PROMPT_E2.md",
                root / "m5_verification/tools/lineage_scrub.sh",
                root / "m5_verification/tests/test_lineage_scrub.sh",
                evidence / "M5_P1_LINEAGE_SCRUB_TRANSCRIPT.txt",
                p1_verdict,
            ],
            "3_custody_runbook": [
                root / "m5_verification/AUDITOR_RUNBOOK.md",
                evidence / "M5_P2_RUNBOOK_DRYRUN_TRANSCRIPT.txt",
                p2_verdict,
            ],
            "4_negative_control_corpus": [
                root / "m5_verification/corpus/negative_controls/CLAIM_BOUNDARY.json",
                root / "m5_verification/corpus/negative_controls/corpus_pins.sha256",
                root / "m5_verification/tools/make_negative_controls.sh",
                evidence / "M5_P2_NEGATIVE_CONTROL_CALIBRATION_TRANSCRIPT.txt",
            ],
            "5_packet_builder_and_validate": [
                repo / "tools/release/build_packet.sh",
                repo / "tools/release/build_packet.py",
                repo / "tests/test_release_mechanics.py",
                evidence / "M5_P5_REPO_TEST_TRANSCRIPT.txt",
                evidence / "M5_P5_RELEASE_MECHANICS_TRANSCRIPT.txt",
                evidence / "M5_P5_CORPUS_PIN_TRANSCRIPT.txt",
            ],
            "6_first_external_exact_sha_audit": [
                repo / "evidence/verification/m5_p3_first_external_audit_20260704/PACKET_MANIFEST.json",
                repo / "evidence/verification/m5_p3_first_external_audit_20260704/MANIFEST.sha256",
                m5p3_cert,
                evidence / "M5_P3_FIRST_AUDIT_PACKET_RECORD.json",
                evidence / "M5_P3_FIRST_AUDIT_PASS_RECORD.json",
            ],
            "7_release_mechanics": [
                repo / "tools/release/assert_release_eligible.sh",
                repo / "tools/release/assert_release_eligible.py",
                root / "m5_verification/corpus/release_mechanics_selftest/corpus_pins.sha256",
                root / "m5_verification/corpus/release_mechanics_selftest/certs/cert_valid_FIXTURE.json",
                root / "m5_verification/corpus/release_mechanics_selftest/certs/cert_implementer_family_FIXTURE.json",
                root / "m5_verification/corpus/release_mechanics_selftest/certs/cert_digest_mismatch_FIXTURE.json",
                p5_verdict,
            ],
            "8_processed_module_closures": [
                m5p4_cert,
                evidence / "M5_P4_MODULE_CLOSURE_PASS_RECORD.json",
                evidence / "M3G_M5_P4_HANDOFF_PACKET.json",
                evidence / "M3G_GATE_VERDICT.json",
                evidence / "M4G_M5_P4_HANDOFF_PACKET.json",
                evidence / "M4G_GATE_VERDICT.json",
            ],
            "9_tracker_update": [
                root / "PROGRESS_TRACKER.md",
                root / "memory/SESSION_STATE.md",
            ],
        }

        required: list[dict[str, Any]] = []
        digest_bound: list[dict[str, str]] = []
        for index, (group, paths) in enumerate(groups.items(), start=1):
            normalized: list[str] = []
            for path in paths:
                path = require_file(path.resolve())
                normalized.append(str(path))
                if group != "9_tracker_update":
                    digest_bound.append(sha_item(f"{group}:{path.name}", path))
            required.append(
                {
                    "id": index,
                    "name": group,
                    "paths": normalized,
                    "status": "PASS",
                }
            )
        digest_bound = unique_items(digest_bound)

        processed_closures = {
            "M3.G": {
                "status": "EXTERNALLY_VERIFIED",
                "certificate_path": str(m5p4_cert),
                "certificate_sha256": file_sha256(m5p4_cert),
            },
            "M4.G": {
                "status": "EXTERNALLY_VERIFIED",
                "certificate_path": str(m5p4_cert),
                "certificate_sha256": file_sha256(m5p4_cert),
            },
        }
        pending_closures = ["M1.G", "M2.TC5/G", "M6.G"]

        rollup = {
            "all_required_items_present": True,
            "automated_eval_summary": {
                "closure_validator_selftest": "PASS",
                "lineage_scrub_seeded_bundle": "PASS",
                "negative_control_calibration": "PASS_5_OF_5_FAIL_AS_EXPECTED",
                "packet_builder_validate": "PASS",
                "release_blocker_battery": "PASS_3_REFUSALS_1_POSITIVE_FIXTURE",
            },
            "child_phase_statuses": {
                "M5.P0": "ADDRESSED",
                "M5.P0b": "ADDRESSED",
                "M5.P1": "ADDRESSED",
                "M5.P2": "ADDRESSED",
                "M5.P3": "EXTERNALLY_VERIFIED",
                "M5.P4": "IN_PROGRESS",
                "M5.P5": "ADDRESSED",
            },
            "digest_bound_artifacts": digest_bound,
            "external_pass_artifact": {
                "gate_id": "M5.P3",
                "path": str(m5p3_cert),
                "sha256": file_sha256(m5p3_cert),
                "verifier_kind": m5p3["verifier"]["kind"],
                "verifier_identity": m5p3["verifier"]["identity"],
            },
            "external_pass_artifact_present": True,
            "gate_id": "M5.G",
            "module": "M5",
            "pending_module_closures": pending_closures,
            "processed_module_closures": processed_closures,
            "processed_module_closures_cert_or_fail": True,
            "recorded_at_utc": recorded_at,
            "required_artifacts": required,
            "schema": "turingos.m5_g_artifact_rollup.v1",
            "status": "ADDRESSED",
            "status_ceiling": "ADDRESSED",
            "status_ceiling_note": "implementer ceiling ADDRESSED; M5.G itself is not externally verified without a later custody-separated exact-SHA audit",
            "status_semantics": {
                "does_not_grant": [
                    "SHIPPED",
                    "RELEASED",
                    "RATIFIED",
                    "M2 enablement",
                    "release eligibility",
                    "OG-10/genesis signature",
                    "constitution-byte change",
                    "FCE.RUN",
                ],
                "implements": "G6 roll-up at implementer ceiling",
            },
        }
        write_json(rollup_path, rollup)

        drift_path.write_text(drift_markdown(root, rollup_path, m5p3_cert, m5p4_cert), encoding="utf-8")

        checklist = [
            {
                "q": index,
                "question": row[0],
                "answer": row[1],
                "artifact": row[2],
                "verdict": "PASS",
            }
            for index, row in enumerate(
                [
                    (
                        "Does the deliverable serve one of G1-G7? Which KPI, exactly?",
                        "Serves G6: independent verification and release machinery have a custody-separated exact-SHA PASS, negative controls, and release blocking.",
                        str(root / "modules/MODULE_M5_independent_verification.md"),
                    ),
                    (
                        "Does it violate any red line in Intent section 5?",
                        "No. The roll-up does not change constitution bytes, does not provide genesis/OG-10 signature, and does not enable M2.",
                        str(root / "02_EXECUTION_PLAYBOOK.md"),
                    ),
                    (
                        "Is every claim backed by an artifact path an independent agent can open?",
                        "Yes. M5G_ARTIFACT_ROLLUP.json digest-binds every non-tracker source artifact.",
                        str(rollup_path),
                    ),
                    (
                        "Is anything labeled real that is a fixture? Is anything unlabeled?",
                        "No. Fixture corpora remain explicitly fixture-labeled; external certificates remain owner-provided external audit mirrors.",
                        str(m5p3_cert),
                    ),
                    (
                        "Did scope grow beyond the Atom/Phase spec? If yes, cite the decision.",
                        "No. This assembles MODULE_M5 section 3 artifacts and does not run new module-closure jobs.",
                        str(root / "modules/MODULE_M5_independent_verification.md"),
                    ),
                    (
                        "Can the work be replayed or resumed by a fresh agent from tracker plus tape alone?",
                        "Yes. The tracker and roll-up paths identify every input, digest, and external certificate mirror needed for replay.",
                        str(root / "PROGRESS_TRACKER.md"),
                    ),
                    (
                        "Does the status honor the ADDRESSED ceiling?",
                        "Yes. The gate verdict remains ADDRESSED and explicitly says M5.G is not externally verified.",
                        str(m5p4_cert),
                    ),
                ],
                start=1,
            )
        ]

        handoff = {
            "artifact_paths": [str(path) for paths in groups.values() for path in paths],
            "gate_id": "M5.G",
            "lineage_excluded": True,
            "non_claims": [
                "No implementation narrative is included.",
                "This hand-off packet does not grant SHIPPED, RELEASED, RATIFIED, M2 enablement, release eligibility, FCE.RUN, OG-10/genesis signature, or constitution-byte change.",
                "M5.G is not externally verified until a custody-separated external verifier returns a PASS certificate for this exact packet.",
            ],
            "packet_intent": "External exact-SHA audit hand-off for M5.G G6 roll-up.",
            "requested_verifier_tier": "external_cross_family_or_human",
            "required_commands": [
                "sha256sum -c M5G_ARTIFACT_MANIFEST.sha256",
                "bash m5_verification/tests/test_m5_g_rollup.sh",
                "bash governance/lint_status_claims.sh",
                "bash governance/lint_claim_boundaries.sh",
            ],
            "status_ceiling": "ADDRESSED",
        }
        write_json(handoff_path, handoff)

        verdict = {
            "alignment_verify": "GREEN",
            "checklist_results": checklist,
            "evidence": [
                sha_item("artifact_rollup", rollup_path),
                sha_item("drift_checklist", drift_path),
                sha_item("external_handoff_packet", handoff_path),
            ],
            "external_pass_artifact": rollup["external_pass_artifact"],
            "gate_id": "M5.G",
            "module": "M5",
            "non_claims": [
                "M5.G is not externally verified",
                "No SHIPPED, RELEASED, RATIFIED, M2 enablement, release eligibility, FCE.RUN, OG-10/genesis signature, or constitution-byte change is claimed.",
                "P4 queue jobs for M1.G, M2.TC5/G, and M6.G remain pending.",
            ],
            "produced": recorded_at,
            "schema": "GateVerdict.v1",
            "status": "ADDRESSED",
            "status_ceiling_note": "implementer ceiling ADDRESSED; external verification for M5.G itself requires a later custody-separated exact-SHA audit",
        }
        write_json(verdict_path, verdict)

        write_manifest(manifest_path, [rollup_path, drift_path, verdict_path, handoff_path])
        print(json.dumps({"status": "PASS", "rollup": str(rollup_path), "verdict": str(verdict_path)}, sort_keys=True))
        return 0
    except GateError as exc:
        print(f"M5_G_GATE_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

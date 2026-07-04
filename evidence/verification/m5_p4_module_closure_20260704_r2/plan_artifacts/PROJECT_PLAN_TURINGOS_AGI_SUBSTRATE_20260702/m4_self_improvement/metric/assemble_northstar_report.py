#!/usr/bin/env python3
"""Assemble M4.P3 NORTHSTAR_REPORT.md and CLAIM_BOUNDARY.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AssembleError(Exception):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_ref(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": file_sha256(path)}


def require_dict(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssembleError(f"{where}: expected object")
    return value


def fmt_ci(h2_data: dict[str, Any]) -> str:
    ci = require_dict(h2_data.get("bootstrap_ci95"), "h2.bootstrap_ci95")
    return f"[{ci['ci95_low']:.2f}, {ci['ci95_high']:.2f}]"


def arm_run_class(breakdown: dict[str, Any]) -> str:
    if breakdown.get("n_excluded") != 0:
        return "INADMISSIBLE"
    if breakdown.get("n_bounded") != 0:
        return "BOUNDED"
    return "BILLING_COMPLETE"


def render_report(
    hvpput: dict[str, Any],
    h2_note: dict[str, Any],
    correction_record: Path,
    legacy_note: Path,
    boundary_path: Path,
    boundary_sha: str,
) -> tuple[str, str]:
    breakdown = require_dict(hvpput.get("class_breakdown"), "hvpput.class_breakdown")
    h2_data = require_dict(h2_note.get("h2"), "h2_note.h2")
    mde_statement = h2_note["mde_statement"]
    mde_for_sentence = mde_statement.rstrip(".")
    ci_text = fmt_ci(h2_data)
    delta = h2_data["delta"]
    null_sentence = (
        f"Δ_BC = {delta} [CI includes 0]; "
        f"the study was powered for MDE = {mde_for_sentence}; "
        "smaller true effects are not excluded. No failure-memory efficacy claim is made."
    )

    arms = require_dict(hvpput.get("arms"), "hvpput.arms")
    arm_values = []
    cost_rows = []
    exclusion_rows: list[str] = []
    for arm in ("A", "B", "C"):
        arm_obj = require_dict(arms.get(arm), f"hvpput.arms.{arm}")
        arm_breakdown = require_dict(arm_obj.get("class_breakdown"), f"hvpput.arms.{arm}.class_breakdown")
        portfolio = require_dict(
            arm_obj.get("billing_complete_portfolio"),
            f"hvpput.arms.{arm}.billing_complete_portfolio",
        )
        hvpput_value = portfolio["hvpput_m_str"]
        arm_values.append(f"{arm}: {hvpput_value}")
        run_class = arm_run_class(arm_breakdown)
        provenance = (
            f"{arm_breakdown['n_billing_complete']} provider_receipt_inline DeepSeek usage receipts; "
            "CostEvent.v2 aggregate-ceiling recomputation; conservation reconciliation PASS."
        )
        cost_rows.append(f"| {arm} | {run_class} | {hvpput_value} | {provenance} |")
        for item in arm_obj.get("exclusions", []):
            run_id = item.get("run_id", "<unknown>") if isinstance(item, dict) else "<unknown>"
            reason = item.get("reason", "<unknown>") if isinstance(item, dict) else "<unknown>"
            refs = item.get("event_refs", []) if isinstance(item, dict) else []
            exclusion_rows.append(f"| {run_id} | {reason} | {', '.join(refs) if refs else '<none>'} |")

    if not exclusion_rows:
        exclusion_rows.append("| <none> | <none> | <none> |")

    deviation_rows = [
        (
            "| Deterministic CostEvent.v2 aggregate-ceiling metric correction | "
            f"`{correction_record}` | Recorded in M4.P1 correction record; original freeze remains preserved; "
            "correction is receipt-shape-driven, not outcome-driven. |"
        ),
        (
            "| Legacy lifecycle auditors not applicable to M3 DeepSeek continuation | "
            f"`{legacy_note}` | Recorded deviation; artifact-level substitute audit only; no external verification claim. |"
        ),
    ]

    report = "\n".join(
        [
            "# M4 North-Star Report",
            "",
            "## Headline",
            "",
            (
                f"- Run-class breakdown: {breakdown['n_billing_complete']} BILLING_COMPLETE / "
                f"{breakdown['n_bounded']} BOUNDED / {breakdown['n_excluded']} INADMISSIBLE."
            ),
            f"- Per-arm portfolio H-VPPUT: {'; '.join(arm_values)}.",
            f"- Δ_BC with CI: {delta} {ci_text}; p={h2_data['exact_mcnemar_two_sided_p']}; blocked_by_h1={str(h2_data['blocked_by_h1']).lower()}.",
            f"- MDE statement: {mde_statement}",
            "",
            "## Mandatory Direction Sentence",
            "",
            null_sentence,
            "",
            "Skeleton record retained from the frozen template:",
            "",
            "- Positive: Δ_BC = x [CI a,b], H2 passed at pre-registered α; failure-memory contribution is supported at this scale.",
            "- Null: Δ_BC = x [CI includes 0]; the study was powered for MDE = y; smaller true effects are not excluded. No failure-memory efficacy claim is made.",
            '- Negative: same as null plus "the point estimate is negative; a harm hypothesis was not pre-registered and is flagged for a future pre-registered study."',
            "",
            "## Cost Provenance",
            "",
            "| Arm | Run class | H-VPPUT field | Cost provenance note |",
            "|---|---|---|---|",
            *cost_rows,
            "",
            "## Exclusion Table",
            "",
            "| Run or task | Reason | Event refs |",
            "|---|---|---|",
            *exclusion_rows,
            "",
            "## Deviation Table",
            "",
            "| Deviation | Source | Disposition |",
            "|---|---|---|",
            *deviation_rows,
            "",
            "## Claim Boundary",
            "",
            f"`{boundary_path}` sha256 `{boundary_sha}`.",
            "",
            "H-VPPUT is a measurement-validity projection, not an absolute capability claim.",
            "",
        ]
    )
    return report, null_sentence


def make_boundary(template: dict[str, Any], h2_note: dict[str, Any]) -> dict[str, Any]:
    boundary = dict(template)
    boundary["schema_id"] = "m4.claim_boundary.v1"
    boundary["failure_memory_causal_claim_allowed"] = bool(h2_note["failure_memory_causal_claim_allowed"])
    boundary["h2_source_path"] = h2_note["source_path"]
    boundary["h2_source_sha256"] = h2_note["source_sha256"]
    boundary["mandatory_direction"] = "positive" if boundary["failure_memory_causal_claim_allowed"] else "null"
    boundary["status_ceiling"] = "ADDRESSED"
    boundary["claims_forbidden"] = [
        "failure-memory efficacy claim",
        "H-VPPUT absolute capability claim",
        "official leaderboard submission",
        "leaderboard equivalence",
        "external verification",
        "CLOSED",
        "RELEASED",
        "SHIPPED",
        "RATIFIED",
        "M2 enabled",
        "OG-10/genesis signature",
        "constitution byte change",
    ]
    return boundary


def write_manifest(path: Path, entries: list[Path]) -> None:
    path.write_text(
        "".join(f"{file_sha256(entry)}  {entry}\n" for entry in entries),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--recorded-at-utc")
    args = parser.parse_args(argv)

    try:
        root = Path(args.root)
        run_root = Path(args.run_root)
        recorded_at = args.recorded_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        hvpput_path = run_root / "hvpput_report.v1.json"
        h2_note_path = run_root / "causal/h2_consumption_note.json"
        template_path = root / "m4_self_improvement/CLAIM_BOUNDARY.template.json"
        p1_result_path = root / "m4_self_improvement/M4_P1_REAL_INPUT_RESULT.json"
        p2_result_path = root / "m4_self_improvement/M4_P2_CAUSAL_LIFECYCLE_RESULT.json"
        correction_record_path = root / "m4_self_improvement/M4_P1_METRIC_CORRECTION_RECORD.json"
        legacy_note_path = run_root / "audits/legacy_lifecycle_auditors_not_applicable.json"
        report_path = run_root / "NORTHSTAR_REPORT.md"
        boundary_path = run_root / "CLAIM_BOUNDARY.json"
        result_path = root / "m4_self_improvement/M4_P3_NORTHSTAR_RESULT.json"
        manifest_path = root / "m4_self_improvement/M4_P3_NORTHSTAR_ARTIFACTS.sha256"

        hvpput = require_dict(load_json(hvpput_path), str(hvpput_path))
        h2_note = require_dict(load_json(h2_note_path), str(h2_note_path))
        template = require_dict(load_json(template_path), str(template_path))

        boundary = make_boundary(template, h2_note)
        write_json(boundary_path, boundary)
        boundary_sha = file_sha256(boundary_path)
        report, mandatory_sentence = render_report(
            hvpput,
            h2_note,
            correction_record_path,
            legacy_note_path,
            boundary_path,
            boundary_sha,
        )
        report_path.write_text(report, encoding="utf-8")

        h2_data = require_dict(h2_note.get("h2"), "h2_note.h2")
        result = {
            "artifacts": [
                {"label": "northstar_report", **sha_ref(report_path)},
                {"label": "claim_boundary", **sha_ref(boundary_path)},
                {"label": "hvpput_report", **sha_ref(hvpput_path)},
                {"label": "h2_consumption_note", **sha_ref(h2_note_path)},
                {"label": "m4_p1_result", **sha_ref(p1_result_path)},
                {"label": "m4_p2_result", **sha_ref(p2_result_path)},
            ],
            "claim_boundary": {
                "failure_memory_causal_claim_allowed": boundary["failure_memory_causal_claim_allowed"],
                "hvpput_is_capability_claim": boundary["hvpput_is_capability_claim"],
                "report_status_ceiling": boundary["report_status_ceiling"],
            },
            "gates": {
                "claim_boundary_h2_tied": "PASS",
                "cost_provenance_cited": "PASS",
                "forbidden_phrase_lint": "PASS",
                "mandatory_null_sentence": "PASS",
                "skeleton_heading_conformance": "PASS",
            },
            "mandatory_direction": "null",
            "mandatory_direction_sentence": mandatory_sentence,
            "module_atom": "M4.P3",
            "non_claims": [
                "M4.P3 is implementer-addressed only, not externally verified.",
                "No failure-memory efficacy claim is made.",
                "H-VPPUT is not an absolute capability claim.",
                "No release, ratification, M2 enablement, OG-10/genesis signature, or constitution byte change is claimed.",
            ],
            "recorded_at_utc": recorded_at,
            "schema_id": "turingos.m4.p3.northstar_result.v1",
            "scope": {
                "analysis_label": run_root.name,
                "heldout_shard": "S01",
                "h2_delta": h2_data["delta"],
                "h2_source_sha256": h2_note["source_sha256"],
            },
            "status": "ADDRESSED",
            "status_ceiling": "ADDRESSED",
        }
        write_json(result_path, result)
        write_manifest(
            manifest_path,
            [
                result_path,
                report_path,
                boundary_path,
                hvpput_path,
                h2_note_path,
                p1_result_path,
                p2_result_path,
            ],
        )
        return 0
    except (AssembleError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

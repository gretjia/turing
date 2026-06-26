#!/usr/bin/env python3
"""Render GoalRunHandoff.v1 for the TuringOS headless triad run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


HEADLESS = Path(__file__).resolve().parent / "headless"
sys.path.insert(0, str(HEADLESS))

from headless_common import (  # noqa: E402
    NO_HUMAN_STATE_CEILING,
    attach_packet_digest,
    forbidden_claims_present,
    git_commit,
    git_remote,
    load_json,
    maybe_sha256_path,
    print_packet_summary,
    sha256_path,
    utc_now,
    write_json,
)


def collect_gate_matrix(evidence: dict, grok: dict, claude: dict) -> list[dict]:
    matrix = list(evidence.get("gate_matrix", []))
    matrix.append(
        {
            "gate_id": "G12-A",
            "product": "PASS" if grok.get("verdict") == "PASS" else "NOT_RUN",
            "not_run": grok.get("not_run", []),
        }
    )
    matrix.append(
        {
            "gate_id": "G12-B",
            "product": "PASS" if claude.get("verdict") == "MODEL_RATIFIED" else "NOT_RUN",
            "not_run": claude.get("not_run", []),
        }
    )
    dedup: dict[str, dict] = {}
    for row in matrix:
        dedup[row["gate_id"]] = row
    return list(dedup.values())


def derive_status(evidence: dict, grok: dict, claude: dict) -> str:
    not_run = []
    not_run.extend(evidence.get("not_run", []))
    not_run.extend(grok.get("not_run", []))
    not_run.extend(claude.get("not_run", []))
    if not_run:
        return "BLOCKED_NOT_RUN"
    if grok.get("verdict") == "PASS" and claude.get("verdict") == "MODEL_RATIFIED":
        return "MODEL_FINAL_RATIFIED"
    return "IMPLEMENTER_ADDRESSED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--grok-report", required=True)
    parser.add_argument("--claude-packet", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    script = Path(__file__).resolve()
    repo = script.parents[1]
    book = Path(args.book)
    evidence_path = Path(args.evidence)
    grok_path = Path(args.grok_report)
    claude_path = Path(args.claude_packet)
    out = Path(args.out)

    evidence = load_json(evidence_path) if evidence_path.exists() else {}
    grok = load_json(grok_path) if grok_path.exists() else {}
    claude = load_json(claude_path) if claude_path.exists() else {}
    not_run = sorted(
        set(
            evidence.get("not_run", [])
            + grok.get("not_run", [])
            + claude.get("not_run", [])
        )
    )
    human_decisions = []
    ledger_path = evidence.get("human_decision_ledger")
    if ledger_path and Path(ledger_path).exists():
        human_decisions = load_json(Path(ledger_path)).get("requests", [])

    forbidden = forbidden_claims_present(
        [
            " ".join(evidence.get("forbidden_claims_present", [])),
            " ".join(grok.get("forbidden_claims_present", [])),
            " ".join(claude.get("forbidden_claims_present", [])),
        ]
    )
    handoff = {
        "schema_id": "GoalRunHandoff.v1",
        "created_at": utc_now(),
        "status": derive_status(evidence, grok, claude),
        "working_repo": {
            "path": str(repo),
            "remote": git_remote(repo),
            "commit": git_commit(repo),
            "branch": "goal/headless-triad",
        },
        "project_book": str(book),
        "project_book_digest": maybe_sha256_path(book),
        "phase_matrix": evidence.get("phase_matrix", []),
        "gate_matrix": collect_gate_matrix(evidence, grok, claude),
        "addressed_classes": [],
        "closed_derived_classes": [],
        "artifacts": {
            "evidence_bundle": str(evidence_path),
            "evidence_bundle_digest": sha256_path(evidence_path) if evidence_path.exists() else None,
            "grok_report": str(grok_path),
            "grok_report_digest": sha256_path(grok_path) if grok_path.exists() else None,
            "claude_packet": str(claude_path),
            "claude_packet_digest": sha256_path(claude_path) if claude_path.exists() else None,
            "human_decision_ledger": ledger_path,
            "human_decision_ledger_digest": evidence.get("human_decision_ledger_digest"),
            "pack_disposition": evidence.get("pack_disposition"),
            "pack_disposition_digest": evidence.get("pack_disposition_digest"),
        },
        "not_run": not_run,
        "human_decisions_required": human_decisions,
        "m2_status": "DISABLED",
        "state_ceiling": NO_HUMAN_STATE_CEILING,
        "forbidden_claims_present": forbidden,
        "verifier_packet_digest": sha256_path(grok_path) if grok_path.exists() else None,
        "ratifier_packet_digest": sha256_path(claude_path) if claude_path.exists() else None,
        "implementation_origin_state_max": "IMPLEMENTER_ADDRESSED",
    }
    handoff = attach_packet_digest(handoff)
    write_json(out, handoff)
    print_packet_summary(handoff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

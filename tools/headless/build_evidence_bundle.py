#!/usr/bin/env python3
"""Build the non-authority EvidenceBundle.v1 for the headless triad run."""

from __future__ import annotations

import argparse
from pathlib import Path

from headless_common import (
    NO_HUMAN_STATE_CEILING,
    attach_packet_digest,
    base_env_digest,
    clean_fixture_pass,
    detect_missing_foundation_primitives,
    forbidden_claims_present,
    gate_result,
    git_commit,
    git_remote,
    git_tree_digest,
    load_json,
    print_packet_summary,
    runsc_version,
    sha256_path,
    tampered_fixture_fail,
    utc_now,
    which_digest,
    write_json,
)


CONSTITUTION = Path(
    "/home/zephryj/turingos_backup/work/turingos_research/Reference Docs/Turingos宪法.md"
)


def build_human_decision_ledger(repo: Path, book: Path, not_run: list[str]) -> dict:
    return {
        "schema_id": "HumanDecisionLedger.v1",
        "created_at": utc_now(),
        "repo": str(repo),
        "book_digest": sha256_path(book),
        "requests": [
            {
                "schema_id": "HumanDecisionRequest.v1",
                "id": "HDR-001",
                "decision": "Provide human OG-10/genesis Ed25519 signature over exact canonical GenesisEnvelope.v1 bytes.",
                "required_before": "HUMAN_RATIFIED_OR_M2_ENABLED",
                "status": "WAIT_FOR_HUMAN",
            },
            {
                "schema_id": "HumanDecisionRequest.v1",
                "id": "HDR-002",
                "decision": "Provision independent verifier key custody disjoint from implementer, ratifier, and genesis signer keys.",
                "required_before": "CLOSURE_CERTIFICATE_V1",
                "status": "WAIT_FOR_HUMAN",
            },
            {
                "schema_id": "HumanDecisionRequest.v1",
                "id": "HDR-003",
                "decision": "Select or provide the Rust authority-kernel implementation repo/crates for this Foundation P0 goal.",
                "required_before": "F1_AUTHORITY_OWNER_CLOSURE",
                "status": "WAIT_FOR_HUMAN" if "rust_authority_kernel_missing" in not_run else "ADDRESSED",
            },
            {
                "schema_id": "HumanDecisionRequest.v1",
                "id": "HDR-004",
                "decision": "Approve supply-chain closure evidence before any genesis signature request.",
                "required_before": "READY_FOR_HUMAN_GENESIS_SIGNATURE",
                "status": "WAIT_FOR_HUMAN" if "cargo_lock_missing" in not_run else "ADDRESSED",
            },
        ],
    }


def build_pack_disposition(repo: Path, not_run: list[str]) -> dict:
    return {
        "schema_id": "PackDisposition.v1",
        "created_at": utc_now(),
        "repo": str(repo),
        "commit": git_commit(repo),
        "mandatory_dispositions": [
            "NO_OG10",
            "M2_DISABLED",
            "CANDIDATE_UNSIGNED",
            "DO_NOT_CLAIM_CLOSED",
            "NO_CLASS_CLOSED",
        ],
        "implementer_origin_state_max": "IMPLEMENTER_ADDRESSED",
        "derived_state": "BLOCKED_NOT_RUN" if not_run else "IMPLEMENTER_ADDRESSED",
        "m2_status": "DISABLED",
        "not_run": not_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    script = Path(__file__).resolve()
    repo = script.parents[2]
    book = Path(args.book)
    out = Path(args.out)
    out_dir = out.parent

    not_run = detect_missing_foundation_primitives(repo)
    grok_path, grok_digest = which_digest("grok")
    claude_path, claude_digest = which_digest("claude")
    runsc_path, runsc_digest = which_digest("runsc")
    if grok_path is None:
        not_run.append("grok_cli_missing")
    if claude_path is None:
        not_run.append("claude_cli_missing")
    not_run = sorted(set(not_run))

    human_ledger = build_human_decision_ledger(repo, book, not_run)
    pack_disposition = build_pack_disposition(repo, not_run)
    human_path = out_dir / "human_decision_ledger.json"
    pack_path = out_dir / "pack_disposition.json"
    write_json(human_path, human_ledger)
    write_json(pack_path, pack_disposition)
    preflight_log = out_dir / "logs" / "G0-G11-PREFLIGHT.json"
    write_json(
        preflight_log,
        {
            "repo": str(repo),
            "book": str(book),
            "not_run": not_run,
            "tooling": {
                "grok": grok_path,
                "claude": claude_path,
                "runsc": runsc_path,
            },
        },
    )

    command_argv = ["python3", str(script.relative_to(repo)), "--book", str(book), "--out", str(out)]
    gate = gate_result(
        gate_id="G0-G11-PREFLIGHT",
        phase_id="F0-F8",
        command_argv=command_argv,
        exit_status=1 if not_run else 0,
        reasons=[
            {
                "id": "selected_repo_remote",
                "verdict": "PASS" if git_remote(repo) == "https://github.com/gretjia/turing.git" else "FAIL",
                "observed": git_remote(repo),
            },
            {
                "id": "rust_authority_kernel_present",
                "verdict": "PASS" if "rust_authority_kernel_missing" not in not_run else "NOT_RUN",
            },
            {
                "id": "launch_platform_primitives_present",
                "verdict": "PASS" if "runsc_missing" not in not_run else "NOT_RUN",
                "runsc_version": runsc_version(),
            },
        ],
        not_run=not_run,
        tool_path=script,
        input_paths=[book, repo / "evidence/g12/phase_capsule.json"],
        output_path=preflight_log,
        clean_fixture_results=[clean_fixture_pass()],
        tampered_fixture_results=[tampered_fixture_fail()],
    )

    gate_dir = out_dir / "gate_results"
    preflight_path = gate_dir / "G0-G11-PREFLIGHT.json"
    write_json(preflight_path, gate)

    gate_paths = sorted(path for path in gate_dir.glob("*.json") if not path.stem.startswith("G12-"))
    gate_matrix = []
    for gate_path in gate_paths:
        try:
            receipt = load_json(gate_path)
        except Exception:
            continue
        gate_matrix.append(
            {
                "gate_id": receipt.get("gate_id", gate_path.stem),
                "product": receipt.get("product"),
                "not_run": receipt.get("not_run", []),
                "receipt": str(gate_path),
                "receipt_digest": sha256_path(gate_path),
            }
        )

    texts_for_forbidden = [
        " ".join(pack_disposition["mandatory_dispositions"]),
        " ".join(not_run),
    ]
    bundle = {
        "schema_id": "EvidenceBundle.v1",
        "created_at": utc_now(),
        "working_repo": {
            "path": str(repo),
            "remote": git_remote(repo),
            "commit": git_commit(repo),
            "tree_digest": git_tree_digest(repo),
            "branch": "goal/headless-triad",
        },
        "authority_inputs": {
            "project_book": str(book),
            "project_book_digest": sha256_path(book),
            "constitution": str(CONSTITUTION),
            "constitution_digest": sha256_path(CONSTITUTION) if CONSTITUTION.exists() else None,
        },
        "tooling": {
            "grok": {"path": grok_path, "digest": grok_digest},
            "claude": {"path": claude_path, "digest": claude_digest},
            "runsc": {"path": runsc_path, "digest": runsc_digest, "version": runsc_version()},
            "env_allowlist_digest": base_env_digest(),
        },
        "phase_matrix": [
            {"phase_id": phase, "status": "NOT_RUN" if not_run else "IMPLEMENTER_ADDRESSED"}
            for phase in ["F0", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"]
        ],
        "gate_results": [str(path) for path in gate_paths],
        "gate_matrix": gate_matrix,
        "not_run": not_run,
        "state_ceiling": NO_HUMAN_STATE_CEILING,
        "implementer_origin_state_max": "IMPLEMENTER_ADDRESSED",
        "m2_status": "DISABLED",
        "forbidden_claims_present": forbidden_claims_present(texts_for_forbidden),
        "human_decision_ledger": str(human_path),
        "human_decision_ledger_digest": sha256_path(human_path),
        "pack_disposition": str(pack_path),
        "pack_disposition_digest": sha256_path(pack_path),
    }
    bundle = attach_packet_digest(bundle)
    write_json(out, bundle)
    print_packet_summary(bundle)
    return 1 if not_run else 0


if __name__ == "__main__":
    raise SystemExit(main())

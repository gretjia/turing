#!/usr/bin/env python3
"""Build a tiny valid SHA-256 MicroTape fixture for HCI projection audits."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


EMPTY_REASON_DIGEST = "sha256:" + hashlib.sha256(b"[]").hexdigest()


def jcs_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(jcs_bytes(value)).hexdigest()


def git(repo: Path, *args: str, stdin: bytes | None = None) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "turingos-hci-fixture",
            "GIT_AUTHOR_EMAIL": "hci-fixture@turingos.local",
            "GIT_COMMITTER_NAME": "turingos-hci-fixture",
            "GIT_COMMITTER_EMAIL": "hci-fixture@turingos.local",
            "GIT_AUTHOR_DATE": "2026-07-04T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-07-04T00:00:00Z",
        }
    )
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout.decode().strip()


def commit_event(
    repo: Path,
    *,
    event_type: str,
    event_schema_id: str,
    payload: dict[str, Any],
    sequence: int,
    prev_tape_tip: str | None,
    accepted_head_before: str | None,
    authorization_head_before: str | None = None,
    head_effect: str,
    predicate_product: str,
) -> str:
    payload_hash = digest_json(payload)
    envelope = {
        "schema_id": "micro_event_envelope.v1",
        "event_type": event_type,
        "writer_id": "writer:hci-fixture",
        "authority_epoch": 0,
        "sequence": sequence,
        "prev_tape_tip": prev_tape_tip,
        "authorization_head_before": authorization_head_before,
        "accepted_head_before": accepted_head_before,
        "head_effect": head_effect,
        "event_schema_id": event_schema_id,
        "predicate_product": predicate_product,
        "reason_digest": EMPTY_REASON_DIGEST,
        "verified": predicate_product == "PASS",
        "content_digest": payload_hash,
        "payload_hash": payload_hash,
        "payload": payload,
    }
    body = jcs_bytes(envelope)
    blob = git(repo, "hash-object", "-w", "--stdin", stdin=body)
    tree = git(repo, "mktree", stdin=f"100644 blob {blob}\tevent\n".encode())
    args = ["commit-tree", tree]
    if prev_tape_tip:
        args.extend(["-p", prev_tape_tip.removeprefix("mu:")])
    commit = git(repo, *args, stdin=b"turingos hci fixture event\n")
    return f"mu:{commit}"


def build_fixture(out: Path) -> dict[str, str | None]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "--object-format=sha256", "-q", str(out)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    fmt = git(out, "rev-parse", "--show-object-format")
    if fmt != "sha256":
        raise RuntimeError(f"fixture repo is not sha256: {fmt}")

    genesis = commit_event(
        out,
        event_type="SystemConstitutionAccepted",
        event_schema_id="system_constitution_accepted.v1",
        payload={
            "constitution_digest": "sha256:"
            + "a" * 64,
        },
        sequence=0,
        prev_tape_tip=None,
        accepted_head_before=None,
        head_effect="ADVANCE",
        predicate_product="PASS",
    )
    git(out, "update-ref", "refs/turingos/tape_tip", genesis.removeprefix("mu:"))
    git(out, "update-ref", "refs/turingos/accepted_head", genesis.removeprefix("mu:"))

    proposal = commit_event(
        out,
        event_type="GoalStateProposed",
        event_schema_id="goal_state_proposed.v1",
        payload={
            "goal_id": "goal_hci_projection_integrity_fixture",
            "intent": "exercise HCI projection-integrity audit fixture",
        },
        sequence=1,
        prev_tape_tip=genesis,
        accepted_head_before=genesis,
        head_effect="PRESERVE",
        predicate_product="PASS",
    )
    git(
        out,
        "update-ref",
        "refs/turingos/tape_tip",
        proposal.removeprefix("mu:"),
        genesis.removeprefix("mu:"),
    )
    return {
        "schema_id": "hci_fixture_micro_tape.v1",
        "repo": str(out),
        "tape_tip": proposal,
        "authorization_head": None,
        "accepted_head": genesis,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-json")
    args = parser.parse_args()

    summary = build_fixture(Path(args.out))
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.summary_json:
        Path(args.summary_json).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

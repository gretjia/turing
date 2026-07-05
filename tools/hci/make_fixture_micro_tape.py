#!/usr/bin/env python3
"""Build a tiny valid SHA-256 MicroTape fixture for HCI projection audits.

`--scenario default` (the historical, byte-identical two-event tape: genesis +
one proposal) is unchanged by this atom. `--scenario liar` (design spec
`m6_hci/DESIGN_UX_UI_DETAIL_20260705.md` §6) extends the same genesis+proposal
prefix with three capsules exercising the per-item work_items contract:

- Capsule A ("the liar"): dispatched, authorized, run started, and *claimed*
  complete on tape — but no WorkerReceiptImported ever lands. Renders
  AWAITING RECEIPT, counted CLAIMED but never ACCEPTED.
- Capsule B ("the honest one"): the same shape, plus a matching
  WorkerReceiptImported and a CandidateAccepted — renders ACCEPTED WORLD
  STATE with a matched receipt.
- Item C ("the blocked one"): authorized, then halted by a FailureNode
  carrying a machine-readable `blocked_reason` — renders AUTHORIZED with a
  BLOCKED annotation, never double-counted as its own bucket.
"""

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


class TapeState:
    """Tracks the three sovereign heads across a sequence of fixture appends, issuing the
    matching `git update-ref` after each one — the same compare-and-swap shape the real
    append algorithm uses (old value required once a ref exists, absent only at its first
    creation)."""

    def __init__(self, repo: Path, tape_tip: str, accepted_head: str | None, sequence: int):
        self.repo = repo
        self.tape_tip = tape_tip
        self.accepted_head = accepted_head
        self.authorization_head: str | None = None
        self.sequence = sequence

    def append(
        self,
        *,
        event_type: str,
        event_schema_id: str,
        payload: dict[str, Any],
        event_class: str,
        predicate_product: str = "PASS",
    ) -> str:
        head_effect = "ADVANCE" if event_class in ("AUTHORIZATION", "SOVEREIGN_ACCEPT") else "PRESERVE"
        new_event = commit_event(
            self.repo,
            event_type=event_type,
            event_schema_id=event_schema_id,
            payload=payload,
            sequence=self.sequence,
            prev_tape_tip=self.tape_tip,
            accepted_head_before=self.accepted_head,
            authorization_head_before=self.authorization_head,
            head_effect=head_effect,
            predicate_product=predicate_product,
        )
        self._update_ref("refs/turingos/tape_tip", new_event, self.tape_tip)
        self.tape_tip = new_event
        self.sequence += 1
        if event_class == "SOVEREIGN_ACCEPT":
            self._update_ref("refs/turingos/accepted_head", new_event, self.accepted_head)
            self.accepted_head = new_event
        elif event_class == "AUTHORIZATION":
            self._update_ref(
                "refs/turingos/authorization_head", new_event, self.authorization_head
            )
            self.authorization_head = new_event
        return new_event

    def _update_ref(self, ref_name: str, new_event: str, old_event: str | None) -> None:
        args = ["update-ref", ref_name, new_event.removeprefix("mu:")]
        if old_event is not None:
            args.append(old_event.removeprefix("mu:"))
        git(self.repo, *args)


def init_repo(out: Path) -> Path:
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
    return out


def build_genesis_and_proposal(out: Path) -> TapeState:
    """The historical two-event prefix (genesis `SystemConstitutionAccepted` +
    `GoalStateProposed`), byte-identical to the pre-`--scenario` fixture. Both scenarios
    build on top of this exact prefix."""
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
    return TapeState(out, tape_tip=proposal, accepted_head=genesis, sequence=2)


def build_default_fixture(out: Path) -> dict[str, str | None]:
    init_repo(out)
    state = build_genesis_and_proposal(out)
    return {
        "schema_id": "hci_fixture_micro_tape.v1",
        "scenario": "default",
        "repo": str(out),
        "tape_tip": state.tape_tip,
        "authorization_head": state.authorization_head,
        "accepted_head": state.accepted_head,
    }


def _append_capsule_dispatch(state: TapeState, *, capsule_id: str, title: str) -> None:
    state.append(
        event_type="WorkCapsuleBuilt",
        event_schema_id="work_capsule_built.v1",
        payload={"capsule_id": capsule_id, "title": title},
        event_class="PROPOSAL",
    )
    state.append(
        event_type="WorkerDispatchAuthorized",
        event_schema_id="worker_dispatch_authorized.v1",
        payload={"capsule_id": capsule_id},
        event_class="AUTHORIZATION",
    )
    state.append(
        event_type="WorkerRunStarted",
        event_schema_id="worker_run_started.v1",
        payload={"capsule_id": capsule_id},
        event_class="RECEIPT",
    )
    # The worker's own on-tape claim of completion (design spec §6; see
    # `derive_work_items` in `crates/turing-projection/src/lib.rs` for why
    # `WorkerDispatched` — not a new event type — is repurposed for this).
    state.append(
        event_type="WorkerDispatched",
        event_schema_id="worker_dispatched.v1",
        payload={"capsule_id": capsule_id},
        event_class="RECEIPT",
    )


def build_liar_fixture(out: Path) -> dict[str, str | None]:
    init_repo(out)
    state = build_genesis_and_proposal(out)

    # Capsule A ("the liar"): claimed complete, no receipt ever lands.
    _append_capsule_dispatch(state, capsule_id="wc_liar_a", title="Capsule A (the liar)")

    # Capsule B ("the honest one"): same shape, plus a matched receipt and acceptance.
    _append_capsule_dispatch(state, capsule_id="wc_liar_b", title="Capsule B (the honest one)")
    state.append(
        event_type="WorkerReceiptImported",
        event_schema_id="worker_receipt_imported.v1",
        payload={
            "capsule_id": "wc_liar_b",
            "receipt_id": "rcp_liar_b",
            "worker_id": "worker:sha256:" + "b" * 64,
            "exit_code": 0,
            "stdout_hash": digest_json("stdout-b"),
            "stderr_hash": digest_json("stderr-b"),
            "done_json_hash": digest_json("done-b"),
            "credential_material_absent": True,
            "micro_refs_moved": False,
        },
        event_class="RECEIPT",
    )
    state.append(
        event_type="CandidateAccepted",
        event_schema_id="candidate_accepted.v1",
        payload={
            "candidate_id": "cand_liar_b",
            "capsule_id": "wc_liar_b",
            "macro_anchor": "macro:diff:liar_b",
        },
        event_class="SOVEREIGN_ACCEPT",
    )

    # Item C ("the blocked one"): authorized, then halted with a machine-readable reason.
    # `blocked_reason` (and the `capsule_id` correlation key) on a FailureNode payload are a
    # derivation-only convention, not part of the real `failure_node_payload.v1` schema — see
    # the `derive_work_items` doc comment for the documented limitation this implies.
    state.append(
        event_type="WorkCapsuleBuilt",
        event_schema_id="work_capsule_built.v1",
        payload={"capsule_id": "wc_liar_c", "title": "Item C (the blocked one)"},
        event_class="PROPOSAL",
    )
    state.append(
        event_type="WorkerDispatchAuthorized",
        event_schema_id="worker_dispatch_authorized.v1",
        payload={"capsule_id": "wc_liar_c"},
        event_class="AUTHORIZATION",
    )
    state.append(
        event_type="FailureNode",
        event_schema_id="failure_node_payload.v1",
        payload={
            "capsule_id": "wc_liar_c",
            "verified": False,
            "failure_class": "AUTH_REQUIRED",
            "candidate_digest": digest_json("candidate-c"),
            "observation_digest": digest_json("observation-c"),
            "detail": "blocked: gate requires a human signature before dispatch may proceed",
            "blocked_reason": "AUTH_REQUIRED",
        },
        event_class="FAILURE",
        # A FailureNode is never a verified transition (`verified` is always false); its
        # envelope-level `predicate_product` mirrors that (`FAIL`, not `PASS`) for realism —
        # the reducer preserves both heads for a PRESERVE-class event regardless of product,
        # so this doesn't change ref movement, only the honesty of the committed envelope.
        predicate_product="FAIL",
    )

    return {
        "schema_id": "hci_fixture_micro_tape.v1",
        "scenario": "liar",
        "repo": str(out),
        "tape_tip": state.tape_tip,
        "authorization_head": state.authorization_head,
        "accepted_head": state.accepted_head,
        "capsules": [
            {"id": "wc_liar_a", "title": "Capsule A (the liar)"},
            {"id": "wc_liar_b", "title": "Capsule B (the honest one)"},
            {"id": "wc_liar_c", "title": "Item C (the blocked one)"},
        ],
    }


def build_fixture(out: Path, scenario: str = "default") -> dict[str, Any]:
    if scenario == "default":
        return build_default_fixture(out)
    if scenario == "liar":
        return build_liar_fixture(out)
    raise ValueError(f"unknown --scenario {scenario!r}; supported: default, liar")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-json")
    parser.add_argument(
        "--scenario",
        choices=["default", "liar"],
        default="default",
        help="default: byte-identical historical 2-event tape. liar: design spec §6 fixture "
        "(capsule A claimed/no-receipt, capsule B receipt-matched+accepted, item C blocked).",
    )
    args = parser.parse_args()

    summary = build_fixture(Path(args.out), args.scenario)
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.summary_json:
        Path(args.summary_json).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""turingos.replay — deterministic Tape-only replay + q_t reconstruction + handoff bundle (M4).

Frozen Stage-0 interface (contracts/INTERFACES.md replay.py section):

    @dataclass(frozen=True) ReplayState{accepted_head, q_t, workgraph}
    replay(tape) -> ReplayState
    make_handoff_bundle(tape, out_dir) -> str
    replay_from_handoff(bundle_dir) -> ReplayState
    verify_replay_equal(tape) -> bool

Load-bearing invariants (CLAUDE.md / contracts/refs.md):

  * Tape-Canonical [Art. 0.2]: ALL 1.0 state is rebuildable from the Micro Tape; sqlite / projection
    / TUI are derived only. `replay` walks the Tape bytes ALONE (tape.walk()) — it never reads a
    sqlite/projection file and never requires one to exist. accepted_head is rebuilt as the OID of
    the LAST event whose class == SOVEREIGN_ACCEPT (the registry decides the class, never the writer),
    and is asserted to equal the on-disk refs/turingos/accepted_head.

  * Integrity: for every node, the recomputed codec.content_digest(payload) MUST equal the stored
    envelope['payload_hash'], and the registry-derived head_effect MUST equal envelope['head_effect'].
    A mismatch means the Tape was tampered with -> raise (the accepted state is NOT rebuildable, so we
    refuse to silently replay it).

  * Determinism [Art. I.1]: the same Tape bytes always reduce to byte-equal (accepted_head, q_t,
    workgraph) — the precondition for replay equality. `verify_replay_equal` replays twice and compares
    the canonical content_digest of a canonical dump of the triple.

  * Handoff: one active sovereign writer + explicit handoff. `make_handoff_bundle` records a
    HandoffGenerated event on the source Tape, bare-clones the Micro repo into the bundle, and writes a
    manifest; `replay_from_handoff` opens the bundled repo and replays it to the same accepted_head in a
    fresh Tape. (The Micro Tape is a SEPARATE private SHA-256 repo — never pushed to a forge.)

Stdlib only (`subprocess`, `json`, `pathlib`, `dataclasses`).
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import codec, reduce, registry
from .errors import RejectedAppend
from .tape import Tape

# The event class that advances accepted_head (registry-derived, never writer-trusted).
_ADVANCE_CLASS = "SOVEREIGN_ACCEPT"

# Bundle layout produced by make_handoff_bundle / consumed by replay_from_handoff.
_BUNDLE_TAPE_DIR = "tape.git"
_BUNDLE_MANIFEST = "manifest.json"

# Deterministic identity for any git plumbing replay drives directly (bare clone).
_TAPE_GIT_ENV = {
    "GIT_AUTHOR_NAME": "turingos",
    "GIT_AUTHOR_EMAIL": "tape@turingos.local",
    "GIT_COMMITTER_NAME": "turingos",
    "GIT_COMMITTER_EMAIL": "tape@turingos.local",
    "GIT_AUTHOR_DATE": "2026-06-20T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2026-06-20T00:00:00+0000",
}


@dataclass(frozen=True)
class ReplayState:
    """The world state rebuilt from the Tape: accepted_head + folded q_t + derived WorkGraph."""

    accepted_head: str | None
    q_t: dict
    workgraph: dict


def _git(repo_dir: str, *args: str) -> str:
    """Run a git command in `repo_dir` with deterministic identity. No shell. Raises on failure."""
    env = {**os.environ, **_TAPE_GIT_ENV}
    result = subprocess.run(
        ["git", "-C", repo_dir, *args],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        raise RejectedAppend(
            f"git {' '.join(args)} -> {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def replay(tape: "Tape") -> ReplayState:
    """Rebuild the accepted world state from the Micro Tape bytes ONLY (no sqlite/projection).

    Walks genesis..tape_tip in order (tape.walk()). For each node:
      * recompute codec.content_digest(payload) and assert == envelope['payload_hash']  (integrity);
      * re-derive registry.head_effect(event_type) and assert == envelope['head_effect'] (registry-truth).
    accepted_head_rebuilt = OID (no 'mu:' prefix) of the LAST event whose registry class is
    SOVEREIGN_ACCEPT; asserted to equal tape.accepted_head() on disk. q_t = reduce.reduce_qt(tape);
    workgraph = reduce.derive_workgraph(q_t, tape, []). Deterministic and byte-stable.
    """
    accepted_rebuilt: str | None = None

    for ev in tape.walk():
        event_type = ev["event_type"]
        payload = ev["payload"]
        envelope = ev["envelope"]
        oid = ev["oid"]

        # INTEGRITY: recomputed digest must match the stored payload_hash (tamper => raise).
        recomputed = codec.content_digest(payload)
        stored = envelope.get("payload_hash")
        if recomputed != stored:
            raise RejectedAppend(
                f"tape integrity: node {oid} payload_hash mismatch "
                f"(stored {stored!r} != recomputed {recomputed!r})"
            )

        # REGISTRY-TRUTH: head_effect is registry-derived, never writer-trusted.
        if not registry.is_known(event_type):
            raise RejectedAppend(f"tape integrity: node {oid} has unknown event_type {event_type!r}")
        derived_he = registry.head_effect(event_type)
        stored_he = envelope.get("head_effect")
        if derived_he != stored_he:
            raise RejectedAppend(
                f"tape integrity: node {oid} head_effect mismatch "
                f"(stored {stored_he!r} != registry-derived {derived_he!r})"
            )

        # accepted_head = the LAST SOVEREIGN_ACCEPT commit (the class decides, never the writer).
        if registry.event_class(event_type) == _ADVANCE_CLASS:
            accepted_rebuilt = oid

    # The rebuilt accepted_head MUST equal the on-disk ref — else the tape is not Tape-Canonical.
    on_disk = tape.accepted_head()
    if accepted_rebuilt != on_disk:
        raise RejectedAppend(
            f"tape integrity: rebuilt accepted_head {accepted_rebuilt!r} != on-disk {on_disk!r}"
        )

    q_t = reduce.reduce_qt(tape)
    workgraph = reduce.derive_workgraph(q_t, tape, [])
    return ReplayState(accepted_head=accepted_rebuilt, q_t=q_t, workgraph=workgraph)


def _canonical_dump(state: ReplayState) -> dict:
    """A codec-safe canonical dump of the replay triple for byte-deterministic comparison."""
    return {
        "accepted_head": state.accepted_head,
        "q_t": state.q_t,
        "workgraph": state.workgraph,
    }


def make_handoff_bundle(tape: "Tape", out_dir: str) -> str:
    """Record a HandoffGenerated event, bare-clone the Micro repo into the bundle, write a manifest.

    Returns the bundle directory. The bundle is self-contained: out_dir/tape.git (a bare clone of the
    Micro Tape) + out_dir/manifest.json {accepted_head, tape_tip, writer}. The clone is taken AFTER the
    HandoffGenerated append so the bundled tape carries the handoff record (the explicit-handoff seam).
    """
    writer = tape.current_writer()
    # PRESERVE event: tape_tip advances, accepted_head does not. Records the replay/handoff production.
    tape.append(
        "HandoffGenerated",
        {"from_writer": writer, "to_writer": writer, "kind": "bundle"},
        writer_id=writer,
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bundle_repo = str(out / _BUNDLE_TAPE_DIR)

    # Bare-clone the SEPARATE Micro Tape repo into the bundle (refs come along with --bare/--mirror).
    # --mirror copies refs/turingos/* verbatim so the bundle's two refs match the source exactly.
    _git(tape.repo_dir, "clone", "--bare", "--mirror", tape.repo_dir, bundle_repo)

    manifest = {
        "accepted_head": tape.accepted_head(),
        "tape_tip": tape.tape_tip(),
        "writer": writer,
    }
    (out / _BUNDLE_MANIFEST).write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return str(out)


def replay_from_handoff(bundle_dir: str) -> ReplayState:
    """Open the bundled Micro Tape repo and replay it to a ReplayState (fresh, Tape-only)."""
    bundle = Path(bundle_dir)
    bundle_repo = str(bundle / _BUNDLE_TAPE_DIR)
    if not Path(bundle_repo).exists():
        raise RejectedAppend(f"handoff bundle missing {_BUNDLE_TAPE_DIR}: {bundle_repo}")

    # Read the recorded writer (best-effort) so the opened Tape carries a sensible writer id.
    writer = "handoff-reader"
    manifest_path = bundle / _BUNDLE_MANIFEST
    if manifest_path.exists():
        try:
            writer = json.loads(manifest_path.read_text(encoding="utf-8")).get("writer", writer)
        except (OSError, json.JSONDecodeError):
            pass

    bundled_tape = Tape(bundle_repo, writer)
    return replay(bundled_tape)


def verify_replay_equal(tape: "Tape") -> bool:
    """Replay twice; compare the canonical content_digest of the (accepted_head, q_t, workgraph) triple.

    On match, emits a ReplayVerified observation (PRESERVE — tape_tip advances, accepted_head does not)
    and returns True; returns False on a mismatch (without claiming acceptance).
    """
    first = replay(tape)
    second = replay(tape)

    digest_a = codec.content_digest(_canonical_dump(first))
    digest_b = codec.content_digest(_canonical_dump(second))
    equal = digest_a == digest_b

    writer = tape.current_writer()
    tape.append(
        "ReplayVerified",
        {
            "equal": equal,
            "replay_digest": digest_a,
            "accepted_head": first.accepted_head or "",
        },
        writer_id=writer,
    )
    return equal

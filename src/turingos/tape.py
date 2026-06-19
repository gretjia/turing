"""turingos.tape — the SHA-256 Micro Git ChainTape + 2 refs + single-writer guard (M2).

Frozen Stage-0 interface (contracts/INTERFACES.md tape.py section, contracts/refs.md,
contracts/append_envelope.md). This module is the SUBSTRATE: every sovereignty-boundary
change is exactly one non-merge commit on a real Git repo whose object format is native
SHA-256. Two refs and only two refs live under `refs/turingos/`:

  refs/turingos/tape_tip       — advances on EVERY valid append (incl. FailureNodes) [Art. 0.2/0.3]
  refs/turingos/accepted_head  — advances ONLY on a SOVEREIGN_ACCEPT event with a deterministic
                                 Predicate PASS (HEAD_t = accepted_head) [Art. 0.4]

There is NO `refs/turingos/authorization_head` in 1.0 — ordinary authorization is a PRESERVE
Tape event, not a third-ref advance.

Two guards are enforced LOCALLY before any commit lands (the 1.0 subset of the future server
authority guard — S-2 evidence):

  * single-writer identity — the FIRST SystemBootstrapped establishes the current sovereign
    writer; every later append must come from current_writer() (or a HandoffGenerated changes
    who that is). Wrong-writer => GuardReject.
  * FF-only — the parent the writer built on must equal the live tape_tip at commit time; a
    stale-parent view => GuardReject. In 1.0 this is the in-process subset of the future server
    pre-receive non-FF check (S-2 single-writer scope); it does not, on its own, guarantee against
    a true concurrent external mutation between the in-call reads — that is the server-hook seam.
  * accepted_head ancestor (append_envelope guard #6) — the accepted_head the writer observed
    (accepted_head_before) must be an ancestor of the live tape_tip; a non-ancestor accepted state
    => GuardReject (audit/consistency; defense-in-depth for external mutation / future multi-writer).

Tape-canonical replay invariant: an ADVANCE (SOVEREIGN_ACCEPT) append MUST carry
predicate_pass=True, else it is RejectedAppend — a FAILED accept is emitted as a FailureNode
(OBSERVATION), never as a non-advancing SOVEREIGN_ACCEPT. So "SOVEREIGN_ACCEPT on the tape
<=> accepted_head advanced", and replay can rebuild accepted_head = last SOVEREIGN_ACCEPT
commit from Tape bytes alone, with no predicate_pass flag stored.

Stdlib only (`subprocess`, `json`, `pathlib`). The Micro Tape is a SEPARATE git repo from the
build repo; never confuse the two and never push the Micro Tape to a forge.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import codec, registry
from .envelope import AppendEnvelope
from .errors import GuardReject, RejectedAppend

# Frozen ref names — exactly two, never a third (authorization_head).
_TAPE_TIP_REF = "refs/turingos/tape_tip"
_ACCEPTED_HEAD_REF = "refs/turingos/accepted_head"

# The single node blob committed per event.
_NODE_FILE = "node.json"

# Writer-establishing events the guard reads to resolve current_writer().
_BOOTSTRAP_EVENT = "SystemBootstrapped"
_HANDOFF_EVENT = "HandoffGenerated"

# Deterministic identity for every commit the Tape makes (no host/user leakage; reproducible).
_TAPE_GIT_ENV = {
    "GIT_AUTHOR_NAME": "turingos",
    "GIT_AUTHOR_EMAIL": "tape@turingos.local",
    "GIT_COMMITTER_NAME": "turingos",
    "GIT_COMMITTER_EMAIL": "tape@turingos.local",
    "GIT_AUTHOR_DATE": "2026-06-20T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2026-06-20T00:00:00+0000",
}


class Tape:
    """A SHA-256 Micro Git ChainTape with two refs and a single-writer FF guard."""

    def __init__(self, repo_dir: str, writer_id: str):
        self.repo_dir = str(Path(repo_dir).resolve())
        self.writer_id = writer_id

    # --- construction -----------------------------------------------------------------------------

    @classmethod
    def init(cls, repo_dir: str, writer_id: str) -> "Tape":
        """`git init --object-format=sha256` + FF/delete protection + local identity.

        Idempotent on the object format: re-initialising an existing sha256 repo is fine; a repo
        that already exists with a different object format is a hard error (we never silently mix).
        """
        path = Path(repo_dir)
        path.mkdir(parents=True, exist_ok=True)
        repo = str(path.resolve())

        # git init is safe to run on an existing repo; it will not clobber refs.
        cls._git(repo, "init", "--object-format=sha256", check=True)

        fmt = cls._git(repo, "rev-parse", "--show-object-format", check=True).stdout.strip()
        if fmt != "sha256":
            raise RejectedAppend(
                f"micro tape at {repo} has object-format {fmt!r}, expected 'sha256'"
            )

        # FF-only, append-only substrate [refs.md F-1].
        cls._git(repo, "config", "receive.denyNonFastForwards", "true", check=True)
        cls._git(repo, "config", "receive.denyDeletes", "true", check=True)
        # Local committer identity (env still overrides at commit time; this is the floor).
        cls._git(repo, "config", "user.name", "turingos", check=True)
        cls._git(repo, "config", "user.email", "tape@turingos.local", check=True)

        return cls(repo, writer_id)

    # --- git plumbing -----------------------------------------------------------------------------

    @staticmethod
    def _git(repo_dir: str, *args, check: bool):
        """Run a git command in `repo_dir` with deterministic identity. No shell."""
        env = {**os.environ, **_TAPE_GIT_ENV}
        result = subprocess.run(
            ["git", "-C", repo_dir, *args],
            capture_output=True, text=True, env=env,
        )
        if check and result.returncode != 0:
            raise RejectedAppend(
                f"git {' '.join(args)} -> {result.returncode}: {result.stderr.strip()}"
            )
        return result

    def _g(self, *args, check: bool = True):
        return self._git(self.repo_dir, *args, check=check)

    def _resolve_ref(self, ref: str) -> str | None:
        """Return the commit OID a ref points at, or None if the ref does not exist yet."""
        result = self._g("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
        oid = result.stdout.strip()
        return oid if result.returncode == 0 and oid else None

    def _is_ancestor(self, maybe_ancestor: str, descendant: str) -> bool:
        """True iff commit `maybe_ancestor` is an ancestor of (or equal to) `descendant`.

        `git merge-base --is-ancestor A B` exits 0 when A is an ancestor of B (or A == B),
        1 when it is not, and other codes on error. Used to enforce append_envelope guard #6
        (accepted_head_before MUST be an ancestor of tape_tip) over Tape bytes.
        """
        result = self._g(
            "merge-base", "--is-ancestor", maybe_ancestor, descendant, check=False
        )
        if result.returncode == 0:
            return True
        if result.returncode == 1:
            return False
        raise RejectedAppend(
            f"git merge-base --is-ancestor {maybe_ancestor} {descendant} "
            f"-> {result.returncode}: {result.stderr.strip()}"
        )

    # --- inspectors -------------------------------------------------------------------------------

    def object_format(self) -> str:
        return self._g("rev-parse", "--show-object-format").stdout.strip()

    def tape_tip(self) -> str | None:
        return self._resolve_ref(_TAPE_TIP_REF)

    def accepted_head(self) -> str | None:
        return self._resolve_ref(_ACCEPTED_HEAD_REF)

    def current_writer(self) -> str:
        """The current sovereign writer, read from the latest writer-establishing Tape event.

        Scans rev-list newest-first: the first HandoffGenerated's payload['to_writer'] wins; else
        the first SystemBootstrapped's envelope.writer_id. Raises if no boot event exists yet.
        """
        tip = self.tape_tip()
        if tip is None:
            raise RejectedAppend("no writer-establishing event on the tape yet")
        log = self._g("rev-list", tip).stdout.split()  # newest first
        for oid in log:
            node = self._read_node(oid)
            etype = node["event_type"]
            if etype == _HANDOFF_EVENT:
                return node["payload"]["to_writer"]
            if etype == _BOOTSTRAP_EVENT:
                return node["envelope"]["writer_id"]
        raise RejectedAppend("no SystemBootstrapped/HandoffGenerated event found on the tape")

    # --- node read helpers ------------------------------------------------------------------------

    def _read_node(self, oid: str) -> dict:
        """Read and parse the node.json blob committed at `oid`."""
        raw = self._g("cat-file", "-p", f"{oid}:{_NODE_FILE}").stdout
        return json.loads(raw)

    def _parents(self, oid: str) -> list[str]:
        out = self._g("rev-list", "--parents", "-n", "1", oid).stdout.split()
        # rev-list --parents -n1 prints: <commit> <parent...>
        return out[1:] if len(out) > 1 else []

    def read_event(self, event_id: str) -> dict:
        """Resolve an event_id ("mu:"+oid) to its node + git metadata."""
        if not isinstance(event_id, str) or not event_id.startswith("mu:"):
            raise RejectedAppend(f"not an event_id (expected 'mu:'+oid): {event_id!r}")
        oid = event_id[len("mu:"):]
        node = self._read_node(oid)
        return {
            "event_type": node["event_type"],
            "payload": node["payload"],
            "envelope": node["envelope"],
            "oid": oid,
            "parents": self._parents(oid),
        }

    def walk(self) -> list[dict]:
        """Genesis..tape_tip in chronological order (each entry as read_event)."""
        tip = self.tape_tip()
        if tip is None:
            return []
        oids = self._g("rev-list", "--reverse", tip).stdout.split()
        return [self.read_event("mu:" + oid) for oid in oids]

    # --- the append path --------------------------------------------------------------------------

    def append(
        self,
        event_type: str,
        payload: dict,
        *,
        writer_id: str | None = None,
        predicate_pass: bool | None = None,
        _expect_parent: str | None = None,
    ) -> str:
        """Append one event as exactly one Micro commit; return its event_id ("mu:"+oid).

        All guards reject (raise) BEFORE any commit lands, so a rejected append never moves a ref.

        _expect_parent is an internal test hook: it lets a caller simulate having built on a stale
        parent so the FF re-read guard can be exercised. Production callers leave it None.
        """
        # GUARD 0: closed-world schema-known (reject unknown types before anything else).
        if not registry.is_known(event_type):
            raise RejectedAppend(f"unknown event_type {event_type!r} (closed-world)")

        he = registry.head_effect(event_type)  # registry-derived ADVANCE|PRESERVE, never trusted
        payload_hash = codec.content_digest(payload)  # also runs the ASCII-key / no-float codec guard

        # The parent we believe we are building on (genesis => None).
        parent = self.tape_tip()
        # The _expect_parent hook lets a test pin a stale parent view to trigger the FF guard.
        believed_parent = _expect_parent if _expect_parent is not None else parent

        # GUARD: single-writer identity. The FIRST SystemBootstrapped establishes the writer; every
        # later append's writer (writer_id or self.writer_id) MUST equal current_writer().
        effective_writer = writer_id if writer_id is not None else self.writer_id
        is_genesis_boot = parent is None and event_type == _BOOTSTRAP_EVENT
        if not is_genesis_boot:
            cw = self.current_writer()
            if effective_writer != cw:
                raise GuardReject(
                    f"wrong_writer: {effective_writer!r} != current sovereign writer {cw!r}"
                )

        # GUARD: ADVANCE invariant — a SOVEREIGN_ACCEPT MUST carry predicate_pass=True, else reject.
        # (A failed accept is a FailureNode, never a non-advancing SOVEREIGN_ACCEPT.)
        if he == "ADVANCE" and predicate_pass is not True:
            raise RejectedAppend(
                "advance requires predicate PASS; emit a FailureNode for a failed accept"
            )

        # GUARD: FF re-read just before committing. In the 1.0 single-writer model (S-2) this
        # rejects a stale-parent view (e.g. the caller built on a tip that has since advanced in
        # this process); it is the in-process subset of the future server pre-receive non-FF check
        # and is NOT a guarantee against a true concurrent external mutation between the in-call
        # reads (that seam belongs to the server hook). believed_parent is the parent the writer
        # built on; if it != the live tape_tip, reject as non-FF.
        live_tip = self.tape_tip()
        if believed_parent != live_tip:
            raise GuardReject(
                f"non_ff: built on parent {believed_parent!r} but live tape_tip is {live_tip!r}"
            )

        # GUARD 6 (append_envelope.md #6 / refs.md / INTERFACES tape docstring): the accepted_head
        # the writer observed (accepted_head_before) MUST be an ancestor of the live tape_tip. This
        # is the load-bearing audit/consistency invariant that keeps accepted_head on the accepted
        # path the tape actually walks. At genesis there is no accepted_head and no tip yet, so the
        # check is vacuous; once both exist, a non-ancestor accepted_head_before is a hard reject
        # (external mutation / corrupted-view defense-in-depth; matters under future multi-writer).
        accepted_before = self.accepted_head()
        if accepted_before is not None and live_tip is not None:
            if not self._is_ancestor(accepted_before, live_tip):
                raise GuardReject(
                    f"accepted_head_before {accepted_before!r} is not an ancestor of "
                    f"live tape_tip {live_tip!r} (guard #6 / inconsistent accepted state)"
                )

        # Build the frozen 7-field envelope (head_effect registry-derived, never writer-supplied).
        envelope = AppendEnvelope(
            prev_tape_tip=parent or "",
            event_schema_id=event_type,
            payload_hash=payload_hash,
            head_effect=he,
            accepted_head_before=accepted_before or "",  # the value guard #6 verified as ancestor
            writer_id=effective_writer,
            authority_epoch=0,
        )
        node = {
            "event_type": event_type,
            "payload": payload,
            "envelope": envelope.to_payload(),
        }

        # Write the node blob, stage, and commit ONE non-merge commit with deterministic identity.
        node_path = Path(self.repo_dir) / _NODE_FILE
        node_path.write_text(
            json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        self._g("add", _NODE_FILE)
        self._g(
            "commit", "--no-gpg-sign", "--allow-empty-message", "-m",
            f"{event_type} {payload_hash}",
        )
        new_oid = self._g("rev-parse", "HEAD").stdout.strip()

        # tape_tip ALWAYS advances on a valid append (incl. FailureNodes) [Art. 0.2/0.3].
        self._g("update-ref", _TAPE_TIP_REF, new_oid)
        # accepted_head advances IFF head_effect == ADVANCE (and predicate_pass==True, already
        # asserted above). NEVER touch authorization_head — it does not exist in 1.0.
        if he == "ADVANCE":
            self._g("update-ref", _ACCEPTED_HEAD_REF, new_oid)

        return codec.event_id_from_oid(new_oid)

    def handoff(self, to_writer: str) -> str:
        """Emit a HandoffGenerated event (PRESERVE) that changes who the guard admits."""
        from_writer = self.current_writer()
        return self.append(
            _HANDOFF_EVENT,
            {"from_writer": from_writer, "to_writer": to_writer},
            writer_id=from_writer,
        )

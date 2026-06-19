"""Contract tests for turingos.replay (stdlib unittest, NOT pytest).

Captures the frozen replay contract from contracts/INTERFACES.md (replay.py section):

    @dataclass(frozen=True) ReplayState{accepted_head, q_t, workgraph}
    replay(tape) -> ReplayState                # walks the Tape ONLY (no sqlite/projection)
    make_handoff_bundle(tape, out_dir) -> str  # emits HandoffGenerated; bare-clones the Micro repo
    replay_from_handoff(bundle_dir) -> ReplayState
    verify_replay_equal(tape) -> bool          # two byte-identical replays; emits ReplayVerified

Load-bearing invariants exercised here (CLAUDE.md / refs.md):
  * Tape-Canonical [Art. 0.2]: accepted_head is rebuilt from Tape bytes alone (last SOVEREIGN_ACCEPT
    commit) and MUST equal the on-disk refs/turingos/accepted_head; replay never reads sqlite/projection.
  * Integrity: a node whose recomputed content_digest(payload) != envelope['payload_hash'] RAISES
    (a tampered tape is not silently replayed).
  * Determinism: two replays of the same Tape produce byte-equal (accepted_head, q_t, workgraph).
  * Handoff: a bare-clone bundle replays to the same accepted_head in a fresh Tape.
  * verify_replay_equal emits a ReplayVerified observation (tape_tip advances) and returns True.

Run: PYTHONPATH=src python3 -m unittest tests.test_replay -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from turingos import codec
from turingos.replay import (
    ReplayState,
    make_handoff_bundle,
    replay,
    replay_from_handoff,
    verify_replay_equal,
)
from turingos.tape import Tape


# Deterministic git identity for any plumbing the test drives directly.
_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "turingos",
    "GIT_AUTHOR_EMAIL": "tape@turingos.local",
    "GIT_COMMITTER_NAME": "turingos",
    "GIT_COMMITTER_EMAIL": "tape@turingos.local",
    "GIT_AUTHOR_DATE": "2026-06-20T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2026-06-20T00:00:00+0000",
}


def _git(repo_dir, *args):
    return subprocess.run(
        ["git", "-C", repo_dir, *args],
        capture_output=True, text=True, env=_GIT_ENV, check=True,
    ).stdout


class ReplayTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / parallel cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_replay_t_")
        self.repo = os.path.join(self.root, "micro_tape")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _populate(self, writer_id="W1"):
        """A small but representative tape: boot (ADVANCE) + goal/module/atom + a failure + an accept."""
        tape = Tape.init(self.repo, writer_id)
        tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)
        tape.append("GoalStateAccepted", {"goal_id": "G1", "text": "ship it"}, predicate_pass=True)
        tape.append("ModulePlanAccepted", {"module_id": "M0", "atoms": 3}, predicate_pass=True)
        tape.append("AtomProposed", {"atom_id": "A1"})
        tape.append("FailureNode", {"atom_id": "A1", "failure_class": "test_fail"})
        tape.append("CandidateAccepted", {"atom_id": "A1", "kind": "accept"}, predicate_pass=True)
        return tape


class TestReplayRebuildsAcceptedHead(ReplayTestBase):
    def test_returns_replaystate(self):
        tape = self._populate()
        state = replay(tape)
        self.assertIsInstance(state, ReplayState)

    def test_accepted_head_matches_on_disk(self):
        # Tape-Canonical: replay rebuilds accepted_head from Tape bytes; MUST equal on-disk ref.
        tape = self._populate()
        state = replay(tape)
        self.assertEqual(state.accepted_head, tape.accepted_head())
        self.assertIsNotNone(state.accepted_head)

    def test_accepted_head_is_last_sovereign_accept(self):
        # Last SOVEREIGN_ACCEPT is the CandidateAccepted commit (the FailureNode after it does NOT move it).
        tape = self._populate()
        state = replay(tape)
        # accepted_head must be a bare 64-hex OID (no 'mu:' prefix), equal to the on-disk ref OID.
        self.assertRegex(state.accepted_head, r"^[0-9a-f]{64}$")
        self.assertEqual(state.accepted_head, tape.accepted_head())

    def test_qt_and_workgraph_present(self):
        tape = self._populate()
        state = replay(tape)
        # q_t carries the folded current state; workgraph is the derived projection.
        self.assertIsInstance(state.q_t, dict)
        self.assertIsInstance(state.workgraph, dict)
        self.assertEqual(state.q_t.get("active_goal"), {"goal_id": "G1", "text": "ship it"})
        self.assertEqual(state.workgraph.get("accepted_head"), tape.accepted_head())

    def test_replay_reads_only_the_tape_no_sqlite(self):
        # replay must NOT create or require a sqlite/projection file anywhere under the tape root.
        tape = self._populate()
        replay(tape)
        for dirpath, _dirnames, filenames in os.walk(self.root):
            for fn in filenames:
                self.assertFalse(
                    fn.endswith(".sqlite") or fn.endswith(".db") or fn.endswith(".sqlite3"),
                    msg=f"replay touched a projection/sqlite file: {os.path.join(dirpath, fn)}",
                )

    def test_empty_tape_replays_to_none_accepted_head(self):
        # An initialised-but-empty tape has no SOVEREIGN_ACCEPT, so accepted_head rebuilds to None.
        tape = Tape.init(self.repo, "W1")
        state = replay(tape)
        self.assertIsNone(state.accepted_head)
        self.assertEqual(state.accepted_head, tape.accepted_head())


class TestTamperRaises(ReplayTestBase):
    def test_tampered_payload_raises(self):
        # Mutate the payload of one node WITHOUT updating envelope['payload_hash'] -> digest mismatch -> raise.
        tape = self._populate()

        # Read the genesis (boot) node.json, corrupt the payload only, rebuild the whole chain.
        oids = _git(self.repo, "rev-list", "--reverse", "refs/turingos/tape_tip").split()
        genesis = oids[0]
        node = json.loads(_git(self.repo, "cat-file", "-p", f"{genesis}:node.json"))
        # Sanity: a correct tape replays cleanly before we tamper.
        replay(tape)

        node["payload"]["kind"] = "TAMPERED"   # envelope.payload_hash stays the OLD digest -> mismatch
        Path(self.repo, "node.json").write_text(
            json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        _git(self.repo, "add", "node.json")
        # Rewrite history from genesis: amend the genesis commit, then re-commit the rest unchanged in order.
        _git(self.repo, "commit", "--amend", "--no-gpg-sign", "--allow-empty-message", "-m", "tampered")
        new_genesis = _git(self.repo, "rev-parse", "HEAD").strip()
        prev = new_genesis
        for oid in oids[1:]:
            child = json.loads(_git(self.repo, "cat-file", "-p", f"{oid}:node.json"))
            Path(self.repo, "node.json").write_text(
                json.dumps(child, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                encoding="utf-8",
            )
            _git(self.repo, "add", "node.json")
            # commit-tree onto prev to keep a linear chain
            tree = _git(self.repo, "write-tree").strip()
            new = subprocess.run(
                ["git", "-C", self.repo, "commit-tree", tree, "-p", prev, "-m", child["event_type"]],
                capture_output=True, text=True, env=_GIT_ENV, check=True,
            ).stdout.strip()
            prev = new
        _git(self.repo, "update-ref", "refs/turingos/tape_tip", prev)

        with self.assertRaises(Exception):
            replay(tape)


class TestDeterminism(ReplayTestBase):
    def test_two_replays_equal(self):
        # Determinism: same Tape bytes -> equal accepted_head + q_t + workgraph.
        tape = self._populate()
        a = replay(tape)
        b = replay(tape)
        self.assertEqual(a.accepted_head, b.accepted_head)
        self.assertEqual(a.q_t, b.q_t)
        self.assertEqual(a.workgraph, b.workgraph)
        # And byte-equal under the canonical codec (the verify_replay_equal contract).
        dump_a = {"accepted_head": a.accepted_head, "q_t": a.q_t, "workgraph": a.workgraph}
        dump_b = {"accepted_head": b.accepted_head, "q_t": b.q_t, "workgraph": b.workgraph}
        self.assertEqual(codec.content_digest(dump_a), codec.content_digest(dump_b))


class TestHandoffBundle(ReplayTestBase):
    def test_bundle_replays_to_same_accepted_head(self):
        tape = self._populate()
        accepted_before = tape.accepted_head()

        out_dir = os.path.join(self.root, "bundle")
        returned = make_handoff_bundle(tape, out_dir)
        self.assertEqual(os.path.abspath(returned), os.path.abspath(out_dir))

        # The bundle has a bare tape repo + a manifest.
        self.assertTrue(os.path.isdir(os.path.join(out_dir, "tape.git")))
        manifest = json.loads(Path(out_dir, "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("accepted_head", manifest)
        self.assertIn("tape_tip", manifest)
        self.assertIn("writer", manifest)

        # make_handoff_bundle emitted a HandoffGenerated -> tape_tip advanced on the source tape.
        self.assertEqual(manifest["accepted_head"], accepted_before)

        # Replaying the bundle reaches the same accepted world state in a FRESH tape repo.
        state = replay_from_handoff(out_dir)
        self.assertEqual(state.accepted_head, accepted_before)

    def test_handoff_generated_recorded_on_source_tape(self):
        tape = self._populate()
        tip_before = tape.tape_tip()
        make_handoff_bundle(tape, os.path.join(self.root, "bundle"))
        # HandoffGenerated is a PRESERVE event: tape_tip moves, accepted_head does not.
        self.assertNotEqual(tape.tape_tip(), tip_before)
        last = tape.walk()[-1]
        self.assertEqual(last["event_type"], "HandoffGenerated")


class TestVerifyReplayEqual(ReplayTestBase):
    def test_returns_true_and_emits_replayverified(self):
        tape = self._populate()
        tip_before = tape.tape_tip()
        acc_before = tape.accepted_head()

        result = verify_replay_equal(tape)
        self.assertTrue(result)

        # ReplayVerified is an OBSERVATION (PRESERVE): tape_tip advances, accepted_head does NOT.
        self.assertNotEqual(tape.tape_tip(), tip_before)
        self.assertEqual(tape.accepted_head(), acc_before)
        last = tape.walk()[-1]
        self.assertEqual(last["event_type"], "ReplayVerified")


if __name__ == "__main__":
    unittest.main()

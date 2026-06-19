"""S-1 / S-2 contract tests for turingos.tape.Tape (stdlib unittest, NOT pytest).

These tests capture the frozen Tape contract from contracts/INTERFACES.md (tape.py section),
contracts/refs.md and contracts/append_envelope.md, lifting the throwaway PRE-spikes
evidence/stage0/s1_spike.py (failure-is-state + 2 refs + replay) and s2_spike.py
(single active sovereign writer + explicit handoff) onto the real Tape class.

Run: PYTHONPATH=src python3 -m unittest tests.test_tape -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from turingos.tape import Tape
from turingos.errors import (
    RejectedAppend,
    GuardReject,
    AsciiKeyViolation,
    FloatViolation,
)


# Deterministic git identity for any plumbing this test drives directly.
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


class TapeTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / parallel cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_tape_t_")
        self.repo = os.path.join(self.root, "micro_tape")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _boot(self, writer_id="W1"):
        tape = Tape.init(self.repo, writer_id)
        ev = tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)
        return tape, ev


class TestObjectFormat(TapeTestBase):
    def test_object_format_is_sha256(self):
        tape = Tape.init(self.repo, "W1")
        self.assertEqual(tape.object_format(), "sha256")

    def test_empty_tape_has_no_heads(self):
        tape = Tape.init(self.repo, "W1")
        self.assertIsNone(tape.tape_tip())
        self.assertIsNone(tape.accepted_head())


class TestAdvanceAndFailureIsState(TapeTestBase):
    def test_bootstrap_advances_both_heads(self):
        # S-1 c1: a SOVEREIGN_ACCEPT (ADVANCE) with predicate PASS advances accepted_head AND tape_tip.
        tape, ev = self._boot()
        self.assertTrue(ev.startswith("mu:"))
        self.assertEqual(len("mu:") + 64, len(ev))  # mu: + 64-hex sha256 oid
        self.assertEqual(tape.tape_tip(), tape.accepted_head())
        self.assertIsNotNone(tape.tape_tip())

    def test_failure_node_advances_tape_tip_only(self):
        # S-1 c2: FailureNode (OBSERVATION/PRESERVE) advances tape_tip but NOT accepted_head.
        tape, _ = self._boot()
        acc_before = tape.accepted_head()
        tip_before = tape.tape_tip()
        tape.append("FailureNode", {"failure_class": "test_fail"})
        self.assertNotEqual(tape.tape_tip(), tip_before)   # tape_tip moved
        self.assertEqual(tape.accepted_head(), acc_before)  # accepted_head did NOT move

    def test_candidate_accepted_advances_accepted_head(self):
        # S-1 c3: CandidateAccepted (ADVANCE) with predicate PASS -> accepted_head == tape_tip.
        tape, _ = self._boot()
        tape.append("FailureNode", {"failure_class": "test_fail"})
        ev = tape.append("CandidateAccepted", {"kind": "accept"}, predicate_pass=True)
        self.assertEqual(tape.accepted_head(), tape.tape_tip())
        self.assertEqual("mu:" + tape.accepted_head(), ev)


class TestAdvanceRequiresPredicatePass(TapeTestBase):
    def test_advance_without_predicate_pass_is_rejected(self):
        # tape-canonical invariant: an ADVANCE event MUST carry predicate_pass=True or be rejected
        # (a failed accept is a FailureNode, never a non-advancing SOVEREIGN_ACCEPT). No commit lands.
        tape, _ = self._boot()
        tip_before = tape.tape_tip()
        with self.assertRaises(RejectedAppend):
            tape.append("CandidateAccepted", {"kind": "accept"})  # predicate_pass omitted (None)
        self.assertEqual(tape.tape_tip(), tip_before)  # no commit on a rejected append

    def test_advance_with_predicate_false_is_rejected(self):
        tape, _ = self._boot()
        with self.assertRaises(RejectedAppend):
            tape.append("CandidateAccepted", {"kind": "accept"}, predicate_pass=False)

    def test_preserve_event_needs_no_predicate_pass(self):
        # A PRESERVE event (FailureNode) is fine with predicate_pass=None.
        tape, _ = self._boot()
        ev = tape.append("FailureNode", {"failure_class": "test_fail"})
        self.assertTrue(ev.startswith("mu:"))


class TestClosedWorld(TapeTestBase):
    def test_unknown_event_is_rejected(self):
        tape, _ = self._boot()
        tip_before = tape.tape_tip()
        with self.assertRaises(RejectedAppend):
            tape.append("NotARealEvent", {"x": 1})
        self.assertEqual(tape.tape_tip(), tip_before)


class TestSingleWriterGuard(TapeTestBase):
    def test_first_bootstrap_establishes_writer(self):
        # S-2: the FIRST SystemBootstrapped establishes the current sovereign writer.
        tape, _ = self._boot("W1")
        self.assertEqual(tape.current_writer(), "W1")

    def test_correct_writer_ff_append_admitted(self):
        tape, _ = self._boot("W1")
        tip0 = tape.tape_tip()
        tape.append("FailureNode", {"n": 1}, writer_id="W1")
        self.assertNotEqual(tape.tape_tip(), tip0)

    def test_wrong_writer_is_guard_rejected(self):
        # S-2: a non-current writer's append is rejected BY THE GUARD (raises), not by convention.
        tape, _ = self._boot("W1")
        tip_before = tape.tape_tip()
        with self.assertRaises(GuardReject):
            tape.append("FailureNode", {"n": 1}, writer_id="W2")
        self.assertEqual(tape.tape_tip(), tip_before)  # rejected before any commit

    def test_default_writer_id_is_self_writer_id(self):
        # When writer_id is omitted, the Tape's own writer_id is used (and must match current writer).
        tape, _ = self._boot("W1")
        tip0 = tape.tape_tip()
        tape.append("FailureNode", {"n": 9})  # writer_id omitted -> self.writer_id == W1
        self.assertNotEqual(tape.tape_tip(), tip0)


class TestNonFastForwardGuard(TapeTestBase):
    def test_stale_parent_is_guard_rejected(self):
        # S-2: a simulated non-FF / stale-parent append (external mutation since we read tape_tip)
        # is rejected by the guard. The internal hook _expect_parent simulates the stale view.
        tape, _ = self._boot("W1")
        tip = tape.tape_tip()
        # advance the tip once so `tip` is now stale
        tape.append("FailureNode", {"n": 1})
        with self.assertRaises(GuardReject):
            tape.append("FailureNode", {"n": 2}, _expect_parent=tip)  # built on a stale parent


class TestHandoff(TapeTestBase):
    def test_handoff_changes_current_writer(self):
        # S-2: HandoffGenerated is a Tape event that changes who the guard admits.
        tape, _ = self._boot("W1")
        self.assertEqual(tape.current_writer(), "W1")
        tip_before = tape.tape_tip()
        ev = tape.handoff("W2")
        self.assertTrue(ev.startswith("mu:"))
        self.assertNotEqual(tape.tape_tip(), tip_before)  # handoff recorded on the tape
        self.assertEqual(tape.current_writer(), "W2")

    def test_handoff_does_not_advance_accepted_head(self):
        tape, _ = self._boot("W1")
        acc_before = tape.accepted_head()
        tape.handoff("W2")
        self.assertEqual(tape.accepted_head(), acc_before)  # PRESERVE event

    def test_new_writer_admitted_old_writer_rejected_after_handoff(self):
        tape, _ = self._boot("W1")
        tape.handoff("W2")
        # W2 (now current) is admitted
        tip0 = tape.tape_tip()
        tape.append("FailureNode", {"n": 1}, writer_id="W2")
        self.assertNotEqual(tape.tape_tip(), tip0)
        # W1 (no longer current) is rejected by the guard
        with self.assertRaises(GuardReject):
            tape.append("FailureNode", {"n": 2}, writer_id="W1")


class TestReadAndWalk(TapeTestBase):
    def test_read_event_round_trips(self):
        tape, ev = self._boot("W1")
        node = tape.read_event(ev)
        self.assertEqual(node["event_type"], "SystemBootstrapped")
        self.assertEqual(node["payload"], {"kind": "boot"})
        self.assertIn("envelope", node)
        self.assertEqual(node["envelope"]["event_schema_id"], "SystemBootstrapped")
        self.assertEqual(node["envelope"]["head_effect"], "ADVANCE")
        self.assertEqual(node["envelope"]["writer_id"], "W1")
        self.assertEqual(node["oid"], ev[len("mu:"):])
        self.assertIsInstance(node["parents"], list)
        self.assertEqual(node["parents"], [])  # genesis has no parent

    def test_envelope_payload_hash_matches_codec(self):
        from turingos import codec
        tape, _ = self._boot("W1")
        ev = tape.append("FailureNode", {"failure_class": "test_fail", "n": 7})
        node = tape.read_event(ev)
        self.assertEqual(
            node["envelope"]["payload_hash"],
            codec.content_digest({"failure_class": "test_fail", "n": 7}),
        )

    def test_walk_returns_genesis_to_tip_in_order(self):
        tape, _ = self._boot("W1")
        tape.append("FailureNode", {"n": 1})
        tape.append("CandidateAccepted", {"n": 2}, predicate_pass=True)
        events = tape.walk()
        self.assertEqual(
            [e["event_type"] for e in events],
            ["SystemBootstrapped", "FailureNode", "CandidateAccepted"],
        )
        # parents chain forward: each non-genesis event has exactly one parent
        self.assertEqual(events[0]["parents"], [])
        self.assertEqual(len(events[1]["parents"]), 1)


class TestExactlyTwoRefs(TapeTestBase):
    def test_only_two_turingos_refs_no_authorization_head(self):
        # S-1 c6: refs/turingos/ lists EXACTLY accepted_head + tape_tip, never authorization_head.
        tape, _ = self._boot("W1")
        tape.append("FailureNode", {"n": 1})
        tape.append("CandidateAccepted", {"n": 2}, predicate_pass=True)
        out = _git(self.repo, "for-each-ref", "refs/turingos/").strip().splitlines()
        refs = sorted(line.split()[-1] for line in out)
        self.assertEqual(
            refs, ["refs/turingos/accepted_head", "refs/turingos/tape_tip"]
        )
        self.assertNotIn("refs/turingos/authorization_head", refs)


class TestFastForwardConfig(TapeTestBase):
    def test_ff_and_delete_protection_configured(self):
        Tape.init(self.repo, "W1")
        self.assertEqual(
            _git(self.repo, "config", "receive.denyNonFastForwards").strip(), "true"
        )
        self.assertEqual(
            _git(self.repo, "config", "receive.denyDeletes").strip(), "true"
        )


class TestCodecGuardsOnAppendPath(TapeTestBase):
    """The append() path MUST enforce the turingos.jcs.v1 codec guards (no commit on violation).

    content_digest(payload) runs inside append() before any ref moves, so a float value or a
    non-ASCII load-bearing key is rejected (FloatViolation / AsciiKeyViolation) and the tape does
    not advance. This locks the wiring against regression (the digest could otherwise be computed
    on a relaxed codec). Both error classes are subclasses of TuringOSError, not of RejectedAppend.
    """

    def test_float_payload_value_is_rejected_no_commit(self):
        tape, _ = self._boot("W1")
        tip_before = tape.tape_tip()
        with self.assertRaises(FloatViolation):
            tape.append("FailureNode", {"n": 1.5})  # float value forbidden (non-deterministic)
        self.assertEqual(tape.tape_tip(), tip_before)  # rejected before any commit

    def test_non_ascii_key_payload_is_rejected_no_commit(self):
        tape, _ = self._boot("W1")
        tip_before = tape.tape_tip()
        with self.assertRaises(AsciiKeyViolation):
            tape.append("FailureNode", {"é": 1})  # non-ASCII load-bearing key
        self.assertEqual(tape.tape_tip(), tip_before)  # rejected before any commit


class TestAcceptedHeadAncestorGuard(TapeTestBase):
    """append_envelope guard #6: accepted_head_before MUST be an ancestor of the live tape_tip.

    The public API always preserves this invariant, so to exercise the guard we corrupt the
    accepted_head ref out-of-band (point it at an unrelated/orphan commit) and confirm the next
    append is GuardReject-ed before any commit lands. This is the load-bearing audit/consistency
    invariant named in append_envelope.md, refs.md and the INTERFACES tape docstring.
    """

    def test_non_ancestor_accepted_head_is_guard_rejected(self):
        tape, _ = self._boot("W1")
        # Fabricate an UNRELATED commit (orphan history) that is NOT on the tape's chain.
        orphan_repo = os.path.join(self.root, "orphan")
        os.makedirs(orphan_repo, exist_ok=True)
        _git(orphan_repo, "init", "--object-format=sha256")
        with open(os.path.join(orphan_repo, "x"), "w", encoding="utf-8") as fh:
            fh.write("unrelated")
        _git(orphan_repo, "add", "x")
        _git(orphan_repo, "commit", "--no-gpg-sign", "-m", "orphan")
        orphan_oid = _git(orphan_repo, "rev-parse", "HEAD").strip()
        # Bring that object into the tape repo, then point accepted_head at it (divergent state).
        bundle = os.path.join(self.root, "orphan.bundle")
        _git(orphan_repo, "bundle", "create", bundle, "HEAD")
        _git(self.repo, "fetch", bundle, f"{orphan_oid}:refs/orphan_import")
        _git(self.repo, "update-ref", "refs/turingos/accepted_head", orphan_oid)
        self.assertEqual(tape.accepted_head(), orphan_oid)  # corrupted accepted state in place

        tip_before = tape.tape_tip()
        with self.assertRaises(GuardReject):
            tape.append("FailureNode", {"n": 1})  # guard #6 must fire: orphan is not an ancestor
        self.assertEqual(tape.tape_tip(), tip_before)  # rejected before any commit

    def test_normal_append_satisfies_ancestor_guard(self):
        # Sanity: in the normal flow accepted_head_before is always an ancestor of tape_tip,
        # so guard #6 admits the append (regression sentinel for an over-strict guard).
        tape, _ = self._boot("W1")
        ev = tape.append("FailureNode", {"n": 1})
        self.assertTrue(ev.startswith("mu:"))
        node = tape.read_event(ev)
        # the recorded accepted_head_before equals the boot accept (an ancestor of the new tip)
        self.assertEqual(node["envelope"]["head_effect"], "PRESERVE")


if __name__ == "__main__":
    unittest.main()

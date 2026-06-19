"""Contract tests for turingos.explore (stdlib unittest, NOT pytest).

Captures the frozen explore-module contract from contracts/INTERFACES.md (explore.py
section) + the 18-event registry (contracts/event_registry.md):

    def register_exploration(tape, exploration) -> str                       # local handle (NO tape event)
    def archive_exploration(tape, exploration_id, *, predicate_pass) -> str   # ExplorationArchived (SOVEREIGN_ACCEPT)
    def promote_exploration(tape, exploration_id, *, predicate_pass) -> str    # ExplorationPromoted (SOVEREIGN_ACCEPT)
    def inject_human_steer(tape, message) -> str                              # HumanSteerInjected (PROPOSAL)

Load-bearing invariants exercised here (CLAUDE.md / event_registry.md):
  * ExplorationArchived / ExplorationPromoted are SOVEREIGN_ACCEPT (head_effect=ADVANCE):
    they advance BOTH accepted_head AND tape_tip, and ONLY on a deterministic Predicate PASS
    (predicate_pass=True), else RejectedAppend [Art. I.1]. A failed disposition is never a
    non-advancing SOVEREIGN_ACCEPT.
  * HumanSteerInjected is a PROPOSAL (head_effect=PRESERVE): a typed steer/authorization event
    that advances tape_tip ONLY, never accepted_head.
  * register_exploration is a LOCAL handle: it returns a deterministic exploration_id (a hash)
    and appends NOTHING to the Tape — neither ref moves. The sovereign disposition events
    (archive/promote) are the recorded Tape state.
  * A rejected disposition lands NO commit (the tape is unchanged).

Run: PYTHONPATH=src python3 -m unittest tests.test_explore -v
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from turingos import explore
from turingos.tape import Tape
from turingos.errors import RejectedAppend


class ExploreTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / parallel cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_explore_t_")
        self.repo = os.path.join(self.root, "micro_tape")
        # Bootstrap a tape with a single sovereign writer (genesis SOVEREIGN_ACCEPT).
        self.tape = Tape.init(self.repo, "W1")
        self.tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    @staticmethod
    def _exploration(**overrides) -> dict:
        ex = {"branch": "exp/spike-a", "atom_id": "A1", "note": "tried approach a"}
        ex.update(overrides)
        return ex


# --- register_exploration: a LOCAL handle, no Tape event ---------------------
class TestRegisterExploration(ExploreTestBase):
    def test_returns_string_id(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        self.assertIsInstance(eid, str)
        self.assertTrue(eid)

    def test_does_not_append_to_tape(self):
        # register is a local handle: NEITHER ref moves (no sovereign disposition yet).
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        explore.register_exploration(self.tape, self._exploration())
        self.assertEqual(self.tape.tape_tip(), tip_before)
        self.assertEqual(self.tape.accepted_head(), acc_before)

    def test_id_is_deterministic(self):
        # Same exploration content => same id (content hash), so a disposition can reference it.
        ex = self._exploration()
        eid1 = explore.register_exploration(self.tape, ex)
        eid2 = explore.register_exploration(self.tape, dict(ex))
        self.assertEqual(eid1, eid2)

    def test_distinct_explorations_get_distinct_ids(self):
        eid1 = explore.register_exploration(self.tape, self._exploration(branch="exp/a"))
        eid2 = explore.register_exploration(self.tape, self._exploration(branch="exp/b"))
        self.assertNotEqual(eid1, eid2)

    def test_non_dict_rejected(self):
        with self.assertRaises((RejectedAppend, TypeError, ValueError)):
            explore.register_exploration(self.tape, "not-a-dict")


# --- archive_exploration: ExplorationArchived (SOVEREIGN_ACCEPT / ADVANCE) ---
class TestArchiveExploration(ExploreTestBase):
    def test_returns_event_id(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        ev = explore.archive_exploration(self.tape, eid, predicate_pass=True)
        self.assertIsInstance(ev, str)
        self.assertTrue(ev.startswith("mu:"))
        self.assertEqual(len("mu:") + 64, len(ev))  # mu: + 64-hex sha256 oid

    def test_advances_accepted_head_and_tape_tip(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        ev = explore.archive_exploration(self.tape, eid, predicate_pass=True)
        # SOVEREIGN_ACCEPT advances BOTH refs to the new commit.
        self.assertNotEqual(self.tape.tape_tip(), tip_before)
        self.assertNotEqual(self.tape.accepted_head(), acc_before)
        self.assertEqual(self.tape.tape_tip(), ev[len("mu:"):])
        self.assertEqual(self.tape.accepted_head(), ev[len("mu:"):])
        self.assertEqual(self.tape.tape_tip(), self.tape.accepted_head())

    def test_records_correct_event_type_and_disposition(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        ev = explore.archive_exploration(self.tape, eid, predicate_pass=True)
        node = self.tape.read_event(ev)
        self.assertEqual(node["event_type"], "ExplorationArchived")
        self.assertEqual(node["payload"]["disposition"], "archived")
        self.assertEqual(node["payload"]["exploration_id"], eid)

    def test_without_predicate_pass_raises(self):
        # advance requires a deterministic Predicate PASS; no PASS => RejectedAppend.
        eid = explore.register_exploration(self.tape, self._exploration())
        with self.assertRaises(RejectedAppend):
            explore.archive_exploration(self.tape, eid, predicate_pass=False)

    def test_failed_disposition_lands_no_commit(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        with self.assertRaises(RejectedAppend):
            explore.archive_exploration(self.tape, eid, predicate_pass=False)
        self.assertEqual(self.tape.tape_tip(), tip_before)
        self.assertEqual(self.tape.accepted_head(), acc_before)


# --- promote_exploration: ExplorationPromoted (SOVEREIGN_ACCEPT / ADVANCE) ---
class TestPromoteExploration(ExploreTestBase):
    def test_returns_event_id(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        ev = explore.promote_exploration(self.tape, eid, predicate_pass=True)
        self.assertTrue(ev.startswith("mu:"))
        self.assertEqual(len("mu:") + 64, len(ev))

    def test_advances_accepted_head_and_tape_tip(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        ev = explore.promote_exploration(self.tape, eid, predicate_pass=True)
        self.assertNotEqual(self.tape.tape_tip(), tip_before)
        self.assertNotEqual(self.tape.accepted_head(), acc_before)
        self.assertEqual(self.tape.accepted_head(), ev[len("mu:"):])
        self.assertEqual(self.tape.tape_tip(), self.tape.accepted_head())

    def test_records_correct_event_type_and_disposition(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        ev = explore.promote_exploration(self.tape, eid, predicate_pass=True)
        node = self.tape.read_event(ev)
        self.assertEqual(node["event_type"], "ExplorationPromoted")
        self.assertEqual(node["payload"]["disposition"], "promoted")
        self.assertEqual(node["payload"]["exploration_id"], eid)

    def test_without_predicate_pass_raises(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        with self.assertRaises(RejectedAppend):
            explore.promote_exploration(self.tape, eid, predicate_pass=False)

    def test_failed_disposition_lands_no_commit(self):
        eid = explore.register_exploration(self.tape, self._exploration())
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        with self.assertRaises(RejectedAppend):
            explore.promote_exploration(self.tape, eid, predicate_pass=False)
        self.assertEqual(self.tape.tape_tip(), tip_before)
        self.assertEqual(self.tape.accepted_head(), acc_before)


# --- inject_human_steer: HumanSteerInjected (PROPOSAL / PRESERVE) ------------
class TestInjectHumanSteer(ExploreTestBase):
    @staticmethod
    def _message(**overrides) -> dict:
        msg = {"text": "prefer approach b", "from": "human"}
        msg.update(overrides)
        return msg

    def test_returns_event_id(self):
        ev = explore.inject_human_steer(self.tape, self._message())
        self.assertTrue(ev.startswith("mu:"))
        self.assertEqual(len("mu:") + 64, len(ev))

    def test_advances_tape_tip_not_accepted_head(self):
        # HumanSteerInjected is a PROPOSAL (PRESERVE): tape_tip moves, accepted_head frozen.
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        ev = explore.inject_human_steer(self.tape, self._message())
        self.assertNotEqual(self.tape.tape_tip(), tip_before)  # tape_tip moved
        self.assertEqual(self.tape.tape_tip(), ev[len("mu:"):])  # tip == steer event oid
        self.assertEqual(self.tape.accepted_head(), acc_before)  # accepted_head DID NOT move

    def test_records_correct_event_type(self):
        ev = explore.inject_human_steer(self.tape, self._message())
        node = self.tape.read_event(ev)
        self.assertEqual(node["event_type"], "HumanSteerInjected")

    def test_message_retrievable_byte_for_byte(self):
        msg = self._message(text="steer the loop", priority=1)
        ev = explore.inject_human_steer(self.tape, msg)
        node = self.tape.read_event(ev)
        self.assertEqual(node["payload"], msg)

    def test_steer_does_not_require_predicate_pass(self):
        # A PROPOSAL never needs a predicate PASS to land (it does not advance accepted_head).
        ev = explore.inject_human_steer(self.tape, self._message())
        self.assertTrue(ev.startswith("mu:"))


# --- end-to-end: a register -> steer -> dispose sequence on one tape ---------
class TestExploreSequence(ExploreTestBase):
    def test_steer_then_promote_only_promote_advances_accepted_head(self):
        acc_genesis = self.tape.accepted_head()
        eid = explore.register_exploration(self.tape, self._exploration())
        # a PROPOSAL steer: accepted_head must stay put.
        explore.inject_human_steer(self.tape, {"text": "go with it"})
        self.assertEqual(self.tape.accepted_head(), acc_genesis)
        # the sovereign promotion: accepted_head advances past genesis.
        ev = explore.promote_exploration(self.tape, eid, predicate_pass=True)
        self.assertEqual(self.tape.accepted_head(), ev[len("mu:"):])
        self.assertNotEqual(self.tape.accepted_head(), acc_genesis)


if __name__ == "__main__":
    unittest.main()

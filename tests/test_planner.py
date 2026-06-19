"""Contract tests for turingos.planner.expand_atoms (stdlib unittest, NOT pytest).

Captures the frozen planner seam (contracts/INTERFACES.md planner.py section):

    def expand_atoms(tape: "Tape", module_id: str) -> list[dict]
        # progressive; emits AtomProposed (active module only)

PROGRESSIVE elaboration (Art. III progressive disclosure): expand ONLY the named/active
module into a SMALL handful of atoms (NOT the whole project). Each atom is emitted as an
AtomProposed event (registry #5, class PROPOSAL, head_effect PRESERVE) so `tape_tip`
advances once per atom and `accepted_head` NEVER moves. Each returned atom dict carries
{atom_id, module_id, intent, allowed_files:[...], acceptance_commands:[...]} and is scoped
to the requested module_id.

Run: PYTHONPATH=src python3 -m unittest tests.test_planner -v
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from turingos import codec
from turingos.tape import Tape
from turingos.planner import expand_atoms
from turingos.errors import RejectedAppend


class PlannerTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_planner_t_")
        self.repo = os.path.join(self.root, "micro_tape")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _boot(self, writer_id="W1"):
        """A booted tape (SystemBootstrapped advances both heads)."""
        tape = Tape.init(self.repo, writer_id)
        tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)
        return tape


class TestExpandReturnsAtomList(PlannerTestBase):
    def test_returns_nonempty_list_of_atom_dicts(self):
        tape = self._boot()
        atoms = expand_atoms(tape, "M1")
        self.assertIsInstance(atoms, list)
        self.assertGreaterEqual(len(atoms), 1)  # a few atoms, at least one
        for atom in atoms:
            self.assertIsInstance(atom, dict)

    def test_progressive_small_not_whole_project(self):
        # Progressive disclosure: a SMALL handful, never an unbounded project-wide dump.
        tape = self._boot()
        atoms = expand_atoms(tape, "M1")
        self.assertLessEqual(len(atoms), 8)

    def test_each_atom_has_required_fields(self):
        tape = self._boot()
        atoms = expand_atoms(tape, "M1")
        for atom in atoms:
            self.assertIn("atom_id", atom)
            self.assertIn("module_id", atom)
            self.assertIn("intent", atom)
            self.assertIn("allowed_files", atom)
            self.assertIn("acceptance_commands", atom)

    def test_allowed_files_and_acceptance_commands_are_nonempty_lists(self):
        tape = self._boot()
        atoms = expand_atoms(tape, "M1")
        for atom in atoms:
            self.assertIsInstance(atom["allowed_files"], list)
            self.assertIsInstance(atom["acceptance_commands"], list)
            self.assertGreaterEqual(len(atom["allowed_files"]), 1)
            self.assertGreaterEqual(len(atom["acceptance_commands"]), 1)

    def test_atom_ids_are_unique(self):
        tape = self._boot()
        atoms = expand_atoms(tape, "M1")
        ids = [a["atom_id"] for a in atoms]
        self.assertEqual(len(ids), len(set(ids)))


class TestScopedToModule(PlannerTestBase):
    def test_all_atoms_scoped_to_requested_module(self):
        tape = self._boot()
        atoms = expand_atoms(tape, "M2")
        for atom in atoms:
            self.assertEqual(atom["module_id"], "M2")

    def test_calling_one_module_does_not_expand_a_different_module(self):
        # Asking for M1 must produce ONLY M1 atoms — never atoms for some other module.
        tape = self._boot()
        atoms = expand_atoms(tape, "M1")
        other = [a for a in atoms if a["module_id"] != "M1"]
        self.assertEqual(other, [])

    def test_different_module_ids_yield_their_own_scope(self):
        tape = self._boot()
        m1 = expand_atoms(tape, "M1")
        m3 = expand_atoms(tape, "M3")
        self.assertTrue(all(a["module_id"] == "M1" for a in m1))
        self.assertTrue(all(a["module_id"] == "M3" for a in m3))


class TestEmitsAtomProposedEvents(PlannerTestBase):
    def test_emits_one_atomproposed_per_atom(self):
        tape = self._boot()
        before = tape.walk()
        atoms = expand_atoms(tape, "M1")
        after = tape.walk()
        new_events = after[len(before):]
        self.assertEqual(len(new_events), len(atoms))
        for ev in new_events:
            self.assertEqual(ev["event_type"], "AtomProposed")

    def test_tape_tip_advances_per_atom(self):
        # PROPOSAL: tape_tip advances once per emitted atom.
        tape = self._boot()
        tip_before = tape.tape_tip()
        atoms = expand_atoms(tape, "M1")
        self.assertNotEqual(tape.tape_tip(), tip_before)
        # number of new commits == number of atoms (genesis boot event + one per atom)
        self.assertEqual(len(tape.walk()), 1 + len(atoms))

    def test_accepted_head_does_not_move(self):
        # AtomProposed is PROPOSAL/PRESERVE: accepted_head MUST NOT advance.
        tape = self._boot()
        acc_before = tape.accepted_head()
        expand_atoms(tape, "M1")
        self.assertEqual(tape.accepted_head(), acc_before)

    def test_atomproposed_payload_is_the_atom_dict(self):
        tape = self._boot()
        atoms = expand_atoms(tape, "M1")
        events = [e for e in tape.walk() if e["event_type"] == "AtomProposed"]
        self.assertEqual(len(events), len(atoms))
        for ev, atom in zip(events, atoms):
            self.assertEqual(ev["payload"], atom)
            # the recorded payload_hash matches the codec digest of the atom
            self.assertEqual(
                ev["envelope"]["payload_hash"], codec.content_digest(atom)
            )

    def test_emitted_events_are_preserve_class(self):
        tape = self._boot()
        expand_atoms(tape, "M1")
        for ev in [e for e in tape.walk() if e["event_type"] == "AtomProposed"]:
            self.assertEqual(ev["envelope"]["head_effect"], "PRESERVE")


class TestDeterminismAndReduce(PlannerTestBase):
    def test_deterministic_atom_ids_for_same_module(self):
        # Same module on two fresh tapes yields the same atom_ids (deterministic plan).
        tape1 = self._boot()
        a1 = expand_atoms(tape1, "M1")
        root2 = tempfile.mkdtemp(prefix="tos_planner_t_")
        self.addCleanup(shutil.rmtree, root2, True)
        tape2 = Tape.init(os.path.join(root2, "micro_tape"), "W1")
        tape2.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)
        a2 = expand_atoms(tape2, "M1")
        self.assertEqual([a["atom_id"] for a in a1], [a["atom_id"] for a in a2])

    def test_active_atom_reduces_to_last_proposed(self):
        # reduce_qt should fold the latest AtomProposed into active_atom (integration sanity).
        from turingos.reduce import reduce_qt
        tape = self._boot()
        atoms = expand_atoms(tape, "M1")
        q = reduce_qt(tape)
        self.assertEqual(q["active_atom"], atoms[-1])

    def test_payload_has_no_floats_and_ascii_keys(self):
        # The codec guard on the append path would reject otherwise; assert it does NOT raise.
        tape = self._boot()
        try:
            expand_atoms(tape, "M1")
        except RejectedAppend as exc:  # pragma: no cover - guard regression sentinel
            self.fail(f"expand_atoms produced a codec-rejected payload: {exc}")


if __name__ == "__main__":
    unittest.main()

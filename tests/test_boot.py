"""Contract tests for turingos.boot (stdlib unittest, NOT pytest).

These capture the frozen boot contract from contracts/INTERFACES.md (boot.py section)
and the IMPLEMENTER spec:

    def boot(tape, project_spec) -> dict        # {bootstrapped, adopted} event_ids
    def accept_goalstate(tape, goalstate) -> str # GoalStateAccepted (SOVEREIGN_ACCEPT)
    def accept_module_plan(tape, module_plan) -> str # ModulePlanAccepted (SOVEREIGN_ACCEPT)

Load-bearing facts being asserted:
  * boot emits exactly TWO events (SystemBootstrapped then ProjectAdopted), both
    SOVEREIGN_ACCEPT/ADVANCE with predicate_pass=True, so accepted_head advances and
    ends equal to tape_tip after a clean boot.
  * The SystemBootstrapped payload carries writer_id (establishes the single-writer guard),
    so subsequent appends from the same writer admit.
  * accept_goalstate structurally requires a 'goal' key; a missing 'goal' raises before any
    commit lands (no ref moves). On success it advances accepted_head.
  * accept_module_plan advances accepted_head.
  * After boot + goalstate + module_plan, reduce_qt(tape)['active_goal'] and ['active_module']
    are populated from the accepted payloads (derived fold).
  * SOVEREIGN_ACCEPT semantics: each accept advances accepted_head AND tape_tip together.

Each test uses a UNIQUE /tmp/tos_boot_t scratch dir so parallel agents never collide.

Run: PYTHONPATH=src python3 -m unittest tests.test_boot -v
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from turingos.tape import Tape
from turingos import boot as boot_mod
from turingos import reduce as reduce_mod
from turingos.errors import SchemaInvalid, TuringOSError


# A representative Project Spec (the Boot INPUT [Art. IV]).
_PROJECT_SPEC = {
    "project_id": "P1",
    "name": "turingos-dogfood",
    "writer_id": "W1",
}


class BootTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_boot_t_")
        self.repo = os.path.join(self.root, "micro_tape")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _fresh_tape(self, writer_id="W1"):
        return Tape.init(self.repo, writer_id)


class TestBoot(BootTestBase):
    def test_boot_returns_two_event_ids(self):
        tape = self._fresh_tape()
        result = boot_mod.boot(tape, _PROJECT_SPEC)
        self.assertIsInstance(result, dict)
        self.assertIn("bootstrapped", result)
        self.assertIn("adopted", result)
        self.assertTrue(result["bootstrapped"].startswith("mu:"))
        self.assertTrue(result["adopted"].startswith("mu:"))
        self.assertNotEqual(result["bootstrapped"], result["adopted"])

    def test_boot_emits_exactly_two_events(self):
        tape = self._fresh_tape()
        boot_mod.boot(tape, _PROJECT_SPEC)
        events = tape.walk()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_type"], "SystemBootstrapped")
        self.assertEqual(events[1]["event_type"], "ProjectAdopted")

    def test_boot_advances_accepted_head_to_tape_tip(self):
        # Both boot events are SOVEREIGN_ACCEPT/ADVANCE with predicate PASS, so after a clean
        # boot accepted_head == tape_tip (both at ProjectAdopted).
        tape = self._fresh_tape()
        self.assertIsNone(tape.accepted_head())
        boot_mod.boot(tape, _PROJECT_SPEC)
        self.assertIsNotNone(tape.accepted_head())
        self.assertEqual(tape.accepted_head(), tape.tape_tip())

    def test_bootstrapped_payload_carries_writer_id(self):
        # The SystemBootstrapped payload MUST carry writer_id so the single-writer guard is set.
        tape = self._fresh_tape()
        result = boot_mod.boot(tape, _PROJECT_SPEC)
        ev = tape.read_event(result["bootstrapped"])
        self.assertEqual(ev["event_type"], "SystemBootstrapped")
        self.assertIn("writer_id", ev["payload"])
        self.assertEqual(ev["payload"]["writer_id"], "W1")
        # The envelope writer_id (what the guard reads) matches too.
        self.assertEqual(ev["envelope"]["writer_id"], "W1")

    def test_bootstrap_establishes_current_writer(self):
        # After boot, the guard admits the established writer; current_writer == W1.
        tape = self._fresh_tape()
        boot_mod.boot(tape, _PROJECT_SPEC)
        self.assertEqual(tape.current_writer(), "W1")

    def test_project_spec_carried_in_adopted(self):
        tape = self._fresh_tape()
        result = boot_mod.boot(tape, _PROJECT_SPEC)
        ev = tape.read_event(result["adopted"])
        self.assertEqual(ev["event_type"], "ProjectAdopted")
        # The Project Spec is the Boot INPUT — ProjectAdopted records it.
        self.assertIsInstance(ev["payload"], dict)


class TestAcceptGoalstate(BootTestBase):
    def _booted(self):
        tape = self._fresh_tape()
        boot_mod.boot(tape, _PROJECT_SPEC)
        return tape

    def test_accept_goalstate_advances_accepted_head(self):
        tape = self._booted()
        acc_before = tape.accepted_head()
        ev = boot_mod.accept_goalstate(tape, {"goal": "ship the loop", "goal_id": "G1"})
        self.assertTrue(ev.startswith("mu:"))
        self.assertNotEqual(tape.accepted_head(), acc_before)  # advanced
        self.assertEqual(tape.accepted_head(), tape.tape_tip())

    def test_accept_goalstate_emits_goalstateaccepted(self):
        tape = self._booted()
        ev = boot_mod.accept_goalstate(tape, {"goal": "ship the loop"})
        node = tape.read_event(ev)
        self.assertEqual(node["event_type"], "GoalStateAccepted")
        self.assertEqual(node["payload"]["goal"], "ship the loop")

    def test_accept_goalstate_requires_goal_key(self):
        tape = self._booted()
        tip_before = tape.tape_tip()
        acc_before = tape.accepted_head()
        with self.assertRaises((SchemaInvalid, TuringOSError, ValueError)):
            boot_mod.accept_goalstate(tape, {"not_goal": "oops"})
        # No commit landed: neither ref moved.
        self.assertEqual(tape.tape_tip(), tip_before)
        self.assertEqual(tape.accepted_head(), acc_before)

    def test_accept_goalstate_non_dict_rejected(self):
        tape = self._booted()
        with self.assertRaises((SchemaInvalid, TuringOSError, ValueError, TypeError)):
            boot_mod.accept_goalstate(tape, ["goal"])


class TestAcceptModulePlan(BootTestBase):
    def _booted_with_goal(self):
        tape = self._fresh_tape()
        boot_mod.boot(tape, _PROJECT_SPEC)
        boot_mod.accept_goalstate(tape, {"goal": "ship the loop", "goal_id": "G1"})
        return tape

    def test_accept_module_plan_advances_accepted_head(self):
        tape = self._booted_with_goal()
        acc_before = tape.accepted_head()
        ev = boot_mod.accept_module_plan(
            tape, {"module_id": "M3", "title": "predicate kernel"}
        )
        self.assertTrue(ev.startswith("mu:"))
        self.assertNotEqual(tape.accepted_head(), acc_before)
        self.assertEqual(tape.accepted_head(), tape.tape_tip())

    def test_accept_module_plan_emits_moduleplanaccepted(self):
        tape = self._booted_with_goal()
        ev = boot_mod.accept_module_plan(tape, {"module_id": "M3"})
        node = tape.read_event(ev)
        self.assertEqual(node["event_type"], "ModulePlanAccepted")
        self.assertEqual(node["payload"]["module_id"], "M3")


class TestReduceAfterBootChain(BootTestBase):
    def test_active_goal_and_module_populated(self):
        # The end-to-end derived-fold check: after boot + goalstate + module_plan,
        # reduce_qt sees active_goal and active_module.
        tape = self._fresh_tape()
        boot_mod.boot(tape, _PROJECT_SPEC)
        boot_mod.accept_goalstate(tape, {"goal": "ship the loop", "goal_id": "G1"})
        boot_mod.accept_module_plan(
            tape, {"module_id": "M3", "title": "predicate kernel"}
        )

        q = reduce_mod.reduce_qt(tape)
        self.assertIsNotNone(q["active_goal"])
        self.assertEqual(q["active_goal"]["goal"], "ship the loop")
        self.assertIsNotNone(q["active_module"])
        self.assertEqual(q["active_module"]["module_id"], "M3")

    def test_boot_only_leaves_goal_and_module_none(self):
        tape = self._fresh_tape()
        boot_mod.boot(tape, _PROJECT_SPEC)
        q = reduce_mod.reduce_qt(tape)
        self.assertIsNone(q["active_goal"])
        self.assertIsNone(q["active_module"])


if __name__ == "__main__":
    unittest.main()

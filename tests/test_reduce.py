"""Contract tests for turingos.reduce (stdlib unittest, NOT pytest).

These capture the frozen reduce contract from contracts/INTERFACES.md (reduce.py section)
and CLAUDE.md's load-bearing invariants:

  * reduce_qt(tape) -> q_t  — a DERIVED fold of tape.walk() into
        {active_goal, active_module, active_atom, current_policy, pending_decision, retry_state}
    Deterministic: same tape => same q_t (binding wording fix #4: WorkGraph/q_t are derived).
  * derive_workgraph(q_t, tape, macro_obs) -> {nodes, edges, accepted_head, tape_tip}
    DERIVED PROJECTION ONLY — never written back to the tape. Deterministic; MUST NOT mutate
    the tape (conservation: tape_tip is unchanged after derive_workgraph).

A small real Tape is built directly via Tape.append (boot + goal + module + atom events),
since boot.py / planner.py are not yet implemented. Each test uses a UNIQUE tmp dir so
parallel agents never collide.

Run: PYTHONPATH=src python3 -m unittest tests.test_reduce -v
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from turingos.tape import Tape
from turingos import reduce as reduce_mod


class ReduceTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_reduce_t_")
        self.repo = os.path.join(self.root, "micro_tape")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _boot(self, writer_id="W1"):
        tape = Tape.init(self.repo, writer_id)
        tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)
        return tape

    def _full_tape(self, writer_id="W1"):
        """boot + goal + module + atom — the canonical minimal q_t-populating tape."""
        tape = self._boot(writer_id)
        tape.append(
            "GoalStateAccepted",
            {"goal_id": "G1", "title": "ship the loop"},
            predicate_pass=True,
        )
        tape.append(
            "ModulePlanAccepted",
            {"module_id": "M3", "title": "predicate kernel"},
            predicate_pass=True,
        )
        tape.append("AtomProposed", {"atom_id": "A1", "module_id": "M3"})
        return tape


class TestReduceQtShape(ReduceTestBase):
    def test_empty_tape_yields_all_none_keys(self):
        # An empty tape (genesis only does not exist) reduces to the full key set, all None.
        tape = Tape.init(self.repo, "W1")
        q = reduce_mod.reduce_qt(tape)
        self.assertEqual(
            set(q.keys()),
            {
                "active_goal",
                "active_module",
                "active_atom",
                "current_policy",
                "pending_decision",
                "retry_state",
            },
        )
        self.assertIsNone(q["active_goal"])
        self.assertIsNone(q["active_module"])
        self.assertIsNone(q["active_atom"])
        self.assertIsNone(q["pending_decision"])

    def test_boot_only_has_no_goal_module_atom(self):
        tape = self._boot()
        q = reduce_mod.reduce_qt(tape)
        self.assertIsNone(q["active_goal"])
        self.assertIsNone(q["active_module"])
        self.assertIsNone(q["active_atom"])


class TestReduceQtPopulation(ReduceTestBase):
    def test_full_tape_populates_goal_module_atom(self):
        tape = self._full_tape()
        q = reduce_mod.reduce_qt(tape)
        self.assertIsNotNone(q["active_goal"])
        self.assertIsNotNone(q["active_module"])
        self.assertIsNotNone(q["active_atom"])
        self.assertEqual(q["active_goal"]["goal_id"], "G1")
        self.assertEqual(q["active_module"]["module_id"], "M3")
        self.assertEqual(q["active_atom"]["atom_id"], "A1")

    def test_active_goal_is_latest_goalstate_payload(self):
        # active_goal <- latest GoalStateAccepted payload (the LAST one wins).
        tape = self._boot()
        tape.append("GoalStateAccepted", {"goal_id": "G1"}, predicate_pass=True)
        tape.append("GoalStateAccepted", {"goal_id": "G2"}, predicate_pass=True)
        q = reduce_mod.reduce_qt(tape)
        self.assertEqual(q["active_goal"]["goal_id"], "G2")

    def test_active_module_is_latest_moduleplan_payload(self):
        tape = self._boot()
        tape.append("GoalStateAccepted", {"goal_id": "G1"}, predicate_pass=True)
        tape.append("ModulePlanAccepted", {"module_id": "M0"}, predicate_pass=True)
        tape.append("ModulePlanAccepted", {"module_id": "M1"}, predicate_pass=True)
        q = reduce_mod.reduce_qt(tape)
        self.assertEqual(q["active_module"]["module_id"], "M1")

    def test_active_atom_is_latest_atom_proposed(self):
        tape = self._full_tape()
        tape.append("AtomProposed", {"atom_id": "A2", "module_id": "M3"})
        q = reduce_mod.reduce_qt(tape)
        self.assertEqual(q["active_atom"]["atom_id"], "A2")

    def test_current_policy_has_a_default(self):
        # current_policy <- default/injected; an un-steered tape carries the default policy
        # (not None), so the loop always has a policy to act under.
        tape = self._full_tape()
        q = reduce_mod.reduce_qt(tape)
        self.assertIsNotNone(q["current_policy"])

    def test_human_steer_injects_policy(self):
        # current_policy <- injected: a HumanSteerInjected policy supersedes the default.
        tape = self._full_tape()
        tape.append(
            "HumanSteerInjected",
            {"policy": {"name": "go_fast"}},
        )
        q = reduce_mod.reduce_qt(tape)
        self.assertEqual(q["current_policy"], {"name": "go_fast"})


class TestRetryState(ReduceTestBase):
    def test_retry_state_counts_failure_nodes_for_active_atom(self):
        # retry_state <- count of FailureNode for the active atom.
        tape = self._full_tape()  # active atom is A1
        self.assertEqual(reduce_mod.reduce_qt(tape)["retry_state"], 0)
        tape.append("FailureNode", {"atom_id": "A1", "failure_class": "test_fail"})
        self.assertEqual(reduce_mod.reduce_qt(tape)["retry_state"], 1)
        tape.append("FailureNode", {"atom_id": "A1", "failure_class": "scope_violation"})
        self.assertEqual(reduce_mod.reduce_qt(tape)["retry_state"], 2)

    def test_retry_state_ignores_failures_for_other_atoms(self):
        tape = self._full_tape()  # active atom is A1
        tape.append("FailureNode", {"atom_id": "A0", "failure_class": "test_fail"})
        # a failure on a DIFFERENT atom must not inflate the active atom's retry count
        self.assertEqual(reduce_mod.reduce_qt(tape)["retry_state"], 0)

    def test_retry_state_resets_when_active_atom_changes(self):
        tape = self._full_tape()  # A1
        tape.append("FailureNode", {"atom_id": "A1", "failure_class": "test_fail"})
        self.assertEqual(reduce_mod.reduce_qt(tape)["retry_state"], 1)
        tape.append("AtomProposed", {"atom_id": "A2", "module_id": "M3"})  # active is now A2
        self.assertEqual(reduce_mod.reduce_qt(tape)["retry_state"], 0)


class TestPendingDecision(ReduceTestBase):
    def test_no_pending_decision_by_default(self):
        tape = self._full_tape()
        self.assertIsNone(reduce_mod.reduce_qt(tape)["pending_decision"])

    def test_open_decision_is_pending(self):
        # pending_decision <- last open decision (a HumanSteerInjected awaiting a human decision).
        tape = self._full_tape()
        tape.append(
            "HumanSteerInjected",
            {"decision_id": "D1", "needs_decision": True, "question": "rebase?"},
        )
        pd = reduce_mod.reduce_qt(tape)["pending_decision"]
        self.assertIsNotNone(pd)
        self.assertEqual(pd["decision_id"], "D1")


class TestDeterminism(ReduceTestBase):
    def test_reduce_qt_is_deterministic(self):
        tape = self._full_tape()
        q1 = reduce_mod.reduce_qt(tape)
        q2 = reduce_mod.reduce_qt(tape)
        self.assertEqual(q1, q2)


class TestDeriveWorkgraph(ReduceTestBase):
    def test_workgraph_has_required_keys(self):
        tape = self._full_tape()
        q = reduce_mod.reduce_qt(tape)
        wg = reduce_mod.derive_workgraph(q, tape, [])
        self.assertEqual(
            set(wg.keys()), {"nodes", "edges", "accepted_head", "tape_tip"}
        )
        self.assertIsInstance(wg["nodes"], list)
        self.assertIsInstance(wg["edges"], list)

    def test_workgraph_reflects_live_refs(self):
        tape = self._full_tape()
        q = reduce_mod.reduce_qt(tape)
        wg = reduce_mod.derive_workgraph(q, tape, [])
        self.assertEqual(wg["tape_tip"], tape.tape_tip())
        self.assertEqual(wg["accepted_head"], tape.accepted_head())

    def test_derive_workgraph_is_deterministic(self):
        # Called twice over the same (q_t, tape, macro_obs) -> byte-equal result.
        tape = self._full_tape()
        q = reduce_mod.reduce_qt(tape)
        wg1 = reduce_mod.derive_workgraph(q, tape, [])
        wg2 = reduce_mod.derive_workgraph(q, tape, [])
        self.assertEqual(wg1, wg2)

    def test_derive_workgraph_does_not_mutate_tape(self):
        # Conservation / no write-back: deriving the projection MUST NOT advance any ref.
        tape = self._full_tape()
        q = reduce_mod.reduce_qt(tape)
        tip_before = tape.tape_tip()
        acc_before = tape.accepted_head()
        walk_before = tape.walk()
        reduce_mod.derive_workgraph(q, tape, [])
        self.assertEqual(tape.tape_tip(), tip_before)        # tape_tip unchanged
        self.assertEqual(tape.accepted_head(), acc_before)   # accepted_head unchanged
        self.assertEqual(len(tape.walk()), len(walk_before)) # no new events on the tape

    def test_macro_observations_appear_in_workgraph(self):
        # WorkGraph = derive(q_t, tape_t, declared Macro observations) — macro_obs are projected in,
        # never folded into q_t.
        tape = self._full_tape()
        q = reduce_mod.reduce_qt(tape)
        macro_obs = [{"kind": "pr", "ref": "PR-7"}]
        wg = reduce_mod.derive_workgraph(q, tape, macro_obs)
        node_ids = [n.get("id") for n in wg["nodes"]]
        # the macro observation contributes at least one node distinct from the q_t nodes
        self.assertTrue(any("macro" in str(nid) for nid in node_ids))

    def test_workgraph_nodes_for_goal_module_atom(self):
        tape = self._full_tape()
        q = reduce_mod.reduce_qt(tape)
        wg = reduce_mod.derive_workgraph(q, tape, [])
        kinds = {n.get("kind") for n in wg["nodes"]}
        self.assertIn("goal", kinds)
        self.assertIn("module", kinds)
        self.assertIn("atom", kinds)


if __name__ == "__main__":
    unittest.main()

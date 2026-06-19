"""Contract tests for turingos.registry (the 18-event registry).

Predicate-first: these tests capture the frozen INTERFACES.md contract for registry.py
and the invariants in contracts/event_registry.json. Run with:

    PYTHONPATH=src python3 -m unittest tests.test_registry -v

stdlib unittest only (pytest is NOT installed).
"""
from __future__ import annotations

import unittest

from turingos import errors, registry


class TestLoadRegistry(unittest.TestCase):
    def test_load_default_path_returns_dict(self):
        reg = registry.load_registry()
        self.assertIsInstance(reg, dict)
        self.assertEqual(reg["contract"], "turingos.event_registry")
        self.assertTrue(reg["closed_world"])
        self.assertIn("events", reg)

    def test_load_explicit_path(self):
        # The default REGISTRY_PATH should resolve to a real file on disk.
        reg = registry.load_registry(registry.REGISTRY_PATH)
        self.assertEqual(len(reg["events"]), 18)

    def test_registry_path_is_resolvable_string(self):
        # REGISTRY_PATH is the frozen default; loading it must succeed.
        self.assertIsNotNone(registry.REGISTRY_PATH)
        reg = registry.load_registry(str(registry.REGISTRY_PATH))
        self.assertEqual(reg["counts"]["total"], 18)


class TestEventNames(unittest.TestCase):
    def test_exactly_18_event_names(self):
        names = registry.event_names()
        self.assertIsInstance(names, frozenset)
        self.assertEqual(len(names), 18)

    def test_known_names_present(self):
        names = registry.event_names()
        for expected in (
            "SystemBootstrapped",
            "ProjectAdopted",
            "GoalStateAccepted",
            "ModulePlanAccepted",
            "AtomProposed",
            "WorkCapsuleBuilt",
            "WorkerDispatched",
            "HumanSteerInjected",
            "WorkerReceiptImported",
            "MacroObservationImported",
            "PredicateEvaluated",
            "CandidateAccepted",
            "CandidateRejected",
            "FailureNode",
            "ExplorationArchived",
            "ExplorationPromoted",
            "ReplayVerified",
            "HandoffGenerated",
        ):
            self.assertIn(expected, names)


class TestClassCounts(unittest.TestCase):
    def test_class_counts_7_4_7(self):
        names = registry.event_names()
        counts = {"SOVEREIGN_ACCEPT": 0, "PROPOSAL": 0, "OBSERVATION": 0}
        for n in names:
            counts[registry.event_class(n)] += 1
        self.assertEqual(counts["SOVEREIGN_ACCEPT"], 7)
        self.assertEqual(counts["PROPOSAL"], 4)
        self.assertEqual(counts["OBSERVATION"], 7)


class TestEventClass(unittest.TestCase):
    def test_candidate_accepted_is_sovereign_accept(self):
        self.assertEqual(registry.event_class("CandidateAccepted"), "SOVEREIGN_ACCEPT")

    def test_failure_node_is_observation(self):
        self.assertEqual(registry.event_class("FailureNode"), "OBSERVATION")

    def test_atom_proposed_is_proposal(self):
        self.assertEqual(registry.event_class("AtomProposed"), "PROPOSAL")

    def test_unknown_event_class_raises_rejected_append(self):
        with self.assertRaises(errors.RejectedAppend):
            registry.event_class("Nope")


class TestHeadEffect(unittest.TestCase):
    def test_failure_node_preserves(self):
        self.assertEqual(registry.head_effect("FailureNode"), "PRESERVE")

    def test_candidate_accepted_advances(self):
        self.assertEqual(registry.head_effect("CandidateAccepted"), "ADVANCE")

    def test_all_sovereign_accept_advance_others_preserve(self):
        for n in registry.event_names():
            eff = registry.head_effect(n)
            if registry.event_class(n) == "SOVEREIGN_ACCEPT":
                self.assertEqual(eff, "ADVANCE", n)
            else:
                self.assertEqual(eff, "PRESERVE", n)

    def test_head_effect_unknown_raises_rejected_append(self):
        with self.assertRaises(errors.RejectedAppend):
            registry.head_effect("Nope")

    def test_derived_head_effect_agrees_with_json(self):
        # Load raw JSON and confirm derive-from-class equals the declared head_effect field.
        reg = registry.load_registry()
        for ev in reg["events"]:
            expected = "ADVANCE" if ev["class"] == "SOVEREIGN_ACCEPT" else "PRESERVE"
            self.assertEqual(ev["head_effect"], expected, ev["name"])
            self.assertEqual(registry.head_effect(ev["name"]), expected, ev["name"])


class TestIsPredicateGated(unittest.TestCase):
    def test_candidate_accepted_gated(self):
        self.assertTrue(registry.is_predicate_gated("CandidateAccepted"))

    def test_failure_node_not_gated(self):
        self.assertFalse(registry.is_predicate_gated("FailureNode"))

    def test_predicate_gated_iff_sovereign_accept(self):
        for n in registry.event_names():
            gated = registry.is_predicate_gated(n)
            self.assertEqual(gated, registry.event_class(n) == "SOVEREIGN_ACCEPT", n)

    def test_predicate_gated_unknown_raises_rejected_append(self):
        with self.assertRaises(errors.RejectedAppend):
            registry.is_predicate_gated("Nope")


class TestIsKnown(unittest.TestCase):
    def test_known_true(self):
        self.assertTrue(registry.is_known("CandidateAccepted"))
        self.assertTrue(registry.is_known("FailureNode"))

    def test_closed_world_unknown_false(self):
        self.assertFalse(registry.is_known("Nope"))
        self.assertFalse(registry.is_known(""))

    def test_is_known_does_not_raise(self):
        # closed-world: is_known must NEVER raise, just return False
        try:
            self.assertFalse(registry.is_known("totally-made-up"))
        except Exception as exc:  # pragma: no cover - defensive
            self.fail("is_known raised: %r" % (exc,))


if __name__ == "__main__":
    unittest.main()

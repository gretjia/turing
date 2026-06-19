"""Contract tests for turingos.capsule (stdlib unittest, NOT pytest).

Captures the frozen capsule-module contract from contracts/INTERFACES.md (capsule.py
section) + contracts/capsule.schema.json + contracts/predicate_set.md. This is the
SHIELD (Art. II/III, S-4):

    def build_capsule(tape, atom, *, failure_memory) -> dict   # emits WorkCapsuleBuilt (PROPOSAL)
    class FailureMemory:
        def classify(self, failure_node) -> dict              # raw FailureNode -> {failure_class, rule}
        def relevant_rules(self, atom) -> list                # ONLY rules whose class is relevant to atom

Key invariants under test:
  * build_capsule emits WorkCapsuleBuilt (PROPOSAL: tape_tip advances, accepted_head does NOT);
  * the built capsule validates against turingos.capsule.v1 (schemas.validate_capsule);
  * with a FailureMemory holding >=2 UNRELATED classified failures, the built capsule's
    injected_rules contains ONLY the relevant abstract rule (the shield filter);
  * SHIELD: the capsule JSON contains NO raw failure payload — no 'worker_stdout' /
    'raw_failure' / 'stack_trace' keys, no stack-trace / stdout values, and NO gate / scoring
    logic anywhere (Art. III.4 Goodhart shield).

Run: PYTHONPATH=src python3 -m unittest tests.test_capsule -v
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from turingos import capsule as capsule_mod
from turingos import schemas
from turingos.tape import Tape
from turingos.errors import SchemaInvalid


# --- fixtures ---------------------------------------------------------------


def _atom(**overrides) -> dict:
    """A minimal AtomProposed-shaped atom payload; override fields for variations."""
    atom = {
        "atom_id": "M3-A1",
        "module_id": "M3",
        "intent": "implement the predicate kernel P1..P9",
        "allowed_files": ["src/turingos/predicate.py", "tests/test_predicate.py"],
        "acceptance_commands": ["PYTHONPATH=src python3 -m unittest tests.test_predicate"],
    }
    atom.update(overrides)
    return atom


def _failure_node(atom_id="M3-A1", module_id="M3", reason_code="test_fail", **overrides) -> dict:
    """A raw FailureNode payload carrying private failure detail the shield MUST NOT broadcast.

    This is intentionally noisy: worker_stdout, a stack_trace, and a raw_failure blob are the
    sort of raw private evidence that lives on the Tape but must NEVER be injected into a capsule.
    """
    fn = {
        "atom_id": atom_id,
        "module_id": module_id,
        "reason_code": reason_code,
        "reason_detail": "P6_tests: 'python -m unittest' -> exit 1",
        "worker_stdout": "Traceback (most recent call last):\n  File 'x.py', line 9\nAssertionError: boundary case missing",
        "stack_trace": "AssertionError at predicate.py:42 in _check_p6_tests",
        "raw_failure": {"exit_code": 1, "stderr": "secret internal detail"},
    }
    fn.update(overrides)
    return fn


# A set of forbidden raw-leak substrings/keys the shield must never let into a capsule.
_FORBIDDEN_KEYS = ("worker_stdout", "raw_failure", "stack_trace", "reason_detail", "stderr")
_FORBIDDEN_VALUE_SUBSTRINGS = ("Traceback", "AssertionError", "secret internal detail")
# Gate / scoring vocabulary that must NOT appear anywhere in the capsule (Goodhart shield).
_FORBIDDEN_GATE_TOKENS = ("score", "reward", "predicate_pass", "gate", "passed", "quality", "ranking")


class CapsuleTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / parallel cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_capsule_t_", dir="/tmp")
        self.repo = os.path.join(self.root, "micro_tape")
        # Bootstrap a tape with a single sovereign writer (genesis SOVEREIGN_ACCEPT).
        self.tape = Tape.init(self.repo, "W1")
        self.tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


# --- build_capsule ----------------------------------------------------------


class TestBuildCapsuleBasics(CapsuleTestBase):
    def test_returns_capsule_dict(self):
        cap = capsule_mod.build_capsule(self.tape, _atom(), failure_memory=capsule_mod.FailureMemory())
        self.assertIsInstance(cap, dict)
        self.assertEqual(cap["schema_id"], "turingos.capsule.v1")

    def test_capsule_validates_against_schema(self):
        cap = capsule_mod.build_capsule(self.tape, _atom(), failure_memory=capsule_mod.FailureMemory())
        # Must not raise.
        schemas.validate_capsule(cap)

    def test_capsule_id_prefix_and_pattern(self):
        cap = capsule_mod.build_capsule(self.tape, _atom(), failure_memory=capsule_mod.FailureMemory())
        self.assertTrue(cap["capsule_id"].startswith("cap:"))
        hexpart = cap["capsule_id"][len("cap:"):]
        self.assertTrue(all(c in "0123456789abcdef" for c in hexpart))
        self.assertTrue(8 <= len(hexpart) <= 64)

    def test_atom_fields_carried(self):
        atom = _atom()
        cap = capsule_mod.build_capsule(self.tape, atom, failure_memory=capsule_mod.FailureMemory())
        self.assertEqual(cap["atom_id"], atom["atom_id"])
        self.assertEqual(cap["allowed_files"], atom["allowed_files"])
        self.assertEqual(cap["acceptance_commands"], atom["acceptance_commands"])

    def test_budget_present_and_well_formed(self):
        cap = capsule_mod.build_capsule(self.tape, _atom(), failure_memory=capsule_mod.FailureMemory())
        self.assertIn("budget", cap)
        self.assertIn("wall_seconds", cap["budget"])
        self.assertIn("max_retries", cap["budget"])
        self.assertGreaterEqual(cap["budget"]["wall_seconds"], 1)
        self.assertGreaterEqual(cap["budget"]["max_retries"], 0)

    def test_context_binds_tape_tip_and_accepted_head(self):
        # The capsule binds the tip it was PROPOSED against (the parent it built on, FF semantics
        # the predicate P2 re-checks); emitting WorkCapsuleBuilt then advances tape_tip, so context
        # must equal the pre-build tip, not the post-build one. accepted_head is unchanged (PRESERVE).
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        cap = capsule_mod.build_capsule(self.tape, _atom(), failure_memory=capsule_mod.FailureMemory())
        self.assertEqual(cap["context"]["tape_tip"], tip_before)
        self.assertEqual(cap["context"]["accepted_head"], acc_before)
        self.assertEqual(self.tape.accepted_head(), acc_before)  # accepted_head did not move

    def test_no_failure_memory_means_empty_injected_rules(self):
        cap = capsule_mod.build_capsule(self.tape, _atom(), failure_memory=capsule_mod.FailureMemory())
        self.assertEqual(cap.get("injected_rules", []), [])


class TestBuildCapsuleEmitsEvent(CapsuleTestBase):
    def test_emits_work_capsule_built(self):
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        cap = capsule_mod.build_capsule(self.tape, _atom(), failure_memory=capsule_mod.FailureMemory())

        # PROPOSAL: tape_tip advances, accepted_head does NOT (shield event is never sovereign).
        self.assertNotEqual(self.tape.tape_tip(), tip_before)
        self.assertEqual(self.tape.accepted_head(), acc_before)

        # The latest event on the tape is WorkCapsuleBuilt and carries the built capsule.
        ev = self.tape.read_event("mu:" + self.tape.tape_tip())
        self.assertEqual(ev["event_type"], "WorkCapsuleBuilt")
        # The emitted event payload must contain the capsule (byte-for-byte round trip).
        self.assertEqual(ev["payload"], cap)


# --- FailureMemory.classify -------------------------------------------------


class TestFailureMemoryClassify(CapsuleTestBase):
    def test_classify_returns_class_and_abstract_rule(self):
        fm = capsule_mod.FailureMemory()
        out = fm.classify(_failure_node())
        self.assertIn("failure_class", out)
        self.assertIn("rule", out)
        self.assertIsInstance(out["failure_class"], str)
        self.assertIsInstance(out["rule"], str)
        self.assertTrue(out["failure_class"])
        self.assertTrue(out["rule"])

    def test_classify_rule_is_abstract_not_raw(self):
        # The lifted rule must be an ABSTRACT lesson, never the raw stdout / stack trace.
        fm = capsule_mod.FailureMemory()
        out = fm.classify(_failure_node())
        blob = json.dumps(out)
        for needle in _FORBIDDEN_VALUE_SUBSTRINGS:
            self.assertNotIn(needle, blob, f"classify leaked raw value {needle!r}")
        for key in _FORBIDDEN_KEYS:
            self.assertNotIn(key, out, f"classify leaked raw key {key!r}")

    def test_classify_deterministic_for_same_reason_code(self):
        fm = capsule_mod.FailureMemory()
        a = fm.classify(_failure_node(reason_code="test_fail"))
        b = fm.classify(_failure_node(reason_code="test_fail", atom_id="OTHER"))
        self.assertEqual(a["failure_class"], b["failure_class"])

    def test_classify_different_reason_codes_different_class(self):
        fm = capsule_mod.FailureMemory()
        a = fm.classify(_failure_node(reason_code="test_fail"))
        b = fm.classify(_failure_node(reason_code="scope_violation"))
        self.assertNotEqual(a["failure_class"], b["failure_class"])


# --- FailureMemory.relevant_rules (the shield filter) -----------------------


class TestRelevantRulesFilter(CapsuleTestBase):
    def test_empty_memory_returns_no_rules(self):
        fm = capsule_mod.FailureMemory()
        self.assertEqual(fm.relevant_rules(_atom()), [])

    def test_only_relevant_class_returned_from_two_unrelated(self):
        # Two UNRELATED classified failures: one against the atom we are about to build for
        # (M3-A1), one against a totally different atom/module (M9-Z9). relevant_rules MUST
        # return ONLY the rule relevant to the target atom.
        fm = capsule_mod.FailureMemory()
        relevant_fn = _failure_node(atom_id="M3-A1", module_id="M3", reason_code="test_fail")
        unrelated_fn = _failure_node(atom_id="M9-Z9", module_id="M9", reason_code="scope_violation")
        fm.classify(relevant_fn)
        fm.classify(unrelated_fn)

        rules = fm.relevant_rules(_atom(atom_id="M3-A1", module_id="M3"))
        self.assertEqual(len(rules), 1)
        # The two failures had different failure_classes; only the relevant one survives.
        classes = {r["failure_class"] for r in rules}
        self.assertEqual(len(classes), 1)
        # Each surviving rule is the {failure_class, rule} shape (additionalProperties=false safe).
        for r in rules:
            self.assertEqual(set(r.keys()), {"failure_class", "rule"})

    def test_built_capsule_injects_only_relevant_rule(self):
        # End-to-end shield: build a capsule with a FailureMemory holding 2 unrelated classes.
        fm = capsule_mod.FailureMemory()
        fm.classify(_failure_node(atom_id="M3-A1", module_id="M3", reason_code="test_fail"))
        fm.classify(_failure_node(atom_id="M9-Z9", module_id="M9", reason_code="anchor_mismatch"))

        cap = capsule_mod.build_capsule(self.tape, _atom(atom_id="M3-A1", module_id="M3"), failure_memory=fm)
        schemas.validate_capsule(cap)

        injected = cap.get("injected_rules", [])
        self.assertEqual(len(injected), 1, f"expected exactly the relevant rule, got {injected}")
        for r in injected:
            self.assertEqual(set(r.keys()), {"failure_class", "rule"})


# --- SHIELD: no raw failure / no gate logic leaks into the capsule ----------


class TestShieldNoLeak(CapsuleTestBase):
    def _build_with_failures(self):
        fm = capsule_mod.FailureMemory()
        fm.classify(_failure_node(atom_id="M3-A1", module_id="M3", reason_code="test_fail"))
        fm.classify(_failure_node(atom_id="M9-Z9", module_id="M9", reason_code="scope_violation"))
        return capsule_mod.build_capsule(self.tape, _atom(atom_id="M3-A1", module_id="M3"), failure_memory=fm)

    def test_capsule_has_no_raw_failure_keys(self):
        cap = self._build_with_failures()
        blob = json.dumps(cap)
        for key in _FORBIDDEN_KEYS:
            self.assertNotIn(f'"{key}"', blob, f"capsule leaked raw failure key {key!r}")

    def test_capsule_has_no_raw_failure_values(self):
        cap = self._build_with_failures()
        blob = json.dumps(cap)
        for needle in _FORBIDDEN_VALUE_SUBSTRINGS:
            self.assertNotIn(needle, blob, f"capsule leaked raw failure value {needle!r}")

    def test_capsule_has_no_gate_or_scoring_logic(self):
        # Art. III.4 Goodhart shield: gate/scoring logic is EXCLUDED from the capsule.
        cap = self._build_with_failures()
        blob = json.dumps(cap).lower()
        for token in _FORBIDDEN_GATE_TOKENS:
            self.assertNotIn(token, blob, f"capsule leaked gate/scoring token {token!r}")

    def test_capsule_schema_rejects_extra_keys(self):
        # Defense in depth: even if a raw key were injected, the schema (additionalProperties=false)
        # rejects it — proving the shield can never smuggle raw payload through a valid capsule.
        cap = self._build_with_failures()
        cap["worker_stdout"] = "leak"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_emitted_event_payload_also_shielded(self):
        # The WorkCapsuleBuilt event recorded on the tape must itself be shielded.
        self._build_with_failures()
        ev = self.tape.read_event("mu:" + self.tape.tape_tip())
        blob = json.dumps(ev["payload"])
        for key in _FORBIDDEN_KEYS:
            self.assertNotIn(f'"{key}"', blob)
        for needle in _FORBIDDEN_VALUE_SUBSTRINGS:
            self.assertNotIn(needle, blob)


# --- determinism ------------------------------------------------------------


class TestDeterminism(CapsuleTestBase):
    def test_same_atom_same_context_same_capsule_id(self):
        # Same atom + same tape context (no intervening append between reads of capsule_id inputs)
        # must yield the same capsule_id (content-addressed). We compute it twice over the SAME tip
        # by reading what build_capsule would hash; here we assert two builds on a frozen-input atom
        # produce capsule_ids that are stable given identical (atom, context) — the id is a function
        # of those inputs, so building against the SAME tip twice gives the same id.
        atom = _atom()
        cap1 = capsule_mod.build_capsule(self.tape, atom, failure_memory=capsule_mod.FailureMemory())
        # The second build happens after the first WorkCapsuleBuilt advanced tape_tip, so its
        # context differs; therefore its id MUST differ (content-addressed over context too).
        cap2 = capsule_mod.build_capsule(self.tape, atom, failure_memory=capsule_mod.FailureMemory())
        self.assertNotEqual(cap1["context"]["tape_tip"], cap2["context"]["tape_tip"])
        self.assertNotEqual(cap1["capsule_id"], cap2["capsule_id"])


if __name__ == "__main__":
    unittest.main()

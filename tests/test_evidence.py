"""Contract tests for turingos.evidence (stdlib unittest, NOT pytest).

Captures the frozen evidence-module contract from contracts/INTERFACES.md (evidence.py
section) + contracts/receipt.schema.json:

    def import_receipt(tape, receipt) -> str         # emits WorkerReceiptImported (OBSERVATION)
    def import_macro_observation(tape, obs) -> str    # emits MacroObservationImported (tree OID anchor)

Both events are OBSERVATIONs (head_effect=PRESERVE): they move tape_tip but NEVER accepted_head.
A receipt is imported via schemas.validate_receipt -> SchemaInvalid on a bad receipt. The imported
payload is retrievable byte-for-byte via tape.read_event. A macro observation must carry a non-empty
tree_oid anchor (the P7 ANCHOR_BINDS_HASH binding target) and that tree_oid must be retrievable.

Run: PYTHONPATH=src python3 -m unittest tests.test_evidence -v
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from turingos import evidence
from turingos.tape import Tape
from turingos.errors import SchemaInvalid, RejectedAppend


def _valid_receipt(**overrides) -> dict:
    """A minimal schema-valid turingos.receipt.v1 receipt; override fields for negative cases."""
    receipt = {
        "schema_id": "turingos.receipt.v1",
        "receipt_id": "rcpt:deadbeef",
        "capsule_id": "cap:cafef00d",
        "worker_id": "fake",
        "worktree_path": "/tmp/wt/atom-1",
        "candidate": {
            "tree_oid": "a" * 64,
            "files_touched": ["src/turingos/foo.py"],
        },
        "status": "ok",
    }
    receipt.update(overrides)
    return receipt


class EvidenceTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / parallel cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_evidence_t_")
        self.repo = os.path.join(self.root, "micro_tape")
        # Bootstrap a tape with a single sovereign writer (genesis SOVEREIGN_ACCEPT).
        self.tape = Tape.init(self.repo, "W1")
        self.tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestImportReceipt(EvidenceTestBase):
    def test_returns_event_id(self):
        ev = evidence.import_receipt(self.tape, _valid_receipt())
        self.assertIsInstance(ev, str)
        self.assertTrue(ev.startswith("mu:"))
        self.assertEqual(len("mu:") + 64, len(ev))  # mu: + 64-hex sha256 oid

    def test_moves_tape_tip_not_accepted_head(self):
        # WorkerReceiptImported is an OBSERVATION (PRESERVE): tape_tip advances, accepted_head frozen.
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        ev = evidence.import_receipt(self.tape, _valid_receipt())

        self.assertNotEqual(self.tape.tape_tip(), tip_before)  # tape_tip moved
        self.assertEqual(self.tape.tape_tip(), ev[len("mu:"):])  # tip == imported event oid
        self.assertEqual(self.tape.accepted_head(), acc_before)  # accepted_head DID NOT move

    def test_records_correct_event_type(self):
        ev = evidence.import_receipt(self.tape, _valid_receipt())
        node = self.tape.read_event(ev)
        self.assertEqual(node["event_type"], "WorkerReceiptImported")

    def test_receipt_retrievable_byte_for_byte(self):
        receipt = _valid_receipt()
        ev = evidence.import_receipt(self.tape, receipt)
        node = self.tape.read_event(ev)
        self.assertEqual(node["payload"], receipt)
        # the candidate tree_oid (the P7 anchor) survives the round-trip
        self.assertEqual(node["payload"]["candidate"]["tree_oid"], receipt["candidate"]["tree_oid"])

    def test_invalid_receipt_raises_schema_invalid(self):
        # missing required field 'status'
        bad = _valid_receipt()
        del bad["status"]
        with self.assertRaises(SchemaInvalid):
            evidence.import_receipt(self.tape, bad)

    def test_wrong_schema_id_raises_schema_invalid(self):
        with self.assertRaises(SchemaInvalid):
            evidence.import_receipt(self.tape, _valid_receipt(schema_id="turingos.capsule.v1"))

    def test_bad_status_enum_raises_schema_invalid(self):
        with self.assertRaises(SchemaInvalid):
            evidence.import_receipt(self.tape, _valid_receipt(status="bogus"))

    def test_invalid_receipt_does_not_move_tape_tip(self):
        # A rejected import must land NO commit — the tape is unchanged.
        tip_before = self.tape.tape_tip()
        bad = _valid_receipt()
        del bad["status"]
        with self.assertRaises(SchemaInvalid):
            evidence.import_receipt(self.tape, bad)
        self.assertEqual(self.tape.tape_tip(), tip_before)


class TestImportMacroObservation(EvidenceTestBase):
    def test_returns_event_id(self):
        ev = evidence.import_macro_observation(self.tape, {"tree_oid": "b" * 64})
        self.assertTrue(ev.startswith("mu:"))
        self.assertEqual(len("mu:") + 64, len(ev))

    def test_moves_tape_tip_not_accepted_head(self):
        # MacroObservationImported is an OBSERVATION (PRESERVE).
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        ev = evidence.import_macro_observation(self.tape, {"tree_oid": "b" * 64})
        self.assertNotEqual(self.tape.tape_tip(), tip_before)
        self.assertEqual(self.tape.tape_tip(), ev[len("mu:"):])
        self.assertEqual(self.tape.accepted_head(), acc_before)

    def test_records_correct_event_type(self):
        ev = evidence.import_macro_observation(self.tape, {"tree_oid": "b" * 64})
        node = self.tape.read_event(ev)
        self.assertEqual(node["event_type"], "MacroObservationImported")

    def test_records_tree_oid_retrievable(self):
        obs = {"tree_oid": "c" * 64, "macro_commit": "d" * 64, "ci_status": "green"}
        ev = evidence.import_macro_observation(self.tape, obs)
        node = self.tape.read_event(ev)
        self.assertEqual(node["payload"]["tree_oid"], "c" * 64)
        self.assertEqual(node["payload"], obs)

    def test_missing_tree_oid_rejected(self):
        with self.assertRaises((SchemaInvalid, RejectedAppend)):
            evidence.import_macro_observation(self.tape, {"macro_commit": "d" * 64})

    def test_empty_tree_oid_rejected(self):
        with self.assertRaises((SchemaInvalid, RejectedAppend)):
            evidence.import_macro_observation(self.tape, {"tree_oid": ""})

    def test_non_string_tree_oid_rejected(self):
        with self.assertRaises((SchemaInvalid, RejectedAppend)):
            evidence.import_macro_observation(self.tape, {"tree_oid": 123})

    def test_rejected_observation_does_not_move_tape_tip(self):
        tip_before = self.tape.tape_tip()
        with self.assertRaises((SchemaInvalid, RejectedAppend)):
            evidence.import_macro_observation(self.tape, {"tree_oid": ""})
        self.assertEqual(self.tape.tape_tip(), tip_before)


if __name__ == "__main__":
    unittest.main()

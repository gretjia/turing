"""Contract tests for turingos.envelope (the 7-field Append Envelope).

Predicate-first: these tests capture the frozen INTERFACES.md (envelope.py section) and
contracts/append_envelope.md contract BEFORE the implementation exists. Run with:

    PYTHONPATH=src python3 -m unittest tests.test_envelope -v

stdlib unittest only (pytest is NOT installed).

Contract under test
-------------------
* AppendEnvelope is a FROZEN dataclass with EXACTLY these fields, in order:
    prev_tape_tip, event_schema_id, payload_hash, head_effect,
    accepted_head_before, writer_id, authority_epoch=0
* to_payload() returns a dict with EXACTLY the 7 keys, all ASCII.
* derive_head_effect(event_type) delegates to registry.head_effect:
    derive_head_effect('CandidateAccepted') == 'ADVANCE'   (SOVEREIGN_ACCEPT)
    derive_head_effect('FailureNode')       == 'PRESERVE'   (OBSERVATION)
"""
from __future__ import annotations

import dataclasses
import unittest

from turingos import envelope, errors, registry


# A representative, well-formed envelope used across cases. The values are opaque to the
# envelope module (it is a pure data carrier + payload projection); they need only be the
# right shape. head_effect is registry-derived from CandidateAccepted (ADVANCE).
def _make(**overrides):
    base = dict(
        prev_tape_tip="0" * 64,
        event_schema_id="CandidateAccepted",
        payload_hash="sha256:" + ("a" * 64),
        head_effect="ADVANCE",
        accepted_head_before="1" * 64,
        writer_id="writer-0",
    )
    base.update(overrides)
    return envelope.AppendEnvelope(**base)


# The 7 fields, in their frozen order.
_EXPECTED_FIELDS = (
    "prev_tape_tip",
    "event_schema_id",
    "payload_hash",
    "head_effect",
    "accepted_head_before",
    "writer_id",
    "authority_epoch",
)


class TestDataclassShape(unittest.TestCase):
    def test_is_a_dataclass(self):
        self.assertTrue(dataclasses.is_dataclass(envelope.AppendEnvelope))

    def test_is_frozen(self):
        # A frozen dataclass sets __setattr__ to raise FrozenInstanceError.
        params = getattr(envelope.AppendEnvelope, "__dataclass_params__", None)
        self.assertIsNotNone(params)
        self.assertTrue(params.frozen)

    def test_exactly_seven_fields_in_order(self):
        names = tuple(f.name for f in dataclasses.fields(envelope.AppendEnvelope))
        self.assertEqual(names, _EXPECTED_FIELDS)

    def test_authority_epoch_defaults_to_zero(self):
        env = _make()
        self.assertEqual(env.authority_epoch, 0)

    def test_authority_epoch_is_int_field(self):
        # authority_epoch is RESERVED-deferred; an int with a 0 default.
        env = _make()
        self.assertIsInstance(env.authority_epoch, int)


class TestImmutability(unittest.TestCase):
    def test_cannot_reassign_field(self):
        env = _make()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            env.prev_tape_tip = "deadbeef"  # type: ignore[misc]

    def test_cannot_reassign_authority_epoch(self):
        env = _make()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            env.authority_epoch = 7  # type: ignore[misc]


class TestToPayload(unittest.TestCase):
    def test_returns_dict(self):
        self.assertIsInstance(_make().to_payload(), dict)

    def test_exactly_the_seven_keys(self):
        payload = _make().to_payload()
        self.assertEqual(set(payload.keys()), set(_EXPECTED_FIELDS))
        self.assertEqual(len(payload), 7)

    def test_keys_are_ascii(self):
        payload = _make().to_payload()
        for key in payload:
            # ASCII-only load-bearing keys [codec policy].
            self.assertTrue(key.isascii(), f"non-ASCII key: {key!r}")

    def test_values_round_trip(self):
        env = _make(
            prev_tape_tip="abc",
            event_schema_id="CandidateAccepted",
            payload_hash="sha256:" + ("b" * 64),
            head_effect="ADVANCE",
            accepted_head_before="def",
            writer_id="w-9",
            authority_epoch=0,
        )
        payload = env.to_payload()
        self.assertEqual(payload["prev_tape_tip"], "abc")
        self.assertEqual(payload["event_schema_id"], "CandidateAccepted")
        self.assertEqual(payload["payload_hash"], "sha256:" + ("b" * 64))
        self.assertEqual(payload["head_effect"], "ADVANCE")
        self.assertEqual(payload["accepted_head_before"], "def")
        self.assertEqual(payload["writer_id"], "w-9")
        self.assertEqual(payload["authority_epoch"], 0)

    def test_payload_is_a_fresh_dict(self):
        # Mutating the returned payload must not corrupt the frozen envelope's view.
        env = _make()
        p1 = env.to_payload()
        p1["prev_tape_tip"] = "mutated"
        p2 = env.to_payload()
        self.assertNotEqual(p2["prev_tape_tip"], "mutated")


class TestDeriveHeadEffect(unittest.TestCase):
    def test_candidate_accepted_advances(self):
        self.assertEqual(envelope.derive_head_effect("CandidateAccepted"), "ADVANCE")

    def test_failure_node_preserves(self):
        self.assertEqual(envelope.derive_head_effect("FailureNode"), "PRESERVE")

    def test_delegates_to_registry(self):
        # Spot-check delegation against the registry for every known event type.
        for name in registry.event_names():
            self.assertEqual(
                envelope.derive_head_effect(name),
                registry.head_effect(name),
                f"derive_head_effect disagrees with registry for {name!r}",
            )

    def test_unknown_event_type_rejected(self):
        # Closed-world: derive_head_effect on an unknown type propagates the registry's reject.
        with self.assertRaises(errors.RejectedAppend):
            envelope.derive_head_effect("NotAnEvent")


if __name__ == "__main__":
    unittest.main()

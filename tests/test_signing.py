"""Contract tests for turingos.signing (ApprovalCard byte/hash model + SigningBackend).

Predicate-first: these tests capture the frozen contract from
contracts/approval_card.md (ADR-0007) + contracts/INTERFACES.md (signing section).
They are written BEFORE the implementation. Stdlib unittest only (pytest is not
installed and the kernel stays dependency-free).

The corrected, binding model (approval_card.md):
    canonical_bytes   := JCS(load-bearing signed fields, ASCII keys, no floats)
                         # display / localization copy EXCLUDED
    visible_card_hash := sha256(canonical_bytes)   # DERIVED digest (NOT the bytes)
    signature         := sign(canonical_bytes)     # DERIVED over the SAME bytes
    gate / replay     := re-derive sha256(canonical_bytes) AND verify(signature)

Run: PYTHONPATH=src python3 -m unittest tests.test_signing -v
"""
from __future__ import annotations

import abc
import hashlib
import re
import unittest

from turingos import codec, signing


# A representative ApprovalCard field set: the signed load-bearing fields from
# contracts/approval_card.md plus a (non-signed) display block.
def base_fields() -> dict:
    return {
        "action_kind": "merge",
        "target": "mu:" + ("a" * 64),
        "evidence_set_digest": "sha256:" + ("b" * 64),
        "risk_class": "R1",
        "expires_at": "2026-12-31T23:59:59Z",
        "nonce": "nonce-0001",
        "tape_tip": "mu:" + ("c" * 64),
        "accepted_head": "mu:" + ("d" * 64),
        "authority_epoch": 0,
        "signature_route": "inproc",
        "key_id": "inproc-key-1",
        # display copy is NOT part of canonical_bytes:
        "display": {
            "title": "Accept candidate",
            "en": "Merge the proposed change",
            "zh": "合并提议的更改",
            "layout": "card-v1",
        },
    }


HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class TestSigningBackend(unittest.TestCase):
    def test_is_abstract(self):
        self.assertTrue(issubclass(signing.SigningBackend, abc.ABC))
        with self.assertRaises(TypeError):
            signing.SigningBackend()  # type: ignore[abstract]

    def test_inproc_is_a_signing_backend(self):
        self.assertTrue(issubclass(signing.InProcSigningBackend, signing.SigningBackend))
        b = signing.InProcSigningBackend()
        self.assertIsInstance(b.key_id(), str)
        self.assertTrue(b.key_id())

    def test_sign_is_deterministic_hex(self):
        b = signing.InProcSigningBackend()
        data = b"hello-turingos"
        s1 = b.sign(data)
        s2 = b.sign(data)
        self.assertEqual(s1, s2)
        self.assertIsInstance(s1, str)
        # HMAC-SHA256 hex digest is 64 lowercase hex chars.
        self.assertTrue(HEX64_RE.match(s1), s1)

    def test_sign_differs_for_different_bytes(self):
        b = signing.InProcSigningBackend()
        self.assertNotEqual(b.sign(b"a"), b.sign(b"b"))

    def test_verify_roundtrip(self):
        b = signing.InProcSigningBackend()
        data = b"payload-bytes"
        self.assertTrue(b.verify(data, b.sign(data)))

    def test_verify_rejects_bad_signature(self):
        b = signing.InProcSigningBackend()
        data = b"payload-bytes"
        self.assertFalse(b.verify(data, b.sign(b"other")))
        self.assertFalse(b.verify(data, "not-a-real-signature"))

    def test_verify_rejects_wrong_bytes(self):
        b = signing.InProcSigningBackend()
        sig = b.sign(b"original")
        self.assertFalse(b.verify(b"tampered", sig))


class TestBuildApprovalCard(unittest.TestCase):
    def test_card_has_required_fields(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        for key in ("canonical_bytes", "visible_card_hash", "signature", "key_id", "display"):
            self.assertIn(key, card, key)

    def test_canonical_bytes_stored_as_hex(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        cb_hex = card["canonical_bytes"]
        self.assertIsInstance(cb_hex, str)
        # hex of arbitrary length, even number of chars, all hex digits
        self.assertTrue(re.match(r"^[0-9a-f]+$", cb_hex), cb_hex)
        self.assertEqual(len(cb_hex) % 2, 0)
        # decodes back to bytes without error
        raw = bytes.fromhex(cb_hex)
        self.assertIsInstance(raw, bytes)

    def test_canonical_bytes_excludes_display(self):
        # The recovered canonical bytes must NOT contain any display copy.
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        raw = bytes.fromhex(card["canonical_bytes"])
        self.assertNotIn(b"display", raw)
        self.assertNotIn(b"layout", raw)
        # the load-bearing keys ARE present
        self.assertIn(b"action_kind", raw)
        self.assertIn(b"evidence_set_digest", raw)

    def test_canonical_bytes_equals_codec_over_signed_fields(self):
        # Build the expected signed-field subset (everything except 'display').
        b = signing.InProcSigningBackend()
        fields = base_fields()
        signed = {k: v for k, v in fields.items() if k != "display"}
        expected = codec.canonical_bytes(signed)
        card = signing.build_approval_card(fields, b)
        self.assertEqual(bytes.fromhex(card["canonical_bytes"]), expected)

    def test_visible_card_hash_is_sha256_of_canonical_bytes(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        raw = bytes.fromhex(card["canonical_bytes"])
        self.assertEqual(card["visible_card_hash"], hashlib.sha256(raw).hexdigest())
        self.assertTrue(HEX64_RE.match(card["visible_card_hash"]))

    def test_visible_card_hash_not_byte_equal_to_canonical_bytes(self):
        # A hash is a FUNCTION of the bytes, never byte-equal to them (the retired
        # four-way byte-equality category error).
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        self.assertNotEqual(card["visible_card_hash"], card["canonical_bytes"])
        self.assertNotEqual(card["visible_card_hash"].encode(), bytes.fromhex(card["canonical_bytes"]))

    def test_signature_matches_backend_over_canonical_bytes(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        raw = bytes.fromhex(card["canonical_bytes"])
        self.assertEqual(card["signature"], b.sign(raw))

    def test_key_id_from_backend(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        self.assertEqual(card["key_id"], b.key_id())

    def test_display_preserved_in_card(self):
        b = signing.InProcSigningBackend()
        fields = base_fields()
        card = signing.build_approval_card(fields, b)
        self.assertEqual(card["display"], fields["display"])

    def test_build_is_deterministic(self):
        b = signing.InProcSigningBackend()
        c1 = signing.build_approval_card(base_fields(), b)
        c2 = signing.build_approval_card(base_fields(), b)
        self.assertEqual(c1["canonical_bytes"], c2["canonical_bytes"])
        self.assertEqual(c1["visible_card_hash"], c2["visible_card_hash"])
        self.assertEqual(c1["signature"], c2["signature"])


class TestVerifyApprovalCard(unittest.TestCase):
    def test_roundtrip_true(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        self.assertTrue(signing.verify_approval_card(card, b))

    def test_mutating_signed_field_fails_closed(self):
        # Tamper with a signed load-bearing field but keep the OLD signature/hash:
        # this is the attack the gate must reject.
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)

        tampered_fields = base_fields()
        tampered_fields["risk_class"] = "R3"  # escalate risk silently
        tampered_signed = {k: v for k, v in tampered_fields.items() if k != "display"}
        # rewrite ONLY the canonical_bytes to the tampered subset, keep old sig+hash
        card_tampered = dict(card)
        card_tampered["canonical_bytes"] = codec.canonical_bytes(tampered_signed).hex()
        self.assertFalse(signing.verify_approval_card(card_tampered, b))

    def test_mutating_hash_fails_closed(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        bad = dict(card)
        bad["visible_card_hash"] = "0" * 64
        self.assertFalse(signing.verify_approval_card(bad, b))

    def test_mutating_signature_fails_closed(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        bad = dict(card)
        bad["signature"] = "f" * 64
        self.assertFalse(signing.verify_approval_card(bad, b))

    def test_target_head_change_fails_closed(self):
        # Changing the bound target/head must invalidate the card (Art. I.1 fail-closed).
        b = signing.InProcSigningBackend()
        fields = base_fields()
        card = signing.build_approval_card(fields, b)
        moved = dict(fields)
        moved["accepted_head"] = "mu:" + ("e" * 64)
        moved_signed = {k: v for k, v in moved.items() if k != "display"}
        bad = dict(card)
        bad["canonical_bytes"] = codec.canonical_bytes(moved_signed).hex()
        self.assertFalse(signing.verify_approval_card(bad, b))

    def test_changing_display_does_not_change_hash_or_signature(self):
        # Display copy is EXCLUDED: re-building with different display copy must yield
        # identical canonical_bytes / hash / signature, and verify must still pass.
        b = signing.InProcSigningBackend()
        card_a = signing.build_approval_card(base_fields(), b)

        fields_b = base_fields()
        fields_b["display"] = {
            "title": "TOTALLY DIFFERENT TITLE",
            "en": "different english copy",
            "zh": "完全不同的文案",
            "layout": "card-v2-redesigned",
            "extra": "an entirely new display field",
        }
        card_b = signing.build_approval_card(fields_b, b)

        self.assertEqual(card_a["canonical_bytes"], card_b["canonical_bytes"])
        self.assertEqual(card_a["visible_card_hash"], card_b["visible_card_hash"])
        self.assertEqual(card_a["signature"], card_b["signature"])
        self.assertNotEqual(card_a["display"], card_b["display"])
        self.assertTrue(signing.verify_approval_card(card_b, b))

    def test_editing_display_on_a_built_card_still_verifies(self):
        # Mutating ONLY the display block of an already-built card does not break verify
        # (display is not part of the signed bytes).
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        card["display"] = {"title": "edited after the fact"}
        self.assertTrue(signing.verify_approval_card(card, b))

    def test_wrong_backend_key_fails_closed(self):
        # A different signer key cannot verify a card it did not sign.
        b1 = signing.InProcSigningBackend(key=b"key-one", key_id="k1")
        b2 = signing.InProcSigningBackend(key=b"key-two", key_id="k2")
        card = signing.build_approval_card(base_fields(), b1)
        self.assertFalse(signing.verify_approval_card(card, b2))

    def test_malformed_canonical_bytes_fails_closed(self):
        # Garbage hex must not raise; it must fail closed (False).
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        bad = dict(card)
        bad["canonical_bytes"] = "not-hex-zz"
        self.assertFalse(signing.verify_approval_card(bad, b))

    def test_missing_field_fails_closed(self):
        b = signing.InProcSigningBackend()
        card = signing.build_approval_card(base_fields(), b)
        for key in ("canonical_bytes", "visible_card_hash", "signature"):
            bad = dict(card)
            del bad[key]
            self.assertFalse(signing.verify_approval_card(bad, b), key)


if __name__ == "__main__":
    unittest.main()

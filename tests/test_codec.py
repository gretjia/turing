"""Contract tests for turingos.codec (turingos.jcs.v1).

Predicate-first: these tests capture the frozen codec contract from
contracts/codec_policy.md + contracts/INTERFACES.md (codec section). They are
written BEFORE the implementation. Stdlib unittest only (pytest is not installed
and the kernel stays dependency-free).

Run: PYTHONPATH=src python3 -m unittest tests.test_codec -v
"""
from __future__ import annotations

import hashlib
import re
import unittest

from turingos import codec
from turingos.errors import AsciiKeyViolation, FloatViolation


GOOD_OID = "a" * 64                          # 64 hex chars
GOOD_OID_2 = "0123456789abcdef" * 4          # 64 hex, mixed digits/letters


class TestCanonicalBytesDeterminism(unittest.TestCase):
    def test_same_payload_twice_identical_bytes(self):
        payload = {"event": "boot", "n": 7, "ok": True, "tags": ["a", "b"]}
        b1 = codec.canonical_bytes(payload)
        b2 = codec.canonical_bytes(payload)
        self.assertEqual(b1, b2)
        self.assertIsInstance(b1, bytes)

    def test_same_payload_twice_identical_digest(self):
        payload = {"event": "boot", "n": 7}
        self.assertEqual(codec.content_digest(payload), codec.content_digest(payload))

    def test_canonical_bytes_minimal_separators(self):
        # No insignificant whitespace; minimal separators.
        b = codec.canonical_bytes({"a": 1, "b": 2})
        self.assertEqual(b, b'{"a":1,"b":2}')

    def test_nested_determinism(self):
        p = {"outer": {"z": 1, "a": 2}, "list": [{"k": 1}, {"k": 2}]}
        self.assertEqual(codec.canonical_bytes(p), codec.canonical_bytes(p))


class TestKeyOrderIndependence(unittest.TestCase):
    def test_top_level_key_order_independent(self):
        a = {"a": 1, "b": 2}
        b = {"b": 2, "a": 1}
        self.assertEqual(codec.canonical_bytes(a), codec.canonical_bytes(b))
        self.assertEqual(codec.content_digest(a), codec.content_digest(b))

    def test_nested_key_order_independent(self):
        a = {"outer": {"a": 1, "b": 2, "c": 3}}
        b = {"outer": {"c": 3, "b": 2, "a": 1}}
        self.assertEqual(codec.canonical_bytes(a), codec.canonical_bytes(b))

    def test_ascii_sort_equals_rfc8785_order(self):
        # For ASCII-only keys, Python sorted() == RFC 8785 UTF-16 code-unit order.
        # Uppercase < underscore < lowercase by codepoint.
        b = codec.canonical_bytes({"b": 2, "a": 1, "A": 3, "_": 4})
        self.assertEqual(b, b'{"A":3,"_":4,"a":1,"b":2}')


class TestAsciiKeyGuard(unittest.TestCase):
    def test_ascii_keys_ok(self):
        # Should not raise.
        codec.assert_ascii_keys({"hello": 1, "world": {"nested": 2}})

    def test_non_ascii_top_level_key_raises(self):
        with self.assertRaises(AsciiKeyViolation):
            codec.assert_ascii_keys({"café": 1})

    def test_non_ascii_nested_key_raises(self):
        with self.assertRaises(AsciiKeyViolation):
            codec.assert_ascii_keys({"outer": {"naïve": 1}})

    def test_non_ascii_key_in_list_of_dicts_raises(self):
        with self.assertRaises(AsciiKeyViolation):
            codec.assert_ascii_keys({"items": [{"ok": 1}, {"μ": 2}]})

    def test_non_str_key_raises(self):
        # A dict with a non-string key cannot be a valid ASCII key.
        with self.assertRaises(AsciiKeyViolation):
            codec.assert_ascii_keys({1: "x"})

    def test_canonical_bytes_rejects_non_ascii_key(self):
        with self.assertRaises(AsciiKeyViolation):
            codec.canonical_bytes({"náме": 1})


class TestNoFloatGuard(unittest.TestCase):
    def test_ints_and_bools_ok(self):
        # bool is a subclass of int but is NOT a float -> must be allowed.
        codec.assert_no_floats({"n": 1, "flag": True, "other": False, "neg": -5})

    def test_float_top_level_raises(self):
        with self.assertRaises(FloatViolation):
            codec.assert_no_floats({"x": 1.5})

    def test_float_nested_raises(self):
        with self.assertRaises(FloatViolation):
            codec.assert_no_floats({"outer": {"x": 0.1}})

    def test_float_in_list_raises(self):
        with self.assertRaises(FloatViolation):
            codec.assert_no_floats({"vals": [1, 2, 3.0]})

    def test_float_in_nested_list_of_dicts_raises(self):
        with self.assertRaises(FloatViolation):
            codec.assert_no_floats({"items": [{"k": 1}, {"k": 2.5}]})

    def test_bool_not_treated_as_float(self):
        # Explicit: True/False must NOT raise FloatViolation.
        try:
            codec.assert_no_floats({"a": True, "b": False})
        except FloatViolation:
            self.fail("bool must not be treated as a float")

    def test_bool_value_survives_canonical_bytes(self):
        b = codec.canonical_bytes({"flag": True, "n": 1})
        self.assertEqual(b, b'{"flag":true,"n":1}')

    def test_canonical_bytes_rejects_float(self):
        with self.assertRaises(FloatViolation):
            codec.canonical_bytes({"ratio": 3.14})


class TestNanInfRejected(unittest.TestCase):
    def test_nan_rejected(self):
        with self.assertRaises(Exception):
            codec.canonical_bytes({"x": float("nan")})

    def test_inf_rejected(self):
        with self.assertRaises(Exception):
            codec.canonical_bytes({"x": float("inf")})

    def test_neg_inf_rejected(self):
        with self.assertRaises(Exception):
            codec.canonical_bytes({"x": float("-inf")})


class TestContentDigest(unittest.TestCase):
    def test_digest_format(self):
        d = codec.content_digest({"a": 1})
        self.assertTrue(d.startswith("sha256:"))
        hexpart = d[len("sha256:"):]
        self.assertEqual(len(hexpart), 64)
        self.assertRegex(hexpart, r"^[0-9a-f]{64}$")

    def test_digest_matches_manual_sha256(self):
        payload = {"a": 1, "b": 2}
        expected = "sha256:" + hashlib.sha256(codec.canonical_bytes(payload)).hexdigest()
        self.assertEqual(codec.content_digest(payload), expected)

    def test_digest_key_order_independent(self):
        self.assertEqual(
            codec.content_digest({"a": 1, "b": 2}),
            codec.content_digest({"b": 2, "a": 1}),
        )


class TestEventIdFromOid(unittest.TestCase):
    def test_good_oid(self):
        eid = codec.event_id_from_oid(GOOD_OID)
        self.assertEqual(eid, "mu:" + GOOD_OID)
        self.assertRegex(eid, codec.EVENT_ID_RE)

    def test_good_oid_mixed(self):
        eid = codec.event_id_from_oid(GOOD_OID_2)
        self.assertEqual(eid, "mu:" + GOOD_OID_2)

    def test_event_id_re_pattern_value(self):
        self.assertEqual(codec.EVENT_ID_RE, r"^mu:[0-9a-f]{64}$")

    def test_short_oid_raises(self):
        with self.assertRaises(Exception):
            codec.event_id_from_oid("abc")

    def test_uppercase_oid_raises(self):
        with self.assertRaises(Exception):
            codec.event_id_from_oid("A" * 64)

    def test_oid_with_non_hex_raises(self):
        with self.assertRaises(Exception):
            codec.event_id_from_oid("g" * 64)

    def test_oid_with_mu_prefix_raises(self):
        # An already-prefixed value is not a raw oid.
        with self.assertRaises(Exception):
            codec.event_id_from_oid("mu:" + GOOD_OID)

    def test_non_str_oid_raises(self):
        with self.assertRaises(Exception):
            codec.event_id_from_oid(123)

    def test_re_does_not_match_bad_ids(self):
        self.assertIsNone(re.match(codec.EVENT_ID_RE, "mu:" + "A" * 64))
        self.assertIsNone(re.match(codec.EVENT_ID_RE, "mu:abc"))
        self.assertIsNotNone(re.match(codec.EVENT_ID_RE, "mu:" + GOOD_OID))


if __name__ == "__main__":
    unittest.main()

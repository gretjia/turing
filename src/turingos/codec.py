"""turingos.jcs.v1 — the canonical codec (F-5, ADR-0006).

This is the one byte-deterministic codec for the whole kernel. It implements the
frozen policy in `contracts/codec_policy.md`:

  C-1  canonical_bytes = RFC 8785 (JCS) of the payload, minimal separators,
       object keys sorted by UTF-16 code-unit order.
  C-2  ASCII-only load-bearing keys (a non-ASCII key is rejected).
  C-3  No floats (any float value is rejected; bool is NOT a float and is allowed).
  C-4  content_digest = "sha256:" + hex(sha256(canonical_bytes)).
  C-5  event_id = "mu:" + <git_commit_oid> (sha256 -> 64 hex), EVENT_ID_RE.
  C-6  determinism: two semantically-equal payloads => identical bytes & digest.

ASCII-key property: for ASCII-only keys, Python `sorted()` (Unicode code-point
order) coincides with RFC 8785 UTF-16 code-unit order, so `json.dumps(..., sort_keys=True)`
yields exactly the RFC 8785 ordering — no separate UTF-16 sort is required.

Subset only: payloads contain ASCII keys and values drawn from {int, bool, None,
str, list, dict}. NaN/Inf are rejected (`allow_nan=False`).
"""
from __future__ import annotations

import hashlib
import json
import re

from .errors import AsciiKeyViolation, FloatViolation

# --- C-5: identity ----------------------------------------------------------
EVENT_ID_RE = r"^mu:[0-9a-f]{64}$"
_OID_RE = re.compile(r"^[0-9a-f]{64}$")


def assert_ascii_keys(payload) -> None:
    """Recursively assert every dict key is an ASCII str (C-2).

    Raises AsciiKeyViolation on any non-str or non-ASCII key, at any depth.
    Non-dict/list scalars are no-ops (only keys are load-bearing here).
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            if not isinstance(key, str) or not key.isascii():
                raise AsciiKeyViolation(f"non-ASCII load-bearing key: {key!r}")
            assert_ascii_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_ascii_keys(item)


def assert_no_floats(payload) -> None:
    """Recursively assert no value is a float (C-3).

    Raises FloatViolation on any float value, at any depth. CRITICAL: `bool` is a
    subclass of `int` in Python but is NOT a float — bools are explicitly allowed.
    """
    if isinstance(payload, float):
        raise FloatViolation(f"float value forbidden (non-deterministic): {payload!r}")
    if isinstance(payload, dict):
        for value in payload.values():
            assert_no_floats(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_floats(item)


def canonical_bytes(payload: dict) -> bytes:
    """Return the RFC 8785 (JCS) byte string of `payload` (C-1).

    Enforces the codec guards first (ASCII keys, no floats), then serializes with
    sorted keys + minimal separators. NaN/Inf are rejected via allow_nan=False.
    """
    assert_ascii_keys(payload)
    assert_no_floats(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_digest(payload: dict) -> str:
    """Return the semantic digest "sha256:" + hex(sha256(canonical_bytes)) (C-4)."""
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def event_id_from_oid(oid: str) -> str:
    """Map a raw git commit OID (sha256, 64 lowercase hex) to an event_id (C-5).

    Returns "mu:" + oid. Raises ValueError if `oid` is not a bare 64-hex sha256
    OID (e.g. already prefixed, wrong length, uppercase, non-hex, or non-str).
    """
    if not isinstance(oid, str) or not _OID_RE.match(oid):
        raise ValueError(f"not a sha256 git OID (expected ^[0-9a-f]{{64}}$): {oid!r}")
    return "mu:" + oid

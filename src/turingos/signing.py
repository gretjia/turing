"""turingos.signing — ApprovalCard byte/hash model + SigningBackend seam (B-5/B.4, ADR-0007).

Implements the corrected, binding model from `contracts/approval_card.md`:

    canonical_bytes   := JCS(load-bearing signed fields, ASCII keys, no floats)
                         # display / localization copy EXCLUDED  (the ONE signed input)
    visible_card_hash := sha256(canonical_bytes)   # DERIVED digest, shown to a human (NOT the bytes)
    signature         := sign(canonical_bytes)     # DERIVED over the SAME bytes (NOT the bytes)
    gate / replay     := re-derive sha256(canonical_bytes) AND verify(signature, canonical_bytes)

The prior plan's four-way byte-equality
(`canonical_bytes == visible_card_hash == signed == gate-consumed`) is a category
error and is retired: a hash and a signature are *functions of* the bytes, never
byte-equal to them.

`SigningBackend` is an open seam abstracted from day one. The 1.0 implementation is
`InProcSigningBackend`, a deterministic in-process HMAC-SHA256 signer sufficient for
local fake-worker E2E. `OSKeyringSigningBackend` (1.x) and `HardwareSigningBackend`
(2.0) are reserved backends behind the same seam — never a rewrite.

Fail-closed [Art. I.1]: ANY tamper of a signed field, hash, or signature — or a
missing/malformed card field, or a wrong/revoked signer — yields verify == False.
No exception escapes `verify_approval_card`.

Stdlib only (`hashlib`, `hmac`, `abc`). No third-party runtime dependency.
"""
from __future__ import annotations

import abc
import hashlib
import hmac

from . import codec

# The card's non-signed display block. EXCLUDED from canonical_bytes so that
# changing display / localization copy perturbs neither the hash nor the signature.
DISPLAY_KEY = "display"

# Default in-process key + key_id for the 1.0 deterministic signer. This is NOT a
# secret-management story (real OS-keyring / hardware signing is BLOCKED, BLK-4);
# it exists solely so local fake-worker E2E has a deterministic, verifiable signer.
_DEFAULT_INPROC_KEY = b"turingos.signing.inproc.v1"
_DEFAULT_INPROC_KEY_ID = "inproc.v1"


class SigningBackend(abc.ABC):
    """Open signing seam. A backend signs/verifies raw `canonical_bytes`.

    Reserved richer backends (`OSKeyringSigningBackend`, `HardwareSigningBackend`)
    implement this same interface — `key_id` is a first-class signed field so a
    stronger authority/hardware route can be added without rewriting the byte model.
    """

    @abc.abstractmethod
    def sign(self, canonical_bytes: bytes) -> str:
        """Return a deterministic signature (hex str) over `canonical_bytes`."""
        raise NotImplementedError

    @abc.abstractmethod
    def verify(self, canonical_bytes: bytes, signature: str) -> bool:
        """Return True iff `signature` is this backend's signature of `canonical_bytes`."""
        raise NotImplementedError

    @abc.abstractmethod
    def key_id(self) -> str:
        """Stable identifier of the signing key (a first-class signed card field)."""
        raise NotImplementedError


class InProcSigningBackend(SigningBackend):
    """Deterministic in-process signer for 1.0 local E2E (HMAC-SHA256 over a fixed key).

    Deterministic: the same bytes + key always yield the same signature, so cards
    are byte-stable across runs and replay can re-verify them. Verification is
    constant-time (`hmac.compare_digest`) and fail-closed on any malformed signature.
    """

    def __init__(self, key: bytes = _DEFAULT_INPROC_KEY, key_id: str = _DEFAULT_INPROC_KEY_ID):
        if not isinstance(key, (bytes, bytearray)):
            raise TypeError(f"InProcSigningBackend key must be bytes, got {type(key).__name__}")
        if not isinstance(key_id, str) or not key_id:
            raise ValueError("InProcSigningBackend key_id must be a non-empty str")
        self._key = bytes(key)
        self._key_id = key_id

    def sign(self, canonical_bytes: bytes) -> str:
        if not isinstance(canonical_bytes, (bytes, bytearray)):
            raise TypeError("sign() requires bytes")
        return hmac.new(self._key, bytes(canonical_bytes), hashlib.sha256).hexdigest()

    def verify(self, canonical_bytes: bytes, signature: str) -> bool:
        # Fail-closed: any malformed input (non-bytes, non-str signature) => False,
        # never an exception. Constant-time compare of the recomputed MAC.
        if not isinstance(canonical_bytes, (bytes, bytearray)) or not isinstance(signature, str):
            return False
        expected = self.sign(bytes(canonical_bytes))
        return hmac.compare_digest(expected, signature)

    def key_id(self) -> str:
        return self._key_id


def _signed_fields(fields: dict) -> dict:
    """Project `fields` to the SIGNED load-bearing subset (everything except display).

    The display / localization block is excluded so it perturbs no derived value.
    """
    return {k: v for k, v in fields.items() if k != DISPLAY_KEY}


def build_approval_card(fields: dict, backend: SigningBackend) -> dict:
    """Build a signed ApprovalCard from `fields` using `backend`.

    `fields` carries the signed load-bearing keys (action_kind, target,
    evidence_set_digest, risk_class, expires_at, nonce, tape_tip, accepted_head,
    authority_epoch, signature_route, key_id) plus an optional non-signed
    ``display`` block.

    Returns a card dict with:
      - ``canonical_bytes``    : hex of JCS(signed load-bearing fields)  (the ONE signed input)
      - ``visible_card_hash``  : sha256(canonical_bytes) hex            (DERIVED, shown to human)
      - ``signature``          : backend.sign(canonical_bytes)         (DERIVED over same bytes)
      - ``key_id``             : backend.key_id()
      - ``display``            : the excluded display block (default {} )
    """
    if not isinstance(fields, dict):
        raise TypeError("fields must be a dict")
    signed = _signed_fields(fields)
    raw = codec.canonical_bytes(signed)  # enforces ASCII keys + no floats
    return {
        "canonical_bytes": raw.hex(),
        "visible_card_hash": hashlib.sha256(raw).hexdigest(),
        "signature": backend.sign(raw),
        "key_id": backend.key_id(),
        "display": fields.get(DISPLAY_KEY, {}),
    }


def verify_approval_card(card: dict, backend: SigningBackend) -> bool:
    """Re-derive the hash and re-verify the signature over the card's canonical_bytes.

    Fail-closed [Art. I.1]: returns False on ANY tamper of a signed field
    (canonical_bytes), on a mismatched ``visible_card_hash``, on a bad/forged
    ``signature``, on a wrong/revoked signer, or on a missing/malformed card field.
    Never raises — every error path collapses to False.
    """
    if not isinstance(card, dict):
        return False
    try:
        cb_hex = card["canonical_bytes"]
        stored_hash = card["visible_card_hash"]
        signature = card["signature"]
    except (KeyError, TypeError):
        return False
    if not isinstance(cb_hex, str) or not isinstance(stored_hash, str) or not isinstance(signature, str):
        return False
    try:
        raw = bytes.fromhex(cb_hex)
    except ValueError:
        return False
    # Re-derive the visible hash and compare (constant-time).
    rederived_hash = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(rederived_hash, stored_hash):
        return False
    # Re-verify the signature over the SAME canonical_bytes.
    try:
        return bool(backend.verify(raw, signature))
    except Exception:
        return False

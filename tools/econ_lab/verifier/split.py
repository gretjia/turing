"""ADR-ECON-003 Decision 2(a): the held-out split function. Case IDs partition into the
accept side (judged by the ∏p acceptance predicate / this harness's "accept" outcome
field) and the verify side (judged only by `independent_verifier.verify`), with an empty
intersection by construction -- a single case can only ever land on one side.

"held-out split 由 SHA256("heldout-split.v1" ‖ case_id) 的首字节奇偶决定
(偶→接受侧,奇→验证侧)" -- copied verbatim, domain separator included.
"""
from __future__ import annotations

import hashlib

SPLIT_DOMAIN_SEPARATOR = "heldout-split.v1"

ACCEPT_SIDE = "accept"
VERIFY_SIDE = "verify"


def split_side(case_id: str) -> str:
    """Deterministic accept/verify partition for a single ``case_id`` (Decision 2(a))."""
    digest = hashlib.sha256((SPLIT_DOMAIN_SEPARATOR + case_id).encode("utf-8")).digest()
    return ACCEPT_SIDE if digest[0] % 2 == 0 else VERIFY_SIDE

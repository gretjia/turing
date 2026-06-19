"""turingos.envelope — the 7-field Append Envelope (B-2, ADR-0002) [Art. 0.2 / 0.3].

Frozen Stage-0 interface (contracts/INTERFACES.md envelope.py section,
contracts/append_envelope.md). One micro Git commit per sovereignty-boundary change carries
exactly one event whose envelope is this 7-field shape. Five fields are load-bearing in 1.0,
two are reserved forward-compat seams (`writer_id` fixed single-writer; `authority_epoch`
deferred — no fencing in 1.0).

This module is a pure data carrier + payload projection. It does NOT touch git, the codec, or
the Tape; the local guard checks (FF parent, schema-known, head_effect-registry-derived,
payload_hash match, single-writer identity, accepted_head ancestor) live on the Tape's append
path. The one piece of policy enforced here is that head_effect is REGISTRY-DERIVED, never
writer-trusted: callers obtain it via derive_head_effect(), which delegates to registry.head_effect.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import registry


@dataclass(frozen=True)
class AppendEnvelope:
    """The frozen 7-field append envelope.

    Field order is part of the frozen contract (positional construction is supported):

      prev_tape_tip        load-bearing — FF parent: parent == prev_tape_tip (reject non-FF)
      event_schema_id      load-bearing — event type / payload schema id (closed-world)
      payload_hash         load-bearing — = content_digest = sha256(JCS(payload))
      head_effect          load-bearing — registry-derived (ADVANCE|PRESERVE); never writer-trusted
      accepted_head_before load-bearing — accepted_head the writer observed (ancestor-of tape_tip)
      writer_id            RESERVED-fixed — single active sovereign writer (audit/handoff)
      authority_epoch=0    RESERVED-deferred — not enforced in 1.0 (no lease/epoch fencing)
    """

    prev_tape_tip: str
    event_schema_id: str
    payload_hash: str
    head_effect: str
    accepted_head_before: str
    writer_id: str
    authority_epoch: int = 0

    def to_payload(self) -> dict:
        """Project the envelope to a plain dict with exactly the 7 ASCII keys.

        A fresh dict each call (mutating the result never affects the frozen envelope), so it is
        safe to feed straight to the JCS codec / commit builder.
        """
        return {
            "prev_tape_tip": self.prev_tape_tip,
            "event_schema_id": self.event_schema_id,
            "payload_hash": self.payload_hash,
            "head_effect": self.head_effect,
            "accepted_head_before": self.accepted_head_before,
            "writer_id": self.writer_id,
            "authority_epoch": self.authority_epoch,
        }


def derive_head_effect(event_type: str) -> str:
    """Return 'ADVANCE' | 'PRESERVE' for an event type, REGISTRY-DERIVED.

    Thin delegation to registry.head_effect — the single source of truth for ADVANCE/PRESERVE.
    Carrying head_effect via this function (rather than trusting a writer-supplied value) is what
    makes the Tape guard able to REJECT any envelope whose head_effect disagrees with the registry.
    An unknown event_type propagates registry's closed-world errors.RejectedAppend.
    """
    return registry.head_effect(event_type)

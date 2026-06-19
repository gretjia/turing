"""turingos.explore — Exploration disposition + typed Human Steer (LOOP layer).

Frozen seam (contracts/INTERFACES.md explore.py section):
    def register_exploration(tape, exploration) -> str                       # local handle (NO tape event)
    def archive_exploration(tape, exploration_id, *, predicate_pass) -> str   # ExplorationArchived (SOVEREIGN_ACCEPT)
    def promote_exploration(tape, exploration_id, *, predicate_pass) -> str    # ExplorationPromoted (SOVEREIGN_ACCEPT)
    def inject_human_steer(tape, message) -> str                              # HumanSteerInjected (PROPOSAL)

Design (per the 18-event registry, contracts/event_registry.md):

  * There is NO dedicated "exploration registered" event in the 18-event registry. Registration
    is therefore a LOCAL handle, not a sovereignty-boundary change: `register_exploration` returns
    a deterministic content-derived `exploration_id` and appends NOTHING to the Tape — neither ref
    moves. The SOVEREIGN dispositions (archive / promote) are the recorded Tape state, and they
    reference that id. Making register a no-op append would either misuse a PROPOSAL event or fake
    a sovereign event; the registry's truth is that only the disposition is sovereign.

  * archive_exploration / promote_exploration emit ExplorationArchived / ExplorationPromoted —
    both SOVEREIGN_ACCEPT (head_effect=ADVANCE). The Tape advances accepted_head (and tape_tip)
    ONLY on a deterministic Predicate PASS [Art. I.1]; we pass predicate_pass straight through to
    tape.append, whose ADVANCE invariant rejects (RejectedAppend) anything that is not a True PASS.
    A failed disposition is never a non-advancing SOVEREIGN_ACCEPT — it simply does not land.

  * inject_human_steer emits HumanSteerInjected — a PROPOSAL (head_effect=PRESERVE): a typed steer/
    authorization event injected into the loop. It advances tape_tip ONLY, never accepted_head, and
    needs no predicate PASS to land (ordinary authorization is a PRESERVE Tape event, not a 3rd-ref
    advance — there is no authorization_head in 1.0).

Stdlib only. The Tape substrate enforces the single-writer FF guard, the registry-derived
head_effect, the ADVANCE-requires-PASS invariant, and the codec guard on every payload; this
module only shapes the disposition/steer payloads and the local exploration id.
"""
from __future__ import annotations

from . import codec
from .errors import RejectedAppend

# Registry event names this module emits.
_ARCHIVED_EVENT = "ExplorationArchived"      # SOVEREIGN_ACCEPT (ADVANCE)
_PROMOTED_EVENT = "ExplorationPromoted"      # SOVEREIGN_ACCEPT (ADVANCE)
_STEER_EVENT = "HumanSteerInjected"          # PROPOSAL (PRESERVE)


def register_exploration(tape: "Tape", exploration: dict) -> str:
    """Register an explored branch as a LOCAL handle; return a deterministic exploration_id.

    This appends NOTHING to the Tape (no ref moves): there is no dedicated "registered" event in
    the 18-event registry, and registration is not a sovereignty-boundary change. The id is the
    content digest of the exploration record (RFC-8785 JCS over the payload, also running the codec
    guard), so the same exploration content always yields the same id and a later archive/promote
    disposition can reference it deterministically. A non-dict exploration is rejected.
    """
    if not isinstance(exploration, dict):
        raise RejectedAppend(
            f"exploration must be an object, got {type(exploration).__name__}"
        )
    # content_digest runs the ASCII-key / no-float codec guard and yields "sha256:"+hex.
    return codec.content_digest(exploration)


def _dispose(tape, event_type: str, exploration_id: str, disposition: str,
             predicate_pass: bool) -> str:
    """Emit a sovereign disposition (ExplorationArchived/Promoted) for an exploration.

    The payload records the exploration_id and the disposition. The append is a SOVEREIGN_ACCEPT,
    so tape.append advances accepted_head ONLY on predicate_pass=True, else RejectedAppend.
    """
    if not isinstance(exploration_id, str) or not exploration_id:
        raise RejectedAppend(
            "exploration_id must be a non-empty string (the register_exploration handle)"
        )
    payload = {"exploration_id": exploration_id, "disposition": disposition}
    # SOVEREIGN_ACCEPT: registry-derived head_effect=ADVANCE; the Tape's ADVANCE invariant
    # rejects (RejectedAppend) unless predicate_pass is exactly True.
    return tape.append(event_type, payload, predicate_pass=predicate_pass)


def archive_exploration(tape: "Tape", exploration_id: str, *, predicate_pass: bool) -> str:
    """Archive an exploration: emit an ExplorationArchived SOVEREIGN_ACCEPT; return its event_id.

    Advances accepted_head (and tape_tip) ONLY on a deterministic Predicate PASS (predicate_pass=
    True); otherwise the Tape's ADVANCE invariant raises RejectedAppend and no commit lands.
    """
    return _dispose(tape, _ARCHIVED_EVENT, exploration_id, "archived", predicate_pass)


def promote_exploration(tape: "Tape", exploration_id: str, *, predicate_pass: bool) -> str:
    """Promote an exploration into accepted state: emit ExplorationPromoted; return its event_id.

    Advances accepted_head (and tape_tip) ONLY on a deterministic Predicate PASS (predicate_pass=
    True); otherwise the Tape's ADVANCE invariant raises RejectedAppend and no commit lands.
    """
    return _dispose(tape, _PROMOTED_EVENT, exploration_id, "promoted", predicate_pass)


def inject_human_steer(tape: "Tape", message: dict) -> str:
    """Inject a typed Human Steer event (HumanSteerInjected PROPOSAL); return its event_id.

    HumanSteerInjected is a PROPOSAL (head_effect=PRESERVE): a typed steer/authorization event in
    the loop. It advances tape_tip ONLY and NEVER accepted_head (there is no authorization_head in
    1.0 — ordinary authorization is a PRESERVE Tape event). No predicate PASS is required to land.
    """
    if not isinstance(message, dict):
        raise RejectedAppend(
            f"human steer message must be an object, got {type(message).__name__}"
        )
    # PROPOSAL append: registry-derived head_effect=PRESERVE; tape_tip advances only.
    return tape.append(_STEER_EVENT, message)

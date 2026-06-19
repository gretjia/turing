"""turingos.evidence — Worker Receipt import + Macro-anchor binding (M4 evidence store).

Frozen seam (contracts/INTERFACES.md evidence.py section):
    def import_receipt(tape: "Tape", receipt: dict) -> str         # emits WorkerReceiptImported
    def import_macro_observation(tape: "Tape", obs: dict) -> str    # emits MacroObservationImported

Both imports are OBSERVATIONs in the 18-event registry (head_effect=PRESERVE): they advance
`tape_tip` and NEVER `accepted_head`. Importing evidence is NOT acceptance — the deterministic
Predicate kernel re-derives/re-runs the gate; a receipt's worker self-reports are recorded for
audit but are never trusted (contracts/receipt.schema.json; plan App C, OBSERVATION class).

  * import_receipt:
      - schemas.validate_receipt(receipt) FIRST (structural P1 + the P0 codec guard);
        an invalid receipt raises SchemaInvalid and NO commit lands (the tape is unchanged).
      - tape.append('WorkerReceiptImported', receipt) → one Micro commit, tape_tip advances.
      - returns the event_id ("mu:"+oid).

  * import_macro_observation:
      - require obs is a dict carrying a NON-EMPTY string 'tree_oid' — this is the Macro Git
        tree OID anchor the predicate P7 (ANCHOR_BINDS_HASH) binds against. Macro Git/worktree/
        PR/CI evidence is imported, never directly sovereign. A missing / empty / non-string
        tree_oid is rejected (RejectedAppend) and NO commit lands.
      - tape.append('MacroObservationImported', obs) → one Micro commit, tape_tip advances.
      - returns the event_id ("mu:"+oid).

Stdlib only. The Tape itself enforces the single-writer FF guard, the registry-derived
head_effect, and the codec guard on the payload; this module adds the receipt-schema gate and
the macro tree_oid-anchor requirement on top of that substrate.
"""
from __future__ import annotations

from . import schemas
from .errors import RejectedAppend

# Registry event names this module emits (both OBSERVATION / PRESERVE).
_RECEIPT_EVENT = "WorkerReceiptImported"
_MACRO_EVENT = "MacroObservationImported"


def import_receipt(tape: "Tape", receipt: dict) -> str:
    """Import a Worker Receipt as a WorkerReceiptImported OBSERVATION; return its event_id.

    Receipt != acceptance: this records the worker self-report on the Tape for audit. The
    receipt is validated against turingos.receipt.v1 FIRST — an invalid receipt raises
    SchemaInvalid before any commit lands, so the tape is left untouched. On success exactly
    one Micro commit is written and tape_tip advances; accepted_head is NOT touched (PRESERVE).
    """
    # Structural gate FIRST (raises SchemaInvalid; no commit on failure).
    schemas.validate_receipt(receipt)
    # OBSERVATION append: head_effect is registry-derived (PRESERVE); tape_tip advances only.
    return tape.append(_RECEIPT_EVENT, receipt)


def import_macro_observation(tape: "Tape", obs: dict) -> str:
    """Import a Macro Git/worktree/CI observation as MacroObservationImported; return its event_id.

    The observation MUST carry a non-empty string 'tree_oid' — the Macro Git tree OID anchor that
    predicate P7 (ANCHOR_BINDS_HASH) binds the accepted candidate against. Macro state is never
    directly sovereign; it is imported as an OBSERVATION (PRESERVE) so tape_tip advances and
    accepted_head does not. A missing / empty / non-string tree_oid is rejected before any commit
    lands (RejectedAppend), leaving the tape untouched.
    """
    if not isinstance(obs, dict):
        raise RejectedAppend(
            f"macro observation must be an object, got {type(obs).__name__}"
        )
    tree_oid = obs.get("tree_oid")
    if not isinstance(tree_oid, str) or not tree_oid:
        raise RejectedAppend(
            "macro observation requires a non-empty string 'tree_oid' (the P7 anchor)"
        )
    # OBSERVATION append: head_effect is registry-derived (PRESERVE); tape_tip advances only.
    return tape.append(_MACRO_EVENT, obs)

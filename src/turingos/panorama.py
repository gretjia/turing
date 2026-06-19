"""turingos.panorama — a text panorama over the DERIVED WorkGraph projection (M5/M11 seam).

Frozen Stage-0 interface (contracts/INTERFACES.md panorama.py section):

    def render(tape) -> str

The panorama is a *view*: it renders the derived projection of the Tape and owns NO truth.

  * It reads ONLY the derived fold of the Micro Tape:
        q_t       = turingos.reduce.reduce_qt(tape)
        workgraph = turingos.reduce.derive_workgraph(q_t, tape, [])
    Both are pure reads (Tape-Canonical [Art. 0.2]); rendering NEVER appends to the tape or moves
    a ref. After render(tape), tape_tip and accepted_head are unchanged (conservation).

  * Binding UI/copy rule (contracts/refs.md App C §C.1.1 / plan App C §C.1.1): even with two
    refs the UI MUST distinguish **Authorized** vs **Accepted**. It is FORBIDDEN to render an
    authorization (a Worker dispatch / a Macro merge) as "accepted / completed / done". The only
    permitted lifecycle labels are:

        Authorized, Pending execution, Awaiting receipt, Receipt matched, Accepted world state

    `accepted_head` (HEAD_t) is the ONLY thing this renderer ever labels "Accepted world state".
    A `WorkerDispatched` (and a Macro merge) is an authorization — a PRESERVE Tape event that
    moves `tape_tip` but NOT `accepted_head` — so it is shown under an Authorized-style label,
    never as accepted/done.

Determinism: render() reads only the Tape bytes (oids, event types, payloads) — no clock, no host
identity — so the same Tape yields a byte-equal panorama every time.

Stdlib only for the default text render. The ONLY optional dependency is `textual`, used solely to
provide an optional interactive TUI app (`PanoramaApp`). It is imported under a guarded try/except
so that the absence of textual NEVER breaks importing this module or calling render().
"""
from __future__ import annotations

from . import reduce as _reduce

# --- optional Textual TUI (guarded) -----------------------------------------------------------
# The default render() is pure stdlib. Textual, if present, powers an optional interactive app.
# Absence of textual must NOT break import or render(), so the import is fully guarded.
try:  # pragma: no cover - exercised only where textual is installed
    from textual.app import App as _TextualApp
    from textual.widgets import Static as _TextualStatic

    HAS_TEXTUAL = True
except Exception:  # ImportError, or any partial-install failure
    _TextualApp = None
    _TextualStatic = None
    HAS_TEXTUAL = False


# --- the binding label vocabulary (refs.md App C §C.1.1) --------------------------------------
# Authorized-style labels describe authorizations (PRESERVE events: dispatch / macro merge / capsule)
# — never the accepted world state.
LABEL_AUTHORIZED = "Authorized"
LABEL_PENDING = "Pending execution"
LABEL_AWAITING_RECEIPT = "Awaiting receipt"
LABEL_RECEIPT_MATCHED = "Receipt matched"
LABEL_ACCEPTED = "Accepted world state"  # ONLY ever applied to accepted_head (HEAD_t)

ALLOWED_LABELS = (
    LABEL_AUTHORIZED,
    LABEL_PENDING,
    LABEL_AWAITING_RECEIPT,
    LABEL_RECEIPT_MATCHED,
    LABEL_ACCEPTED,
)

# Map the lifecycle-relevant event types to the lifecycle label that describes them. Every entry
# here is an AUTHORIZATION or OBSERVATION (PRESERVE) — by construction none maps to LABEL_ACCEPTED,
# which is reserved for accepted_head. WorkerDispatched (and macro merge) => Authorized-style only.
_EVENT_LABEL = {
    "WorkCapsuleBuilt": LABEL_AUTHORIZED,
    "WorkerDispatched": LABEL_AUTHORIZED,          # an authorization, NEVER "accepted/done"
    "MacroObservationImported": LABEL_AUTHORIZED,  # a Macro merge/PR/CI observation — authorization
    "WorkerReceiptImported": LABEL_AWAITING_RECEIPT,
    "PredicateEvaluated": LABEL_RECEIPT_MATCHED,
}


def _short(oid):
    """A short, deterministic display form of an oid (full oid is still shown where load-bearing)."""
    if not oid:
        return "(none)"
    return oid[:12] + "..." if len(oid) > 12 else oid


def _atom_status_label(q_t) -> str:
    """The lifecycle label for the active atom, derived purely from q_t (retry_state)."""
    atom = q_t.get("active_atom")
    if not isinstance(atom, dict):
        return LABEL_PENDING
    # An atom with recorded failures is still pending (re)execution, not accepted.
    return LABEL_PENDING


def _render_text(tape) -> str:
    """Build the deterministic text panorama from the derived projection (q_t + WorkGraph)."""
    q_t = _reduce.reduce_qt(tape)
    wg = _reduce.derive_workgraph(q_t, tape, [])

    accepted_head = wg.get("accepted_head")
    tape_tip = wg.get("tape_tip")

    lines: list = []
    lines.append("TuringOS panorama (derived projection — owns no truth)")
    lines.append("=" * 56)

    # --- the two refs, with the binding Authorized/Accepted distinction made explicit ----------
    # accepted_head is the ONLY thing ever labelled 'Accepted world state'.
    lines.append(f"{LABEL_ACCEPTED}: accepted_head = {accepted_head if accepted_head else '(none)'}")
    # tape_tip is the universal append head — NOT an acceptance. Label it as such, never 'accepted'.
    lines.append(f"tape_tip (append head, authorizations land here): {tape_tip if tape_tip else '(none)'}")
    lines.append("")

    # --- q_t summary (active goal/module/atom + policy) ----------------------------------------
    lines.append("q_t (reduced state):")
    goal = q_t.get("active_goal")
    module = q_t.get("active_module")
    atom = q_t.get("active_atom")
    policy = q_t.get("current_policy")
    pending = q_t.get("pending_decision")

    lines.append("  active_goal:   " + (str(goal.get("goal_id")) if isinstance(goal, dict) else "(none)"))
    lines.append("  active_module: " + (str(module.get("module_id")) if isinstance(module, dict) else "(none)"))
    if isinstance(atom, dict):
        lines.append(
            "  active_atom:   "
            + str(atom.get("atom_id"))
            + "  [" + _atom_status_label(q_t) + "]"
            + ("  retries=" + str(q_t.get("retry_state")) if q_t.get("retry_state") else "")
        )
    else:
        lines.append("  active_atom:   (none)")
    lines.append("  current_policy: " + (str(policy.get("name")) if isinstance(policy, dict) else "(none)"))
    if pending is not None:
        lines.append("  pending_decision: " + str(pending.get("decision_id") if isinstance(pending, dict) else pending))
    lines.append("")

    # --- WorkGraph nodes (the structural projection of q_t + declared macro observations) -------
    lines.append("WorkGraph nodes:")
    nodes = wg.get("nodes") or []
    if not nodes:
        lines.append("  (no nodes)")
    for node in nodes:
        nid = node.get("id")
        kind = node.get("kind")
        lines.append(f"  - {kind}: {nid}")
    lines.append("")

    # --- lifecycle of authorizations on the tape ----------------------------------------------
    # Walk the tape (a pure read) and label each lifecycle-relevant event with an ALLOWED label.
    # CRITICAL: an authorization (WorkerDispatched / macro merge) is shown under an Authorized-style
    # label, NEVER 'accepted/completed/done'. accepted_head alone bears 'Accepted world state'.
    lines.append("Authorizations & observations (tape_tip lane — NOT acceptance):")
    walked = tape.walk()
    any_lifecycle = False
    for ev in walked:
        etype = ev.get("event_type")
        label = _EVENT_LABEL.get(etype)
        if label is None:
            continue
        any_lifecycle = True
        oid = ev.get("oid")
        # The label is constrained to the Authorized-style / Awaiting / Receipt-matched set above;
        # by construction it is never LABEL_ACCEPTED here.
        lines.append(f"  [{label}] {etype} @ {_short(oid)}")
    if not any_lifecycle:
        lines.append("  (no authorizations dispatched yet)")
    lines.append("")

    # --- the one acceptance line (HEAD_t) ------------------------------------------------------
    if accepted_head:
        lines.append(f"[{LABEL_ACCEPTED}] HEAD_t = {accepted_head}")
    else:
        lines.append(f"[{LABEL_ACCEPTED}] HEAD_t = (none — nothing sovereignly accepted yet)")

    return "\n".join(lines) + "\n"


def render(tape) -> str:
    """Render a text panorama of the tape's DERIVED projection (stdlib only; owns no truth).

    Reads q_t = reduce.reduce_qt(tape) and workgraph = reduce.derive_workgraph(q_t, tape, []),
    then formats them into a deterministic text view that honours the binding Authorized-vs-Accepted
    distinction (contracts/refs.md App C §C.1.1). Never appends to / mutates the tape.

    Works with or without the optional `textual` package.
    """
    return _render_text(tape)


# --- optional interactive Textual TUI ---------------------------------------------------------
# Only defined when textual is importable; absence never affects import or render(). The app is a
# thin viewer over the SAME text render() — it adds no truth and performs no writes.
if HAS_TEXTUAL:  # pragma: no cover - requires the optional textual dependency

    class PanoramaApp(_TextualApp):  # type: ignore[misc, valid-type]
        """A read-only Textual viewer of render(tape). Owns no truth; performs no tape writes."""

        def __init__(self, tape, **kwargs):
            super().__init__(**kwargs)
            self._tape = tape

        def compose(self):
            yield _TextualStatic(render(self._tape))

else:

    class PanoramaApp:  # type: ignore[no-redef]
        """Placeholder when `textual` is not installed.

        Constructing it raises a clear error; the default text render() is always available via
        panorama.render(tape) regardless of whether textual is present.
        """

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "PanoramaApp requires the optional 'textual' dependency; "
                "use turingos.panorama.render(tape) for the stdlib text panorama."
            )

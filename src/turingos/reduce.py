"""turingos.reduce — fold the Tape into q_t; derive the WorkGraph projection (M4/M5 seam).

Frozen Stage-0 interface (contracts/INTERFACES.md reduce.py section):

    def reduce_qt(tape) -> dict
    def derive_workgraph(q_t, tape, macro_obs) -> dict

Two load-bearing invariants govern this module (CLAUDE.md / contracts/00_README.md fix #4):

  * Tape-Canonical [Art. 0.2]: q_t is a DERIVED fold of the Micro Tape — there is no separate
    persisted q_t. `reduce_qt` walks `tape.walk()` (genesis..tape_tip, Tape bytes only) and folds
    the event stream into the serialized current state.
  * WorkGraph = derived projection of (serialized q_t + tape_t + declared Macro observations),
    NEVER `q_t = WorkGraph`, and NEVER written back to the tape. `derive_workgraph` is a pure read:
    it MUST NOT append, mutate a ref, or otherwise touch the tape (conservation).

Both functions are deterministic: the same Tape bytes (and the same macro_obs) yield byte-equal
results, every time — a precondition for replay equality [replay.py / Art. I.1].

q_t shape (values may be None):
    {active_goal, active_module, active_atom, current_policy, pending_decision, retry_state}

Stdlib only.
"""
from __future__ import annotations

# --- event-type axis (registry names; see contracts/event_registry.json) ----------------------
_GOAL_ACCEPTED = "GoalStateAccepted"
_MODULE_ACCEPTED = "ModulePlanAccepted"
_ATOM_PROPOSED = "AtomProposed"
_FAILURE_NODE = "FailureNode"
_HUMAN_STEER = "HumanSteerInjected"

# The policy a freshly-booted, un-steered loop acts under until a HumanSteerInjected supersedes it.
# Kept as a plain dict so the projection always has a policy to display (never None on a live tape).
_DEFAULT_POLICY = {"name": "default", "source": "default"}

# The full key set of q_t — always present, even on an empty tape (values may be None).
_QT_KEYS = (
    "active_goal",
    "active_module",
    "active_atom",
    "current_policy",
    "pending_decision",
    "retry_state",
)


def _atom_id(atom_payload) -> object:
    """The identity of an atom payload (for matching FailureNodes to the active atom)."""
    if isinstance(atom_payload, dict):
        return atom_payload.get("atom_id")
    return None


def reduce_qt(tape) -> dict:
    """Fold the Micro Tape into the serialized current state q_t (derived; deterministic).

    Walks `tape.walk()` (genesis..tape_tip, Tape bytes ONLY — no sqlite/projection) and folds:

      active_goal      <- latest GoalStateAccepted payload
      active_module    <- latest ModulePlanAccepted payload (the active module)
      active_atom      <- latest AtomProposed payload
      current_policy   <- default, superseded by the latest HumanSteerInjected that carries a policy
      pending_decision <- the latest still-open decision (a HumanSteerInjected needs_decision==True),
                          else None
      retry_state      <- count of FailureNode events whose atom_id matches the active atom

    `retry_state` is scoped to the *active* atom and is naturally reset when the active atom changes,
    because failures are matched by atom_id against whatever atom is active at the end of the walk.
    Always returns all six keys (values may be None).
    """
    q: dict = {key: None for key in _QT_KEYS}
    q["current_policy"] = dict(_DEFAULT_POLICY)
    q["retry_state"] = 0

    # walk() returns [] on an empty tape, so an un-booted tape reduces to the all-None/default shape.
    events = tape.walk()

    failures_by_atom: dict = {}
    for ev in events:
        etype = ev.get("event_type")
        payload = ev.get("payload")

        if etype == _GOAL_ACCEPTED:
            q["active_goal"] = payload
        elif etype == _MODULE_ACCEPTED:
            q["active_module"] = payload
        elif etype == _ATOM_PROPOSED:
            q["active_atom"] = payload
        elif etype == _FAILURE_NODE:
            aid = payload.get("atom_id") if isinstance(payload, dict) else None
            failures_by_atom[aid] = failures_by_atom.get(aid, 0) + 1
        elif etype == _HUMAN_STEER:
            if isinstance(payload, dict):
                # A steer may inject a policy and/or open a decision; the two axes are independent.
                if payload.get("policy") is not None:
                    q["current_policy"] = payload["policy"]
                if payload.get("needs_decision") is True:
                    q["pending_decision"] = payload

    # retry_state = number of FailureNodes recorded against whatever atom is active now (or None).
    active_aid = _atom_id(q["active_atom"])
    q["retry_state"] = failures_by_atom.get(active_aid, 0)

    return q


def _qt_nodes_edges(q_t: dict) -> tuple:
    """Goal/module/atom nodes + their containment edges, derived from q_t (deterministic order)."""
    nodes: list = []
    edges: list = []

    goal = q_t.get("active_goal")
    module = q_t.get("active_module")
    atom = q_t.get("active_atom")

    goal_id = module_id = atom_id = None

    if isinstance(goal, dict):
        goal_id = "goal:" + str(goal.get("goal_id"))
        nodes.append({"id": goal_id, "kind": "goal", "data": goal})
    if isinstance(module, dict):
        module_id = "module:" + str(module.get("module_id"))
        nodes.append({"id": module_id, "kind": "module", "data": module})
        if goal_id is not None:
            edges.append({"from": goal_id, "to": module_id, "kind": "contains"})
    if isinstance(atom, dict):
        atom_id = "atom:" + str(atom.get("atom_id"))
        nodes.append({"id": atom_id, "kind": "atom", "data": atom})
        if module_id is not None:
            edges.append({"from": module_id, "to": atom_id, "kind": "contains"})

    return nodes, edges


def derive_workgraph(q_t: dict, tape, macro_obs: list) -> dict:
    """Derive the WorkGraph projection from (q_t, tape_t, declared Macro observations).

    DERIVED PROJECTION ONLY (binding wording fix #4): a pure read that NEVER writes back to the
    tape (no append, no ref move) and NEVER mutates its inputs. Reads only the two live refs
    (`tape_tip`, `accepted_head`) for the projection header; the structural body comes from q_t and
    the declared Macro observations. Deterministic: same (q_t, refs, macro_obs) => byte-equal result.

    Returns {nodes, edges, accepted_head, tape_tip}.
    """
    nodes, edges = _qt_nodes_edges(q_t)

    # Declared Macro observations are projected IN as their own nodes (never folded into q_t).
    macro_list = list(macro_obs) if macro_obs else []
    for i, obs in enumerate(macro_list):
        nodes.append({"id": "macro:" + str(i), "kind": "macro", "data": obs})

    # Projection header reads the two live refs only — a pure inspection, no mutation.
    return {
        "nodes": nodes,
        "edges": edges,
        "accepted_head": tape.accepted_head(),
        "tape_tip": tape.tape_tip(),
    }
